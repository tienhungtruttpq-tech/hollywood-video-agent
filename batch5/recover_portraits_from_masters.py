#!/usr/bin/env python3
"""Recover production portrait crops from the already delivered legacy masters.

The repository intentionally keeps large temporary source-image downloads out
of Git.  These compact, reviewed portrait crops are retained under
``reference_portraits`` so a premium re-render can be reproduced even after a
workspace reset.  They are direct crops from the former masters, not AI faces
or generated imagery.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

ROOT = Path(__file__).resolve().parent
DELIVERABLES = ROOT.parent / "deliverables"
REFERENCE = ROOT / "reference_portraits"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def focus_time(index: int, era: str) -> float:
    """Return the mid-point of the legacy focused portrait scene."""
    comparison_start = 12 + index * 75 if index < 3 else 243 + (index - 3) * 75
    focus_start = comparison_start + 18 + (0 if era == "then" else 14)
    return focus_start + 5


def main() -> None:
    manifest = json.loads((ROOT / "episodes.json").read_text(encoding="utf-8"))
    for episode in manifest["episodes"]:
        master = DELIVERABLES / episode["filename"]
        if not master.exists():
            raise FileNotFoundError(f"Legacy master not found: {master}")
        for index, person in enumerate(episode["people"]):
            box = (584, 112, 1195, 605) if index % 2 == 0 else (85, 112, 696, 605)
            for era in ("then", "now"):
                scratch = ROOT / "work" / "portrait_recovery" / episode["id"] / f"{index:02d}_{era}_frame.jpg"
                scratch.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-ss", str(focus_time(index, era)), "-i", str(master), "-frames:v", "1", str(scratch)],
                    check=True,
                )
                with Image.open(scratch) as source:
                    x1, y1, x2, y2 = box
                    portrait = source.convert("RGB").crop((x1 + 8, y1 + 8, x2 - 8, y2 - 8))
                    target = REFERENCE / episode["id"] / f"{index:02d}_{era}.jpg"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    portrait.save(target, "JPEG", quality=95, subsampling=0, optimize=True)
    count = len(list(REFERENCE.rglob("*.jpg")))
    assert count == 60, f"Expected 60 portraits, found {count}"
    print(f"Recovered {count} compact portrait crops into {REFERENCE.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
