#!/usr/bin/env python3
"""Normalize the selected research images into deterministic production paths.

Network access in the render environment is deliberately not required. Images
were selected from Wikimedia-facing image-search results and the established
source records in the repository remain in episodes.json for attribution.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
SEARCH = REPO / "image-search"

# (episode id, visual position, era, file saved by the image-search tool)
# Each source was checked as a portrait of the named performer.  Most source
# records are the previously researched Commons records from the two existing
# episodes. A few older search thumbnails are intentionally used as an archival
# crop where the original file is no longer available in the workspace.
ASSIGNMENTS = [
    # 01 — Leading men
    ("01_leading_men", 0, "then", "tom-cruise-young-and-recent-portrait-wik-1.jpg"),
    ("01_leading_men", 0, "now", "tom-cruise-young-and-recent-portrait-wik-2.jpg"),
    ("01_leading_men", 1, "then", "leonardo-dicaprio-young-and-recent-portr-1.jpg"),
    ("01_leading_men", 1, "now", "leonardo-dicaprio-young-and-recent-portr-2.jpg"),
    ("01_leading_men", 2, "then", "tom-hanks-young-and-recent-portrait-wiki-1.jpg"),
    ("01_leading_men", 2, "now", "tom-hanks-young-and-recent-portrait-wiki-2.jpg"),
    ("01_leading_men", 3, "then", "brad-pitt-young-and-recent-portrait-wiki-1.jpg"),
    ("01_leading_men", 3, "now", "brad-pitt-young-and-recent-portrait-wiki-2.jpg"),
    ("01_leading_men", 4, "then", "denzel-washington-1990-solo-portrait-1.jpg"),
    ("01_leading_men", 4, "now", "denzel-washington-young-and-recent-portr-2.jpg"),
    ("01_leading_men", 5, "then", "george-clooney-young-and-recent-portrait-1.jpg"),
    ("01_leading_men", 5, "now", "george-clooney-young-and-recent-portrait-2.jpg"),

    # 02 — Leading ladies
    ("02_leading_ladies", 0, "then", "julia-roberts-young-and-recent-portrait--1.jpg"),
    ("02_leading_ladies", 0, "now", "julia-roberts-2024-solo-portrait-2.jpg"),
    ("02_leading_ladies", 1, "then", "angelina-jolie-early-and-recent-portrait-2.jpg"),
    ("02_leading_ladies", 1, "now", "angelina-jolie-2024-solo-portrait-1.jpg"),
    ("02_leading_ladies", 2, "then", "nicole-kidman-young-and-recent-portrait--1.jpg"),
    ("02_leading_ladies", 2, "now", "nicole-kidman-2024-solo-portrait-3.jpg"),
    ("02_leading_ladies", 3, "then", "kate-winslet-young-and-recent-portrait-w-2.jpg"),
    ("02_leading_ladies", 3, "now", "kate-winslet-young-and-recent-portrait-w-1.jpg"),
    ("02_leading_ladies", 4, "then", "charlize-theron-young-and-recent-portrai-2.jpg"),
    ("02_leading_ladies", 4, "now", "charlize-theron-young-and-recent-portrai-1.jpg"),
    ("02_leading_ladies", 5, "then", "anne-hathaway-early-and-recent-portrait--1.jpg"),
    ("02_leading_ladies", 5, "now", "anne-hathaway-early-and-recent-portrait--2.jpg"),

    # 03 — Action icons
    ("03_action_icons", 0, "then", "arnold-schwarzenegger-early-and-recent-p-2.jpg"),
    ("03_action_icons", 0, "now", "arnold-schwarzenegger-early-and-recent-p-1.jpg"),
    ("03_action_icons", 1, "then", "sylvester-stallone-1985-solo-portrait-1.jpg"),
    ("03_action_icons", 1, "now", "sylvester-stallone-early-and-recent-port-2.jpg"),
    ("03_action_icons", 2, "then", "harrison-ford-early-and-recent-portrait--1.jpg"),
    ("03_action_icons", 2, "now", "harrison-ford-early-and-recent-portrait--2.jpg"),
    ("03_action_icons", 3, "then", "samuel-l-jackson-actor-1990s-portrait-an-1.jpg"),
    ("03_action_icons", 3, "now", "samuel-l-jackson-actor-1990s-portrait-an-2.jpg"),
    ("03_action_icons", 4, "then", "hugh-jackman-2024-solo-portrait-2.jpg"),
    ("03_action_icons", 4, "now", "hugh-jackman-early-and-recent-portrait-w-1.jpg"),
    ("03_action_icons", 5, "then", "sigourney-weaver-early-and-recent-portra-1.jpg"),
    ("03_action_icons", 5, "now", "sigourney-weaver-early-and-recent-portra-2.jpg"),

    # 04 — Nineties icons
    ("04_nineties_icons", 0, "then", "winona-ryder-actress-1990-portrait-and-2-2.jpg"),
    ("04_nineties_icons", 0, "now", "winona-ryder-actress-1990-portrait-and-2-1.jpg"),
    ("04_nineties_icons", 1, "then", "meg-ryan-early-and-recent-portrait-wikim-1.jpg"),
    ("04_nineties_icons", 1, "now", "meg-ryan-early-and-recent-portrait-wikim-2.jpg"),
    ("04_nineties_icons", 2, "then", "johnny-depp-early-and-recent-portrait-wi-1.jpg"),
    ("04_nineties_icons", 2, "now", "johnny-depp-early-and-recent-portrait-wi-2.jpg"),
    ("04_nineties_icons", 3, "then", "will-smith-actor-1990s-portrait-and-2024-3.jpg"),
    ("04_nineties_icons", 3, "now", "will-smith-actor-1990s-portrait-and-2024-1.jpg"),
    ("04_nineties_icons", 4, "then", "halle-berry-1995-solo-portrait-1.jpg"),
    ("04_nineties_icons", 4, "now", "halle-berry-early-and-recent-portrait-wi-1.jpg"),
    ("04_nineties_icons", 5, "then", "uma-thurman-1994-solo-portrait-1.jpg"),
    ("04_nineties_icons", 5, "now", "uma-thurman-early-and-recent-portrait-wi-1.jpg"),

    # 05 — Comedy stars
    ("05_comedy_stars", 0, "then", "jim-carrey-early-and-recent-portrait-wik-2.jpg"),
    ("05_comedy_stars", 0, "now", "jim-carrey-early-and-recent-portrait-wik-1.jpg"),
    ("05_comedy_stars", 1, "then", "adam-sandler-early-and-recent-portrait-w-2.jpg"),
    ("05_comedy_stars", 1, "now", "adam-sandler-early-and-recent-portrait-w-1.jpg"),
    ("05_comedy_stars", 2, "then", "ben-stiller-2000-solo-portrait-1.jpg"),
    ("05_comedy_stars", 2, "now", "ben-stiller-early-and-recent-portrait-wi-2.jpg"),
    ("05_comedy_stars", 3, "then", "eddie-murphy-early-and-recent-portrait-w-2.jpg"),
    ("05_comedy_stars", 3, "now", "eddie-murphy-actor-1980s-portrait-and-20-3.jpg"),
    ("05_comedy_stars", 4, "then", "steve-carell-early-and-recent-portrait-w-1.jpg"),
    ("05_comedy_stars", 4, "now", "steve-carell-early-and-recent-portrait-w-2.jpg"),
    ("05_comedy_stars", 5, "then", "melissa-mccarthy-early-and-recent-portra-2.jpg"),
    ("05_comedy_stars", 5, "now", "melissa-mccarthy-early-and-recent-portra-1.jpg"),
]

# The search index includes copies/crops generated by Commons and Wikipedia.
# The links below point readers to the primary file page. If licensing changes,
# the source page is authoritative.
COMEDY_SOURCE_UPDATES = {
    "Jim Carrey": [
        {"title": "File:Jim Carrey 2008.jpg", "source": "https://commons.wikimedia.org/wiki/File:Jim_Carrey_2008.jpg", "year": 2008, "artist": "Ian Smith from London, England", "license": "CC BY-SA 2.0", "license_url": "https://creativecommons.org/licenses/by-sa/2.0/"},
        {"title": "File:Jim Carrey 2020.jpg", "source": "https://commons.wikimedia.org/wiki/File:Jim_Carrey_2020.jpg", "year": 2020, "artist": "SHOWTIME", "license": "CC BY 3.0", "license_url": "https://creativecommons.org/licenses/by/3.0/"},
    ],
    "Adam Sandler": [
        {"title": "File:Adam Sandler 2011 (Cropped).jpg", "source": "https://commons.wikimedia.org/wiki/File:Adam_Sandler_2011_(Cropped).jpg", "year": 2011, "artist": "Angela George", "license": "CC BY-SA 3.0", "license_url": "https://creativecommons.org/licenses/by-sa/3.0/"},
        {"title": "File:Adam Sandler 2025.jpg", "source": "https://commons.wikimedia.org/wiki/File:Adam_Sandler_2025.jpg", "year": 2025, "artist": "Raph_PH", "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/"},
    ],
    "Ben Stiller": [
        {"title": "File:BenStillerTropicThunderPendleton.jpg", "source": "https://commons.wikimedia.org/wiki/File:BenStillerTropicThunderPendleton.jpg", "year": 2008, "artist": "Dave Gatley, U.S. Marine Corps", "license": "Public domain", "license_url": "https://commons.wikimedia.org/wiki/File:BenStillerTropicThunderPendleton.jpg"},
        {"title": "File:Ben Stiller at the 2024 Toronto International Film Festival (cropped).jpg", "source": "https://commons.wikimedia.org/wiki/File:Ben_Stiller_at_the_2024_Toronto_International_Film_Festival_(cropped).jpg", "year": 2024, "artist": "Frank Sun", "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"},
    ],
    "Eddie Murphy": [
        {"title": "File:Eddie Murphy Tribeca Shankbone 2010 NYC (2).jpg", "source": "https://commons.wikimedia.org/wiki/File:Eddie_Murphy_Tribeca_Shankbone_2010_NYC_(2).jpg", "year": 2010, "artist": "David Shankbone", "license": "CC BY 3.0", "license_url": "https://creativecommons.org/licenses/by/3.0/"},
        {"title": "File:Casey Patterson and Eddie Murphy.jpg", "source": "https://commons.wikimedia.org/wiki/File:Casey_Patterson_and_Eddie_Murphy.jpg", "year": 2012, "artist": "Viacom / New 38th Floor Productions Inc.", "license": "CC BY-SA 3.0", "license_url": "https://creativecommons.org/licenses/by-sa/3.0/"},
    ],
    "Steve Carell": [
        {"title": "File:Steve Carell 2, 2013.jpg", "source": "https://commons.wikimedia.org/wiki/File:Steve_Carell_2,_2013.jpg", "year": 2013, "artist": "Eva Rinaldi", "license": "CC BY-SA 2.0", "license_url": "https://creativecommons.org/licenses/by-sa/2.0/"},
        {"title": "File:Steve Carell - The 40-Year-Old-Virgin.jpg", "source": "https://commons.wikimedia.org/wiki/File:Steve_Carell_-_The_40-Year-Old-Virgin.jpg", "year": 2025, "artist": "Kevin Paul", "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/"},
    ],
    "Melissa McCarthy": [
        {"title": "File:Melissa McCarthy 2012 (Straighten Crop).jpg", "source": "https://commons.wikimedia.org/wiki/File:Melissa_McCarthy_2012_(Straighten_Crop).jpg", "year": 2012, "artist": "MingleMediaTV", "license": "CC BY-SA 2.0", "license_url": "https://creativecommons.org/licenses/by-sa/2.0/"},
        {"title": "File:Melissa McCarthy in 2018 (cropped).jpg", "source": "https://commons.wikimedia.org/wiki/File:Melissa_McCarthy_in_2018_(cropped).jpg", "year": 2018, "artist": "Greg2600", "license": "CC BY-SA 2.0", "license_url": "https://creativecommons.org/licenses/by-sa/2.0/"},
    ],
}


def load_manifest() -> dict:
    return json.loads((ROOT / "episodes.json").read_text(encoding="utf-8"))


def save_manifest(data: dict) -> None:
    (ROOT / "episodes.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize(source: Path, target: Path) -> tuple[int, int]:
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        # Preserve enough detail for the framed 720p composition without
        # retaining a large raw archive in the repository workspace.
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, "JPEG", quality=92, optimize=True, progressive=True)
        return image.size


def main() -> None:
    manifest = load_manifest()
    by_id = {ep["id"]: ep for ep in manifest["episodes"]}
    records = []
    missing = []

    for episode_id, person_index, era, source_name in ASSIGNMENTS:
        src = SEARCH / source_name
        target = ROOT / by_id[episode_id]["people"][person_index]["assets"][era]
        if not src.exists():
            missing.append(str(src))
            continue
        size = normalize(src, target)
        records.append({
            "episode": episode_id,
            "person": by_id[episode_id]["people"][person_index]["name"],
            "era": era,
            "input": str(src.relative_to(REPO)),
            "output": str(target.relative_to(ROOT)),
            "normalized_size": list(size),
        })

    if missing:
        raise SystemExit("Missing input image(s):\n" + "\n".join(missing))

    # Insert the primary Commons records for the episode that was researched
    # independently of the two original manifests.
    comedy = by_id["05_comedy_stars"]
    for person in comedy["people"]:
        then, now = COMEDY_SOURCE_UPDATES[person["name"]]
        person["then"] = then
        person["now"] = now
        person["years"] = [then["year"], now["year"]]
        person["delta"] = now["year"] - then["year"]

    save_manifest(manifest)
    (ROOT / "manifests" / "asset_import.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Normalized {len(records)} portraits into batch5/assets/photos/.")


if __name__ == "__main__":
    main()
