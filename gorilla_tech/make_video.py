#!/usr/bin/env python3
"""
make_video.py — end-to-end orchestrator for the Gorilla Tech style video agent.

    python make_video.py --topic "Mi-28N interceptado por drones FPV" \
        --entities "Mil Mi-28,Orlan-10,Wild Hornets" --lang es --minutes 13

Stages: research -> script -> assets -> voice -> subtitles -> score -> render ->
package -> validate. Every stage is cached on disk, so re-running only redoes
what changed (`--force` to rebuild everything).

Offline mode: `--offline` (or a sandbox with no internet) falls back to
`cache/<topic>.json` for research and to `templates/<name>.json` or the
deterministic fallback writer for the script.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import assets as assets_mod          # noqa: E402
import config                        # noqa: E402
import llm as llm_mod                # noqa: E402
import music                         # noqa: E402
import packaging                     # noqa: E402
import render                        # noqa: E402
import research                      # noqa: E402
import scripting                     # noqa: E402
import subtitles                     # noqa: E402
import util                          # noqa: E402
import voice                         # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Gorilla Tech style military-tech storytelling video.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--topic", default=None, help="subject of the episode")
    parser.add_argument("--entities", default="", help="comma separated platforms/units to research")
    parser.add_argument("--image-queries", default="", help="extra Wikimedia Commons queries")
    parser.add_argument("--lang", default=config.DEFAULT_LANG, choices=sorted(config.LANGUAGES),
                        help="narration + on-screen language")
    parser.add_argument("--minutes", type=float, default=config.TARGET_MINUTES,
                        help="target runtime in minutes")
    parser.add_argument("--resolution", default=config.RESOLUTION, choices=sorted(config.RESOLUTIONS),
                        help="output resolution profile")
    parser.add_argument("--fps", type=int, default=config.FPS)
    parser.add_argument("--workers", type=int, default=config.RENDER_WORKERS)
    parser.add_argument("--tts", default=config.TTS_PROVIDER,
                        choices=["edge", "elevenlabs", "openai", "none"],
                        help="narration provider")
    parser.add_argument("--voice", default="", help="override the TTS voice name")
    parser.add_argument("--brand", default="GORIZON TECH", help="on-screen channel brand")
    parser.add_argument("--project", default="", help="project directory (default projects/<slug>)")
    parser.add_argument("--template", default="", help="use a committed script template by name")
    parser.add_argument("--script", default="", help="use an existing script.json file")
    parser.add_argument("--notes", default="", help="extra editorial instructions for the writer")
    parser.add_argument("--preview", type=float, default=0.0,
                        help="render only the first N seconds (fast QA)")
    parser.add_argument("--no-music", action="store_true", help="skip the synthesised score")
    parser.add_argument("--no-subs", action="store_true", help="do not burn subtitles in")
    parser.add_argument("--no-research", action="store_true", help="skip the research stage")
    parser.add_argument("--offline", action="store_true", help="force cached/offline sources")
    parser.add_argument("--force", action="store_true", help="ignore caches and rebuild")
    parser.add_argument("--stills", action="store_true", help="also export one JPG per scene")
    parser.add_argument("--list-voices", action="store_true", help="print configured voices and exit")
    parser.add_argument("--test-llm", action="store_true", help="ping the LLM gateway and exit")
    parser.add_argument("--json", action="store_true", help="print a machine readable summary")
    return parser.parse_args(argv)


def resolve_project(args: argparse.Namespace) -> Path:
    if args.project:
        project = Path(args.project)
    else:
        slug = util.slugify(args.topic or args.template or "episode")
        project = config.PROJECTS_DIR / slug
    for sub in ("research", "assets/images", "audio", "work/segments", "output"):
        (project / sub).mkdir(parents=True, exist_ok=True)
    return project


def stage_research(args: argparse.Namespace, project: Path, offline: bool) -> dict:
    util.step("1/8  RESEARCH")
    facts_file = project / "research" / "facts.json"
    if facts_file.exists() and not args.force:
        cached = util.read_json(facts_file, {})
        util.ok("research", f"cached facts.json ({len(cached.get('entities', []))} entities, "
                            f"{len(cached.get('images', []))} images)")
        return cached
    if args.no_research or offline:
        cached = util.read_json(facts_file, {})
        if cached:
            return cached
        util.warn("research", "skipped — using bundled cache if the topic matches")
        bundled = util.read_json(config.CACHE_DIR / f"{util.slugify(args.topic or '')}.json")
        return bundled or {"topic": args.topic or "", "entities": [], "images": [], "sources": []}

    entities = [e.strip() for e in args.entities.split(",") if e.strip()]
    if not entities and args.topic:
        entities = [args.topic]
    queries = [q.strip() for q in args.image_queries.split(",") if q.strip()]
    if not queries:
        queries = entities[:4]
    try:
        return research.research_topic(
            topic=args.topic or "episode", entities=entities, lang=args.lang,
            project=project, image_queries=queries,
        )
    except Exception as exc:
        util.warn("research", f"{exc} — continuing without facts")
        return {"topic": args.topic or "episode", "entities": [], "images": [], "sources": [],
                "notes": [str(exc)]}


def stage_script(args: argparse.Namespace, project: Path, facts: dict) -> dict:
    util.step("2/8  SCRIPT & STORYBOARD")
    script_file = project / "script.json"

    if args.script:
        loaded = util.read_json(Path(args.script))
        if not loaded:
            raise SystemExit(f"cannot read --script {args.script}")
        util.ok("script", f"loaded {args.script}")
        return scripting.normalize_script(loaded, lang=args.lang, target_minutes=args.minutes,
                                          topic=args.topic or "", brand=args.brand)

    if script_file.exists() and not args.force and not args.template:
        cached = util.read_json(script_file)
        if cached and cached.get("scenes"):
            util.ok("script", f"cached script.json — {scripting.script_summary(cached)}")
            return cached

    if args.template:
        template = scripting.load_template(args.template)
        if template:
            util.ok("script", f"template '{args.template}' loaded")
            normalized = scripting.normalize_script(template, lang=template.get("meta", {}).get("lang", args.lang),
                                                    target_minutes=args.minutes,
                                                    topic=args.topic or template["meta"].get("topic", ""),
                                                    brand=args.brand)
            normalized["meta"]["generator"] = f"template:{args.template}"
            util.write_json(script_file, normalized)
            return normalized
        util.warn("script", f"template '{args.template}' not found — using fallback writer")

    client = llm_mod.LLM()
    if client.available:
        try:
            script = scripting.generate_script(
                topic=args.topic or facts.get("topic", "episode"), facts=facts,
                lang=args.lang, target_minutes=args.minutes, brand=args.brand,
                client=client, extra_notes=args.notes,
            )
            script["meta"]["generator"] = f"llm:{client.model}"
            util.write_json(script_file, script)
            util.ok("script", f"{scripting.script_summary(script)} · {client.total_tokens} tokens")
            return script
        except Exception as exc:
            util.warn("script", f"LLM failed ({str(exc)[:140]}) — deterministic fallback")
    else:
        util.warn("script", "no LLM credentials — deterministic fallback")

    script = scripting.fallback_script(
        topic=args.topic or facts.get("topic", "episode"), facts=facts, lang=args.lang,
        target_minutes=args.minutes, brand=args.brand,
    )
    util.write_json(script_file, script)
    util.ok("script", scripting.script_summary(script))
    return script


def stage_assets(script: dict, facts: dict, project: Path, offline: bool) -> dict:
    util.step("3/8  VISUAL ASSETS")
    return assets_mod.resolve_scene_images(script, facts, project,
                                           live_search=not offline, polite_delay=0.8)


def stage_voice(args: argparse.Namespace, script: dict, project: Path) -> dict:
    util.step("4/8  NARRATION")
    timing_file = project / "timing.json"
    if timing_file.exists() and not args.force:
        cached = util.read_json(timing_file, {})
        if cached and cached.get("scenes"):
            util.ok("voice", f"cached timing.json — {util.clock(cached.get('total_seconds', 0))}")
            return cached
    return voice.synthesise_scenes(script, project, provider=args.tts,
                                   voice=args.voice or None, force=args.force)


def stage_subtitles(script: dict, timing: dict, project: Path,
                    size: tuple[int, int]) -> dict:
    util.step("5/8  SUBTITLES")
    if not script.get("meta", {}).get("title"):
        util.warn("subs", "script has no title")
    cues = subtitles.build_cues(timing)
    name = util.slugify(script["meta"].get("title") or "video", 40)
    return subtitles.write_subtitles(cues, project, name, size)


def stage_music(args: argparse.Namespace, script: dict, timing: dict, project: Path) -> Path | None:
    util.step("6/8  SCORE & MIX")
    if args.no_music:
        util.log("music", "skipped (--no-music)")
        return None
    duration = float(timing.get("total_seconds", 0.0)) + 1.0
    risers, impacts = music.sfx_accents(project, timing)
    score_path = project / "audio" / "score.wav"
    if args.force or not (score_path.exists() and util.media_duration(score_path) > 0):
        music.render_score(duration, score_path, seed=int(script["meta"].get("seed", 2024)),
                           risers=risers, impacts=impacts)
    narration = voice.build_narration_track(timing, project)
    mix_path = project / "audio" / "mix.wav"
    if args.force or not (mix_path.exists() and util.media_duration(mix_path) > 0):
        music.mix_audio(narration, score_path, mix_path)
    return mix_path


def stage_render(args: argparse.Namespace, script: dict, timing: dict, project: Path,
                 size: tuple[int, int], subs: dict, mix: Path | None) -> Path:
    util.step("7/8  RENDER")
    segments = render.render_scenes(script, timing, project, size, args.fps,
                                    workers=args.workers,
                                    preview_seconds=args.preview or None, force=args.force)
    expected_total = sum(render.scene_durations(script, timing))
    if args.preview:
        expected_total = min(expected_total, args.preview)
    raw = project / "work" / "video_raw.mp4"
    raw_ok = raw.exists() and abs(util.media_duration(raw) - expected_total) < 2.0
    if args.force or not raw_ok:
        render.concat_segments(segments, raw)

    final_video = raw
    if not args.no_subs and subs.get("ass"):
        subbed = project / "work" / "video_subs.mp4"
        sub_ok = subbed.exists() and abs(util.media_duration(subbed) -
                                          util.media_duration(raw)) < 2.0
        if args.force or not sub_ok:
            fonts_dir = util.find_font(config.FONT_BOLD)
            final_video = render.burn_subtitles(raw, Path(subs["ass"]), subbed,
                                                fonts_dir.parent if fonts_dir else None)
        else:
            final_video = subbed

    name = util.slugify(script["meta"].get("title") or "video", 48)
    destination = project / "output" / f"{name}.mp4"
    render.mux(final_video, mix, destination)

    if args.stills:
        stills_dir = project / "output" / "stills"
        images = (util.read_json(project / "assets" / "images.json", {}) or {}).get("mapping", {})
        durations = render.scene_durations(script, timing)
        for scene, duration in zip(script["scenes"], durations):
            render.export_still(scene, project, size, min(2.0, duration / 2),
                                stills_dir / f"{scene['id']}.jpg", images)
        util.ok("render", f"{len(script['scenes'])} stills -> {stills_dir}")
    return destination


def stage_package(script: dict, timing: dict, project: Path, video: Path,
                  subs: dict) -> dict:
    util.step("8/8  PACKAGING")
    thumb = packaging.build_thumbnail(script, project)
    package = packaging.build_package(script, timing, project, video, subs, thumb)
    return package


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_voices:
        print(voice.voice_preview(Path(".")))
        return 0
    if args.test_llm:
        return 0 if llm_mod.test_connection() else 1
    if not args.topic and not args.template and not args.script:
        print("error: pass --topic, --template or --script", file=sys.stderr)
        return 2

    started = time.time()
    offline = args.offline or not util.probe_network()
    if offline and not args.offline:
        util.warn("net", "no internet route detected — running in offline mode")
    project = resolve_project(args)
    size = config.video_size(args.resolution)
    util.step(f"PROJECT  {project.name}")
    util.log("config", f"lang={args.lang} · {args.minutes:g} min · {size[0]}x{size[1]}@{args.fps} · "
                       f"tts={args.tts} · workers={args.workers} · offline={offline}")

    facts = stage_research(args, project, offline)
    script = stage_script(args, project, facts)
    script["meta"]["lang"] = args.lang
    script["meta"]["brand"] = args.brand
    script["meta"]["target_minutes"] = args.minutes
    script["meta"]["seed"] = abs(hash(script["meta"].get("title", "seed"))) % 9999

    asset_info = stage_assets(script, facts, project, offline)
    util.write_json(project / "script.json", script)

    timing = stage_voice(args, script, project)
    subs = stage_subtitles(script, timing, project, size)
    mix = stage_music(args, script, timing, project)
    video = stage_render(args, script, timing, project, size, subs, mix)
    package = stage_package(script, timing, project, video, subs)

    expected = float(timing.get("total_seconds", 0.0))
    if args.preview:
        expected = min(expected, args.preview)
    report = render.validate(video, expected, size, project)

    summary = {
        "topic": script["meta"].get("topic"),
        "title": package["title"],
        "language": args.lang,
        "duration_sec": report["duration_sec"],
        "resolution": report["resolution"],
        "size_bytes": report["size_bytes"],
        "video": str(video),
        "thumbnail": package["files"]["thumbnail"],
        "srt": package["files"]["srt"],
        "package_json": str(project / "output" / "package.json"),
        "images_used": len([i for i in asset_info.get("records", []) if i.get("origin") != "none"]),
        "tts_provider": timing.get("provider"),
        "script_generator": script["meta"].get("generator", "unknown"),
        "validation_passed": report["passed"],
        "elapsed_sec": round(time.time() - started, 1),
    }
    util.write_json(project / "output" / "run_report.json", summary)

    util.step("DONE")
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        for key, value in summary.items():
            print(f"  {key:<18} {value}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
