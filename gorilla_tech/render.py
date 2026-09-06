"""
Stage 7 — render.

scene specs + narration timings  ->  per-scene MP4 segments  ->  concat  ->
burn subtitles (libass)  ->  mux the mix  ->  final MP4 + validation report.

Segments are cached by content hash, so a re-render after a script tweak only
redraws the scenes that actually changed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from PIL import Image

import config
import graphics as g
import util
import visuals


# ─────────────────────────────────────────────────────────────
# Scene segments
# ─────────────────────────────────────────────────────────────

def _fade_frame(arr: np.ndarray, factor: float) -> np.ndarray:
    if factor >= 0.999:
        return arr
    return (arr.astype(np.float32) * factor).astype(np.uint8)


def render_segment(scene: dict, duration: float, size: tuple[int, int], fps: int,
                   output: Path, ctx_kwargs: dict, fade_in: float = 0.22,
                   fade_out: float = 0.28, max_seconds: float | None = None) -> Path:
    """Draw every frame of one scene and encode it straight into an MP4."""
    output.parent.mkdir(parents=True, exist_ok=True)
    ctx = visuals.SceneContext(**ctx_kwargs)
    renderer = visuals.build_scene(scene, ctx)
    frames = int(round(min(duration, max_seconds or duration) * fps))
    frames = max(1, frames)

    command = [
        util.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo", "-s", f"{size[0]}x{size[1]}",
        "-pix_fmt", "rgb24", "-r", str(fps), "-i", "-", "-an",
        "-c:v", "libx264", "-preset", config.X264_PRESET, "-crf", str(config.CRF),
        "-pix_fmt", "yuv420p", "-g", str(fps * 2), "-movflags", "+faststart",
        str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    started = time.time()
    try:
        for index in range(frames):
            t = index / fps
            image = renderer.frame(t, duration)
            arr = np.asarray(image.convert("RGB"), dtype=np.uint8)
            fade = 1.0
            if t < fade_in:
                fade = min(fade, t / max(fade_in, 1e-6))
            if t > duration - fade_out:
                fade = min(fade, max(0.0, (duration - t) / max(fade_out, 1e-6)))
            if fade < 0.999:
                arr = _fade_frame(arr, fade)
            process.stdin.write(arr.tobytes())
    except BrokenPipeError:
        pass
    finally:
        try:
            process.stdin.close()
        except Exception:
            pass
        stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
        code = process.wait(timeout=600)
    if code != 0 or not output.exists():
        raise RuntimeError(f"segment {output.name} failed: {stderr[:400]}")
    elapsed = time.time() - started
    util.log("render", f"{scene.get('id', '?'):<10} {util.clock(duration):>8} "
                       f"· {frames} frames · {elapsed:.1f}s · {util.human_size(output.stat().st_size)}")
    return output


def _worker(payload: dict) -> dict:
    """Process-pool entry point (must stay module level for spawn/fork safety)."""
    package_root = str(config.PACKAGE_ROOT)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    scene = payload["scene"]
    try:
        path = render_segment(
            scene, payload["duration"], payload["size"], payload["fps"],
            Path(payload["output"]), payload["ctx"],
            fade_in=payload.get("fade_in", 0.22), fade_out=payload.get("fade_out", 0.28),
            max_seconds=payload.get("max_seconds"),
        )
        return {"id": scene.get("id"), "ok": True, "path": str(path),
                "seconds": payload["duration"]}
    except Exception as exc:  # pragma: no cover
        return {"id": scene.get("id"), "ok": False, "error": str(exc)[:400]}


# ─────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────

def scene_durations(script: dict, timing: dict, min_scene: float = 2.5,
                    max_scene: float = 90.0) -> list[float]:
    """Authoritative durations: narration length first, script hint second."""
    by_id = {s["id"]: s for s in timing.get("scenes", [])}
    durations = []
    for scene in script.get("scenes", []):
        entry = by_id.get(scene["id"], {})
        value = float(entry.get("scene_duration") or scene.get("duration_hint") or 8.0)
        durations.append(round(min(max(value, min_scene), max_scene), 3))
    return durations


def render_scenes(script: dict, timing: dict, project: Path, size: tuple[int, int],
                  fps: int, workers: int = 1, preview_seconds: float | None = None,
                  force: bool = False) -> list[Path]:
    work = Path(project) / "work" / "segments"
    work.mkdir(parents=True, exist_ok=True)
    images = (util.read_json(Path(project) / "assets" / "images.json", {}) or {}).get("mapping", {})
    durations = scene_durations(script, timing)

    ctx_kwargs = {
        "project": Path(project),
        "lang": script["meta"].get("lang", config.DEFAULT_LANG),
        "size": size,
        "brand": script["meta"].get("brand", "GORIZON TECH"),
        "seed": int(script["meta"].get("seed", 1234)),
        "images": images,
        "show_hud": bool(script["meta"].get("show_hud", True)),
    }

    payloads, cached = [], []
    elapsed = 0.0
    for scene, duration in zip(script["scenes"], durations):
        if preview_seconds and elapsed >= preview_seconds:
            break
        elapsed += duration
        payload_duration = duration
        if preview_seconds:
            payload_duration = min(duration, preview_seconds - (elapsed - duration))
        signature = util.data_hash({
            "scene": scene, "duration": round(payload_duration, 3), "size": size, "fps": fps,
            "fade": config.XFADE_SEC, "visuals_version": "4",
        })
        segment = work / f"{scene['id']}.mp4"
        marker = work / f"{scene['id']}.hash"
        if segment.exists() and marker.exists() and marker.read_text().strip() == signature and not force:
            cached.append(segment)
            util.log("render", f"{scene['id']:<10} cached")
            continue
        util.write_text(marker, signature)
        payloads.append({
            "scene": scene, "duration": payload_duration, "size": size, "fps": fps,
            "output": str(segment), "ctx": dict(ctx_kwargs, project=str(Path(project))),
            "fade_in": 0.5 if scene.get("beat") in ("cold_open", "cta") else 0.22,
            "fade_out": 1.1 if scene.get("beat") == "cta" else 0.28,
            "max_seconds": payload_duration,
        })

    results: dict[str, Path] = {str(p): p for p in cached}
    if payloads:
        util.log("render", f"{len(payloads)} scene(s) to draw · {workers} worker(s) · "
                           f"{size[0]}x{size[1]}@{fps}")
        if workers > 1 and len(payloads) > 1:
            try:
                import multiprocessing

                context = multiprocessing.get_context("fork")
                with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
                    futures = [pool.submit(_worker, payload) for payload in payloads]
                    for future in as_completed(futures):
                        outcome = future.result()
                        if not outcome.get("ok"):
                            raise RuntimeError(f"scene {outcome.get('id')}: {outcome.get('error')}")
                        results[outcome["id"]] = Path(outcome["path"])
            except (ValueError, OSError, RuntimeError) as exc:
                util.warn("render", f"parallel render unavailable ({exc}) — sequential")
                results = {str(p): p for p in cached}
                for payload in payloads:
                    outcome = _worker(payload)
                    if not outcome.get("ok"):
                        raise RuntimeError(f"scene {outcome.get('id')}: {outcome.get('error')}")
                    results[outcome["id"]] = Path(outcome["path"])
        else:
            for payload in payloads:
                outcome = _worker(payload)
                if not outcome.get("ok"):
                    raise RuntimeError(f"scene {outcome.get('id')}: {outcome.get('error')}")
                results[outcome["id"]] = Path(outcome["path"])

    ordered = []
    for scene, duration in zip(script["scenes"], durations):
        if preview_seconds and sum(d for d in durations[:len(ordered)]) >= preview_seconds:
            break
        segment = results.get(scene["id"]) or work / f"{scene['id']}.mp4"
        if segment.exists():
            ordered.append(segment)
        if preview_seconds and sum(util.media_duration(p) for p in ordered) >= preview_seconds:
            break
    if not ordered:
        raise RuntimeError("no segments were produced")
    return ordered


def concat_segments(segments: list[Path], destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    list_file = destination.parent / "concat.txt"
    list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in segments), encoding="utf-8")
    command = [util.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
               "-f", "concat", "-safe", "0", "-i", str(list_file),
               "-c", "copy", "-movflags", "+faststart", str(destination)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        raise RuntimeError(f"concat failed: {result.stderr[:400]}")
    util.ok("render", f"{len(segments)} segments -> {destination.name} "
                      f"({util.clock(util.media_duration(destination))})")
    return destination


def burn_subtitles(video: Path, ass_file: Path, destination: Path,
                   fonts_dir: Path | None = None) -> Path:
    """Burn the styled ASS track with libass; degrade gracefully if unavailable."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    escaped = str(ass_file).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    options = f"ass='{escaped}'"
    if fonts_dir and Path(fonts_dir).exists():
        font_path = str(Path(fonts_dir)).replace("\\", "/").replace(":", "\\:")
        options += f":fontsdir='{font_path}'"
    command = [util.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
               "-i", str(video), "-vf", options,
               "-c:v", "libx264", "-preset", config.X264_PRESET, "-crf", str(config.CRF),
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(destination)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=3600)
    if result.returncode == 0 and destination.exists():
        util.ok("subs", f"burned {ass_file.name} into {destination.name}")
        return destination
    util.warn("subs", f"libass burn failed ({result.stderr[:160]}) — keeping video without subtitles")
    return video


