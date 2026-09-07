"""
Stage 8 — packaging: thumbnail, YouTube metadata, credits, subtitle export.

Produces, inside `projects/<slug>/output/`:
  <slug>.mp4         final video
  <slug>.srt         subtitles (upload next to the video)
  <slug>.ass         styled subtitles used for the burn-in
  thumbnail.jpg      1280x720 YouTube thumbnail
  package.json       title / description / tags / hashtags / chapters
  CREDITS.md         every photo licence + attribution, ready to paste in the description
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import assets as assets_mod
import config
import graphics as g
import util

P = config.PALETTE
THUMB_SIZE = (1280, 720)


# ─────────────────────────────────────────────────────────────
# Thumbnail
# ─────────────────────────────────────────────────────────────

def build_thumbnail(script: dict, project: Path, destination: Path | None = None) -> Path:
    meta = script.get("meta", {})
    destination = Path(destination or (Path(project) / "output" / "thumbnail.jpg"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    width, height = THUMB_SIZE

    source = assets_mod.thumbnail_source(script, project)
    if source:
        try:
            base = Image.open(source).convert("RGB")
            base = g.cover(g.grade_photo(base, cool=0.86, contrast=1.2, saturation=0.7), width, height)
        except Exception as exc:
            util.warn("thumb", f"{source.name} unusable ({exc})")
            base = None
    else:
        base = None
    if base is None:
        base = g.dark_base(width, height, seed=9, terrain=0.45, tint=(26, 34, 30)).convert("RGB")

    canvas = base.convert("RGBA")
    # left-to-right dark scrim so the text stays readable
    scrim = Image.new("L", (width, height), 0)
    gradient = np.linspace(215, 40, width, dtype=np.uint8)[None, :].repeat(height, axis=0)
    scrim = Image.fromarray(gradient, "L")
    canvas.putalpha(255)
    darkened = Image.composite(Image.new("RGBA", (width, height), (4, 6, 10, 255)),
                               canvas, scrim).convert("RGBA")
    d = ImageDraw.Draw(darkened, "RGBA")

    headline = str(meta.get("thumb_text") or _thumb_words(meta.get("title", meta.get("topic", ""))))
    f = g.fit_font_size(d, headline.upper(), int(width * 0.56), 104, 44)
    lines = g.wrap(d, headline.upper(), f, int(width * 0.56))
    y = int(height * 0.30) - (len(lines) - 1) * 46
    for line in lines[:3]:
        d.text((58 + 5, y + 5), line, font=f, fill=(0, 0, 0, 225))
        d.text((58, y), line, font=f, fill=(*P["text"], 255))
        y += int(g.text_size(d, line, f)[1] * 1.08)

    kicker = str(meta.get("kicker") or meta.get("topic", ""))[:34].upper()
    if kicker:
        g.kicker(d, (58, int(height * 0.14)), kicker, color=P["accent"], size=26, letter_gap=4)

    tag = str(meta.get("thumb_tag") or "")[:22].upper()
    if tag:
        f_tag = g.font(30, "mono")
        tw = g.text_size(d, tag, f_tag)[0]
        box = (width - tw - 76, 40, width - 36, 92)
        d.rounded_rectangle(box, radius=8, fill=(*P["danger"], 235))
        d.text((box[0] + 20, box[1] + 9), tag, font=f_tag, fill=(255, 255, 255, 255))

    brand = str(meta.get("brand", "GORIZON TECH")).upper()
    f_brand = g.font(26, "mono")
    d.text((58, height - 66), brand, font=f_brand, fill=(*P["accent_alt"], 240))
    d.rectangle([58, height - 34, 58 + 210, height - 28], fill=(*P["accent"], 255))

    out = darkened.convert("RGB")
    out.save(destination, quality=92)
    util.ok("package", f"thumbnail -> {destination.name} ({util.human_size(destination.stat().st_size)})")
    return destination


def _thumb_words(title: str) -> str:
    """Pick <= 5 impactful words from the title for the thumbnail."""
    cleaned = re.sub(r"[^\w\s…\-]", " ", title or "")
    words = [w for w in cleaned.split() if len(w) > 1]
    if not words:
        return "ANÁLISIS"
    priority = [w for w in words if w.isupper() or len(w) > 6]
    chosen = (priority or words)[:5]
    return " ".join(chosen)


# ─────────────────────────────────────────────────────────────
# Metadata
# ─────────────────────────────────────────────────────────────

def chapters_from_timeline(timing: dict) -> list[dict]:
    chapters = []
    for scene in timing.get("scenes", []):
        label = str(scene.get("chapter") or "").strip()
        if not label:
            continue
        start = float(scene.get("scene_start", 0.0))
        if chapters and start - chapters[-1]["start"] < 25:
            continue
        chapters.append({"start": round(start, 1), "title": label[:60],
                         "timestamp": _yt_timestamp(start)})
    return chapters


def _yt_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:d}:{secs:02d}"


def build_description(script: dict, timing: dict, credits: str, chapters: list[dict],
                      lang: str = "es") -> str:
    meta = script.get("meta", {})
    parts = [str(meta.get("description") or meta.get("logline") or "").strip()]
    if chapters:
        parts.append("\n".join(["", "CAPÍTULOS" if lang == "es" else "CHAPTERS",
                                *[f"{c['timestamp']}  {c['title']}" for c in chapters]]))
    hashtags = [h if h.startswith("#") else f"#{h}" for h in (meta.get("hashtags") or [])][:15]
    if hashtags:
        parts.append("\nHashtags\n" + " ".join(hashtags))
    tags = [str(t).strip() for t in (meta.get("tags") or []) if str(t).strip()][:35]
    if tags:
        parts.append("\n" + ("Tags para YouTube" if lang == "es" else "YouTube tags") + "\n" +
                     ", ".join(tags))
    if credits:
        parts.append("\n" + ("Créditos de imágenes" if lang == "es" else "Image credits") + "\n" + credits)
    parts.append(_boilerplate(meta.get("brand", ""), lang))
    return "\n".join(part for part in parts if part).strip()


def _boilerplate(brand: str, lang: str) -> str:
    if lang == "es":
        return (f"\nBienvenido a {brand or 'este canal'}: análisis de tecnología militar con "
                f"datos, mapa y cronología. Reconstrucción basada en fuentes abiertas.\n"
                f"Suscríbete para el próximo caso.")
    if lang == "vi":
        return (f"\nChào mừng đến với {brand or 'kênh'}: phân tích công nghệ quân sự bằng số liệu, "
                f"bản đồ và dòng thời gian. Dựng lại từ nguồn mở.\nĐăng ký để xem tập tiếp theo.")
    return (f"\nWelcome to {brand or 'this channel'}: military technology analysis with data, maps "
            f"and timelines. Reconstruction based on open sources.\nSubscribe for the next case.")


def build_credits(script: dict, project: Path) -> str:
    records = (util.read_json(Path(project) / "assets" / "images.json", {}) or {}).get("images", [])
    lines = []
    used = 0
    for record in records:
        if record.get("origin") == "none":
            continue
        used += 1
        origin = ("AI-generated illustration" if record.get("origin") == "ai-generated"
                  else f"{record.get('artist') or 'unknown author'} — {record.get('license') or 'see source'}")
        lines.append(f"- {record.get('title') or record.get('query')} ({origin}) "
                     f"{record.get('page') or record.get('source') or ''}".strip())
    if not used:
        lines.append("- All visuals in this video are procedurally generated (no third-party assets).")
    lines.append(f"- Music: synthesised in-pipeline (gorilla_tech/music.py), no third-party recording.")
    lines.append(f"- Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
                 f"by gorilla_tech agent.")
    text = "\n".join(lines)
    util.write_text(Path(project) / "output" / "CREDITS.md",
                    "# Image & audio credits\n\n" + text + "\n")
    return text


def build_package(script: dict, timing: dict, project: Path, video_path: Path,
                  subtitle_paths: dict, thumb_path: Path | None = None) -> dict:
    meta = script.get("meta", {})
    lang = meta.get("lang", config.DEFAULT_LANG)
    chapters = chapters_from_timeline(timing)
    credits = build_credits(script, project)
    description = build_description(script, timing, credits, chapters, lang)
    title = str(meta.get("title") or meta.get("topic") or "Untitled")[:100]

    package = {
        "title": title,
        "title_options": meta.get("title_options", []),
        "description": description,
        "tags": (meta.get("tags") or [])[:35],
        "hashtags": meta.get("hashtags", []),
        "categoryId": "28",  # Science & Technology
        "privacyStatus": "private",
        "language": lang,
        "duration_sec": round(float(timing.get("total_seconds", 0.0)), 2),
        "chapters": chapters,
        "files": {
            "video": str(video_path),
            "thumbnail": str(thumb_path) if thumb_path else "",
            "srt": subtitle_paths.get("srt", ""),
            "ass": subtitle_paths.get("ass", ""),
            "credits": str(Path(project) / "output" / "CREDITS.md"),
        },
        "stats": script.get("stats", {}),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": meta.get("generator", "llm"),
    }
    util.write_json(Path(project) / "output" / "package.json", package)
    util.write_text(Path(project) / "output" / "description.txt", description)
    util.ok("package", f"title: {title}")
    util.log("package", f"{len(package['tags'])} tags · {len(chapters)} chapters · "
                        f"{util.clock(package['duration_sec'])}")
    return package
