"""
Stage 3 — visual assets.

Resolves one image per `photo` scene:
  1. a CC/PD photo already found during research,
  2. a live Wikimedia Commons search,
  3. an AI-generated still (only if GT_IMAGE_API_BASE + GT_IMAGE_API_KEY are set),
  4. nothing — the renderer then falls back to the scene's `fallback` visual type.

Downloaded files and their licence metadata are written to `assets/images.json`,
which `packaging.py` turns into the on-screen credits and CREDITS.md.
"""

from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path

import config
import research
import util

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9]+", (text or "").lower()) if len(t) > 3]


def match_score(query: str, title: str) -> int:
    q, t = _tokens(query), set(_tokens(title))
    if not q:
        return 0
    hits = sum(1 for token in q if token in t)
    score = hits * 4
    lowered = title.lower()
    if any(bad in lowered for bad in ("icon", "logo", "map of", "flag", "coat of arms", "schema")):
        score -= 6
    return score


def download_candidates(query: str, limit: int = 5) -> list[dict]:
    try:
        return research.commons_search(query, limit=limit)
    except Exception as exc:
        util.warn("assets", f"commons search failed for '{query}': {str(exc)[:90]}")
        return []


def generate_ai_image(prompt: str, destination: Path) -> Path | None:
    """Optional AI still. Skipped silently when no image API is configured."""
    if not (config.IMAGE_GEN_API_BASE and config.IMAGE_GEN_API_KEY):
        return None
    try:
        response = util.http_post_json(
            f"{config.IMAGE_GEN_API_BASE.rstrip('/')}/images/generations",
            {"model": config.IMAGE_GEN_MODEL or "gpt-image-1", "prompt": prompt,
             "size": "1536x1024", "n": 1},
            headers={"Authorization": f"Bearer {config.IMAGE_GEN_API_KEY}"},
            timeout=240,
        )
    except Exception as exc:
        util.warn("assets", f"AI image generation failed: {str(exc)[:120]}")
        return None
    data = (response.get("data") or [{}])[0]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if data.get("b64_json"):
        destination.write_bytes(base64.b64decode(data["b64_json"]))
        return destination
    if data.get("url"):
        try:
            return util.download_file(data["url"], destination)
        except Exception as exc:
            util.warn("assets", f"AI image download failed: {str(exc)[:120]}")
    return None


