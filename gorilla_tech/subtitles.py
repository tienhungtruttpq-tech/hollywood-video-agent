"""
Stage 5 — subtitles.

Word boundaries from the TTS step become broadcast-style cues: max two lines,
~42 characters per line, never splitting a number or a unit. Two artefacts are
produced: `output/<name>.srt` (for YouTube) and a styled `.ass` burned into the
video with ffmpeg/libass.
"""

from __future__ import annotations

import re
from pathlib import Path

import config
import util

MAX_CHARS_PER_LINE = 42
MAX_LINES = 2
MIN_CUE = 0.9
MAX_CUE = 6.5
GAP = 0.06

_BIND = re.compile(r"(\d[\d.,]*)\s*(km/h|km|m|s|kg|t|mm|USD|\$|%|:1|rpm|ft|lb)", re.I)


def _group_words(words: list[dict]) -> list[dict]:
    cues: list[dict] = []
    current: list[dict] = []
    current_text = ""

    def flush() -> None:
        nonlocal current, current_text
        if current:
            cues.append({
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "text": current_text.strip(),
            })
        current, current_text = [], ""

    for word in words:
        token = word["text"].strip()
        if not token:
            continue
        candidate = f"{current_text} {token}".strip()
        too_long = len(candidate) > MAX_CHARS_PER_LINE * MAX_LINES
        long_enough = len(current_text) >= MAX_CHARS_PER_LINE
        ends_sentence = bool(re.search(r"[.!?…:;]$", token))
        duration_ok = word["end"] - (current[0]["start"] if current else word["start"]) < MAX_CUE
        if current and (too_long or (long_enough and (ends_sentence or not duration_ok))):
            flush()
            candidate = token
        current.append(word)
        current_text = candidate

    flush()

    # tidy: minimum length, no overlap, balanced two-line splits
    cleaned: list[dict] = []
    for cue in cues:
        cue["end"] = max(cue["end"], cue["start"] + MIN_CUE)
        if cleaned and cue["start"] < cleaned[-1]["end"] + GAP:
            cleaned[-1]["end"] = max(cleaned[-1]["start"] + MIN_CUE, cue["start"] - GAP)
        cleaned.append(cue)
    return [c for c in cleaned if c["text"]]


def build_cues(timing: dict) -> list[dict]:
    cues: list[dict] = []
    for scene in timing.get("scenes", []):
        words = scene.get("words") or []
        if not words:
            continue
        cues.extend(_group_words(words))
    return cues


def wrap_two_lines(text: str) -> str:
    """Break a cue into at most two balanced lines, never inside a number+unit."""
    protected = _BIND.sub(lambda m: m.group(0).replace(" ", "\u00a0"), text)
    words = protected.split()
    if not words:
        return ""
    if len(protected) <= MAX_CHARS_PER_LINE:
        return protected.replace("\u00a0", " ")
    best_split, best_diff = 0, 10 ** 6
    length = 0
    for index, word in enumerate(words):
        length += len(word) + 1
        diff = abs(length - (len(protected) - length))
        if diff < best_diff:
            best_diff, best_split = diff, index + 1
    first = " ".join(words[:best_split]).replace("\u00a0", " ")
    second = " ".join(words[best_split:]).replace("\u00a0", " ")
    if second and len(first) > MAX_CHARS_PER_LINE + 8:
        return first[:MAX_CHARS_PER_LINE + 8] + "\n" + second
    return (first + ("\n" + second if second else "")).strip()


def to_srt(cues: list[dict]) -> str:
    lines = []
    for index, cue in enumerate(cues, start=1):
        lines.append(str(index))
        lines.append(f"{util.srt_time(cue['start'])} --> {util.srt_time(max(cue['end'], cue['start'] + MIN_CUE))}")
        lines.append(wrap_two_lines(cue["text"]))
        lines.append("")
    return "\n".join(lines)


def _ass_color(rgb: tuple[int, int, int], alpha: int = 0) -> str:
    return f"&H{alpha:02X}{rgb[2]:02X}{rgb[1]:02X}{rgb[0]:02X}"


def to_ass(cues: list[dict], size: tuple[int, int], font_name: str = "DejaVu Sans") -> str:
    width, height = size
    play_res_y = 1080
    scale = play_res_y / height
    font_size = int(52 * scale * height / 1080) if height != 1080 else 52
    font_size = max(34, min(64, int(height * 0.046)))
    margin_v = int(height * 0.075)
    outline = max(2, int(height * 0.0032))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narration,{font_name},{font_size},{_ass_color((255, 255, 255))},{_ass_color((255, 210, 120))},{_ass_color((8, 10, 14))},{_ass_color((0, 0, 0), 128)},-1,0,0,0,100,100,0.2,0,1,{outline},1,2,{int(width * 0.06)},{int(width * 0.06)},{margin_v},1
Style: Chapter,{font_name},{int(font_size * 0.72)},{_ass_color(config.PALETTE['accent_alt'])},{_ass_color((255, 255, 255))},{_ass_color((8, 10, 14))},{_ass_color((0, 0, 0), 150)},-1,0,0,0,100,100,1.4,0,1,{outline},1,8,{int(width * 0.05)},{int(width * 0.05)},{int(height * 0.10)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for cue in cues:
        text = wrap_two_lines(cue["text"]).replace("\n", "\\N")
        events.append(
            f"Dialogue: 0,{_ass_time(cue['start'])},{_ass_time(max(cue['end'], cue['start'] + MIN_CUE))},"
            f"Narration,,0,0,0,,{text}"
        )
    return header + "\n".join(events) + "\n"


def _ass_time(seconds: float) -> str:
    centiseconds = int(round(max(0.0, seconds) * 100))
    h, rest = divmod(centiseconds, 360_000)
    m, rest = divmod(rest, 6_000)
    s, cs = divmod(rest, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def write_subtitles(cues: list[dict], project: Path, name: str,
                    size: tuple[int, int] | None = None) -> dict:
    output_dir = Path(project) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    srt_path = output_dir / f"{name}.srt"
    ass_path = output_dir / f"{name}.ass"
    util.write_text(srt_path, to_srt(cues))
    util.write_text(ass_path, to_ass(cues, size or config.video_size()))
    util.ok("subs", f"{len(cues)} cues -> {srt_path.name}, {ass_path.name}")
    return {"srt": str(srt_path), "ass": str(ass_path), "cues": len(cues)}
