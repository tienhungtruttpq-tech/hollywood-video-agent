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
    ("01_leading_men", 0, "then", "tom-cruise-1989-2-jpg-tom-cruise-2428-sq-2.jpg"),
    ("01_leading_men", 0, "now", "tom-cruise-1989-2-jpg-tom-cruise-2428-sq-4.jpg"),
    ("01_leading_men", 1, "then", "leonardo-dicaprio-jpeg-leonardo-dicaprio-5.jpg"),
    ("01_leading_men", 1, "now", "leonardo-dicaprio-jpeg-leonardo-dicaprio-1.jpg"),
    ("01_leading_men", 2, "then", "1989-tom-hanks-cropped-jpg-tom-hanks-int-2.jpg"),
    ("01_leading_men", 2, "now", "1989-tom-hanks-cropped-jpg-tom-hanks-int-1.jpg"),
    ("01_leading_men", 3, "then", "brad-pitt-at-incirlik2-jpg-brad-pitt-698-4.jpg"),
    ("01_leading_men", 3, "now", "brad-pitt-at-incirlik2-jpg-brad-pitt-698-1.jpg"),
    ("01_leading_men", 4, "then", "file-denzel-washington-2106641898-croppe-1.jpg"),
    ("01_leading_men", 4, "now", "site-commons-wikimedia-org-wiki-file-den-3.jpg"),
    ("01_leading_men", 5, "then", "file-george-clooney-1995-jpg-wikimedia-c-1.jpg"),
    ("01_leading_men", 5, "now", "george-clooney-1995-jpg-george-clooney-j-1.jpg"),

    # 02 — Leading ladies
    ("02_leading_ladies", 0, "then", "julia-roberts-1990-2025-portrait-wikimed-1.jpg"),
    ("02_leading_ladies", 0, "now", "julia-roberts-1990-2025-portrait-wikimed-2.jpg"),
    ("02_leading_ladies", 1, "then", "angelina-jolie-2004-2025-portrait-wikime-3.jpg"),
    ("02_leading_ladies", 1, "now", "angelina-jolie-2004-2025-portrait-wikime-1.jpg"),
    ("02_leading_ladies", 2, "then", "nicole-kidman-2001-2025-portrait-wikimed-4.jpg"),
    ("02_leading_ladies", 2, "now", "nicole-kidman-2001-2025-portrait-wikimed-1.jpg"),
    ("02_leading_ladies", 3, "then", "kate-winslet-2006-2025-portrait-wikimedi-4.jpg"),
    ("02_leading_ladies", 3, "now", "kate-winslet-2006-2025-portrait-wikimedi-1.jpg"),
    ("02_leading_ladies", 4, "then", "charlize-theron-2005-2026-portrait-wikim-1.jpg"),
    ("02_leading_ladies", 4, "now", "charlize-theron-2005-2026-portrait-wikim-1.jpg"),
    ("02_leading_ladies", 5, "then", "anne-hathaway-2008-2026-portrait-wikimed-3.jpg"),
    ("02_leading_ladies", 5, "now", "anne-hathaway-2008-2026-portrait-wikimed-2.jpg"),

    # 03 — Action icons
    ("03_action_icons", 0, "then", "arnold-schwarzenegger-1984-2025-portrait-3.jpg"),
    ("03_action_icons", 0, "now", "arnold-schwarzenegger-1984-2025-portrait-1.jpg"),
    ("03_action_icons", 1, "then", "sylvester-stallone-1985-2025-portrait-wi-1.jpg"),
    ("03_action_icons", 1, "now", "sylvester-stallone-2024-2025-portrait-wi-1.jpg"),
    ("03_action_icons", 2, "then", "harrison-ford-2007-2025-portrait-wikimed-1.jpg"),
    ("03_action_icons", 2, "now", "harrison-ford-2007-2025-portrait-wikimed-2.jpg"),
    ("03_action_icons", 3, "then", "samuel-l-jackson-2008-2024-portrait-wiki-4.jpg"),
    ("03_action_icons", 3, "now", "samuel-l-jackson-2008-2024-portrait-wiki-2.jpg"),
    ("03_action_icons", 4, "then", "hugh-jackman-2003-2025-portrait-wikimedi-1.jpg"),
    ("03_action_icons", 4, "now", "hugh-jackman-2003-2025-portrait-wikimedi-4.jpg"),
    ("03_action_icons", 5, "then", "sigourney-weaver-1989-2025-portrait-wiki-1.jpg"),
    ("03_action_icons", 5, "now", "sigourney-weaver-1989-2025-portrait-wiki-4.jpg"),

    # 04 — Nineties icons
    ("04_nineties_icons", 0, "then", "winona-ryder-2008-2024-portrait-wikimedi-1.jpg"),
    ("04_nineties_icons", 0, "now", "winona-ryder-2008-2024-portrait-wikimedi-2.jpg"),
    ("04_nineties_icons", 1, "then", "meg-ryan-2006-2025-portrait-wikimedia-co-4.jpg"),
    ("04_nineties_icons", 1, "now", "meg-ryan-2006-2025-portrait-wikimedia-co-1.jpg"),
    ("04_nineties_icons", 2, "then", "johnny-depp-1992-2023-portrait-wikimedia-1.jpg"),
    ("04_nineties_icons", 2, "now", "johnny-depp-1992-2023-portrait-wikimedia-4.jpg"),
    ("04_nineties_icons", 3, "then", "will-smith-1993-2025-portrait-wikimedia--4.jpg"),
    ("04_nineties_icons", 3, "now", "will-smith-1993-2025-portrait-wikimedia--2.jpg"),
    ("04_nineties_icons", 4, "then", "halle-berry-signs-autographs-for-us-sold-1.jpg"),
    ("04_nineties_icons", 4, "now", "halle-berry-signs-autographs-for-us-sold-3.jpg"),
    ("04_nineties_icons", 5, "then", "1994-uma-thurman-03-wikimedia-commons-1.jpg"),
    ("04_nineties_icons", 5, "now", "actress-uma-thurman-at-oh-canada-press-c-1.jpg"),

    # 05 — Comedy stars. These are direct Commons / Wikipedia-thumbnail source
    # images; source file titles are recorded below in COMEDY_SOURCE_UPDATES.
    ("05_comedy_stars", 0, "then", "jim-carrey-2010-cropped-wikimedia-common-4.jpg"),
    ("05_comedy_stars", 0, "now", "jim-carrey-2024-2025-portrait-wikimedia--3.jpg"),
    ("05_comedy_stars", 1, "then", "site-commons-wikimedia-org-wiki-file-ada-3.jpg"),
    ("05_comedy_stars", 1, "now", "site-commons-wikimedia-org-wiki-file-ada-5.jpg"),
    ("05_comedy_stars", 2, "then", "ben-stiller-early-recent-portrait-wikime-1.jpg"),
    ("05_comedy_stars", 2, "now", "ben-stiller-at-the-2024-toronto-internat-3.jpg"),
    ("05_comedy_stars", 3, "then", "eddie-murphy-2024-2025-portrait-wikimedi-1.jpg"),
    ("05_comedy_stars", 3, "now", "site-commons-wikimedia-org-wiki-file-edd-2.jpg"),
    ("05_comedy_stars", 4, "then", "site-commons-wikimedia-org-wiki-file-ste-5.jpg"),
    ("05_comedy_stars", 4, "now", "site-commons-wikimedia-org-wiki-file-ste-1.jpg"),
    ("05_comedy_stars", 5, "then", "melissa-mccarthy-2024-2025-portrait-wiki-1.jpg"),
    ("05_comedy_stars", 5, "now", "site-commons-wikimedia-org-wiki-file-mel-4.jpg"),
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