def resolve_scene_images(script: dict, facts: dict, project: Path,
                         live_search: bool = True, polite_delay: float = 1.0) -> dict:
    """Fill `ctx.images` (scene id -> local path) and write assets/images.json."""
    image_dir = Path(project) / "assets" / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    available = list((facts or {}).get("images") or [])
    used_urls: set[str] = set()
    mapping: dict[str, str] = {}
    records: list[dict] = []

    photo_scenes = [s for s in script.get("scenes", [])
                    if str(s.get("visual", {}).get("type", "")).lower() in ("photo", "image")]
    if not photo_scenes:
        util.log("assets", "no photo scenes in script")
        util.write_json(Path(project) / "assets" / "images.json", {"images": [], "mapping": {}})
        return {"mapping": {}, "records": []}

    for scene in photo_scenes:
        scene_id = scene["id"]
        query = str(scene["visual"].get("image_query") or scene["visual"].get("name")
                    or script["meta"].get("topic", ""))
        chosen = None
        for candidate in available:
            url = candidate.get("url", "")
            if url in used_urls:
                continue
            if match_score(query, candidate.get("title", "")) >= 4:
                chosen = candidate
                break
        if chosen is None and live_search and util.probe_network():
            fresh = download_candidates(query, limit=6)
            time.sleep(polite_delay)
            available.extend(fresh)
            best, best_score = None, 0
            for candidate in fresh:
                if candidate.get("url") in used_urls:
                    continue
                score = match_score(query, candidate.get("title", ""))
                if score > best_score:
                    best, best_score = candidate, score
            chosen = best if best_score >= 4 else (fresh[0] if fresh else None)

        if chosen is not None:
            local = _download(chosen, image_dir, scene_id)
            if local:
                used_urls.add(chosen.get("url", ""))
                mapping[scene_id] = str(local)
                credit = _credit_line(chosen)
                scene["visual"]["credit"] = scene["visual"].get("credit") or credit
                scene["visual"]["caption"] = scene["visual"].get("caption") or \
                    _clean_title(chosen.get("title", ""))[:70]
                records.append({
                    "scene_id": scene_id, "query": query, "file": local.name,
                    "title": chosen.get("title", ""), "page": chosen.get("page", ""),
                    "source": chosen.get("url", ""), "license": chosen.get("license", ""),
                    "artist": chosen.get("artist", ""), "credit": credit,
                    "origin": "wikimedia-commons",
                })
                util.ok("assets", f"{scene_id}: {local.name} [{chosen.get('license', '?')}]")
                continue

        # AI fallback (opt-in) — clearly labelled in the credits
        if config.IMAGE_GEN_API_BASE and config.IMAGE_GEN_API_KEY:
            prompt = (f"Photorealistic documentary still of {query}, overcast battlefield light, "
                      f"muted cold colour grade, no text, no logos, 16:9")
            generated = generate_ai_image(prompt, image_dir / f"{scene_id}_ai.png")
            if generated:
                mapping[scene_id] = str(generated)
                scene["visual"]["credit"] = "AI-generated illustration (not a real photograph)"
                records.append({"scene_id": scene_id, "query": query, "file": generated.name,
                                "title": query, "origin": "ai-generated",
                                "license": "synthetic", "credit": scene["visual"]["credit"]})
                util.ok("assets", f"{scene_id}: AI still {generated.name}")
                continue

        util.warn("assets", f"{scene_id}: no usable image for '{query}' -> "
                            f"fallback {scene['visual'].get('fallback', 'text')}")
        records.append({"scene_id": scene_id, "query": query, "origin": "none"})

    util.write_json(Path(project) / "assets" / "images.json",
                    {"images": records, "mapping": mapping})
    return {"mapping": mapping, "records": records}


def _download(record: dict, image_dir: Path, scene_id: str) -> Path | None:
    url = record.get("thumb") or record.get("url")
    if not url:
        return None
    extension = _extension(url, record.get("title", ""))
    destination = image_dir / f"{scene_id}{extension}"
    try:
        util.download_file(url, destination, min_bytes=4096)
    except Exception as exc:
        util.warn("assets", f"download failed {url[:70]}: {str(exc)[:90]}")
        return None
    if Image is not None:
        try:
            with Image.open(destination) as probe:
                probe.verify()
            with Image.open(destination) as probe:
                if probe.width < 320 or probe.height < 200:
                    util.warn("assets", f"{destination.name} too small ({probe.width}x{probe.height})")
                    destination.unlink(missing_ok=True)
                    return None
        except Exception as exc:
            util.warn("assets", f"{destination.name} is not a valid image: {exc}")
            destination.unlink(missing_ok=True)
            return None
    return destination


def _extension(url: str, title: str) -> str:
    tail = url.split("?")[0].rsplit(".", 1)[-1].lower()
    if tail in ("jpg", "jpeg", "png", "webp"):
        return "." + ("jpg" if tail == "jpeg" else tail)
    lowered = title.lower()
    if lowered.endswith(".png"):
        return ".png"
    return ".jpg"


def _clean_title(title: str) -> str:
    text = re.sub(r"\.[a-zA-Z]{3,4}$", "", title.replace("File:", "").replace("_", " "))
    return re.sub(r"\s+", " ", text).strip()


def _credit_line(record: dict) -> str:
    artist = re.sub(r"\s+", " ", record.get("artist", "")).strip()[:60]
    license_name = record.get("license", "") or "see source"
    return f"{artist + ' · ' if artist else ''}{license_name}".strip(" ·")


def thumbnail_source(script: dict, project: Path) -> Path | None:
    """Largest downloaded still — used as the base for the YouTube thumbnail."""
    image_dir = Path(project) / "assets" / "images"
    if not image_dir.exists():
        return None
    candidates = [p for p in image_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not candidates:
        return None
    if Image is None:
        return candidates[0]
    def area(path: Path) -> int:
        try:
            with Image.open(path) as probe:
                return probe.width * probe.height
        except Exception:
            return 0
    return max(candidates, key=area)