def mux(video: Path, audio: Path | None, destination: Path,
        loudnorm: bool = True) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [util.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video)]
    if audio and Path(audio).exists():
        command += ["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-shortest"]
    else:
        command += ["-map", "0:v:0", "-c:v", "copy", "-an"]
    command += ["-movflags", "+faststart", str(destination)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        raise RuntimeError(f"mux failed: {result.stderr[:400]}")
    util.ok("render", f"final -> {destination.name} ({util.human_size(destination.stat().st_size)})")
    return destination


def validate(video: Path, expected_duration: float, size: tuple[int, int],
             project: Path) -> dict:
    probe = subprocess.run([util.ffmpeg_exe(), "-hide_banner", "-i", str(video)],
                           capture_output=True, text=True, timeout=120)
    header = probe.stderr
    duration = util.media_duration(video)
    report = {
        "file": str(video),
        "size_bytes": video.stat().st_size,
        "duration_sec": round(duration, 2),
        "expected_duration_sec": round(expected_duration, 2),
        "duration_delta_sec": round(duration - expected_duration, 2),
        "resolution": f"{size[0]}x{size[1]}",
        "has_video": "Video:" in header,
        "has_audio": "Audio:" in header,
        "codec": (header.split("Video:")[1].split(",")[0].strip() if "Video:" in header else ""),
        "audio_codec": (header.split("Audio:")[1].split(",")[0].strip() if "Audio:" in header else ""),
        "checks": {
            "duration_within_2s": abs(duration - expected_duration) < 2.0,
            "resolution_present": f"{size[0]}x{size[1]}" in header,
            "file_not_empty": video.stat().st_size > 100_000,
        },
    }
    report["passed"] = all(report["checks"].values())
    util.write_json(Path(project) / "work" / "validation.json", report)
    level = "ok" if report["passed"] else "warn"
    util.log("validate", f"{'PASS' if report['passed'] else 'CHECK FAILED'} · "
                         f"{util.clock(duration)} · {util.human_size(report['size_bytes'])} · "
                         f"{report['codec']}/{report['audio_codec']}", level)
    return report


def export_still(scene: dict, project: Path, size: tuple[int, int], t: float,
                 destination: Path, images: dict | None = None) -> Path:
    """Single frame export — used for thumbnails and visual QA."""
    ctx = visuals.SceneContext(project=Path(project), size=size,
                               images=images or {}, lang="es")
    renderer = visuals.build_scene(scene, ctx)
    frame = renderer.frame(t, max(t * 2, 4.0))
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.save(destination, quality=92)
    return destination
