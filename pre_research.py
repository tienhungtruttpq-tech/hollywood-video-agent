#!/usr/bin/env python3
"""
Pre-research script v2: Uses Wikimedia THUMBNAILS (800px) instead of 
full-resolution originals, with longer delays to avoid rate limits.
"""

import json, time, re, urllib.request, urllib.parse, sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent / "new_project"
PHOTOS = PROJECT / "assets" / "photos"
PHOTOS.mkdir(parents=True, exist_ok=True)

DELAY = 5  # seconds between Wikimedia requests

ACTORS = [
    {"name": "Tom Hanks",          "then_query": "Tom Hanks 1989",               "now_query": "Tom Hanks 2023"},
    {"name": "Brad Pitt",          "then_query": "Brad Pitt Cannes",             "now_query": "Brad Pitt 2024"},
    {"name": "Leonardo DiCaprio",  "then_query": "Leonardo DiCaprio 2002",       "now_query": "Leonardo DiCaprio 2016"},
    {"name": "Keanu Reeves",       "then_query": "Keanu Reeves 2005 portrait",   "now_query": "Keanu Reeves 2019"},
    {"name": "Denzel Washington",  "then_query": "Denzel Washington 1990",       "now_query": "Denzel Washington 2018"},
    {"name": "Robert Downey Jr.",  "then_query": "Robert Downey Jr 1990",        "now_query": "Robert Downey Jr 2019"},
    {"name": "Morgan Freeman",     "then_query": "Morgan Freeman portrait",      "now_query": "Morgan Freeman 2018"},
    {"name": "Harrison Ford",      "then_query": "Harrison Ford 2009",           "now_query": "Harrison Ford Blade Runner"},
    {"name": "Samuel L. Jackson",  "then_query": "Samuel L Jackson 2008",        "now_query": "Samuel L Jackson 2019"},
    {"name": "Tom Cruise",         "then_query": "Tom Cruise Alan Light",        "now_query": "Tom Cruise 2022"},
]

HEADERS = {"User-Agent": "HollywoodAgentBot/1.0 (archival photo documentary; thumbnails only)"}


def search_wikimedia(query, limit=5):
    """Search Wikimedia Commons — request 800px thumbnails."""
    params = urllib.parse.urlencode({
        "action": "query", "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": limit, "gsrnamespace": 6,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "iiurlwidth": 800,  # Request 800px thumbnail
        "iiextmetadatafilter": "LicenseShortName|Artist",
    })
    url = f"https://commons.wikimedia.org/w/api.php?{params}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    results = []
    for page in data.get("query", {}).get("pages", {}).values():
        ii = (page.get("imageinfo") or [{}])[0]
        ext = ii.get("extmetadata", {})
        w = ii.get("width", 0) or 0
        h = ii.get("height", 0) or 0
        if w < 300 or h < 300:
            continue
        thumb = ii.get("thumburl", ii.get("url", ""))
        results.append({
            "title": page.get("title", ""),
            "url": ii.get("url", ""),
            "thumb": thumb,  # 800px thumbnail
            "width": w, "height": h,
            "license": ext.get("LicenseShortName", {}).get("value", ""),
            "artist": re.sub(r"<[^>]+>", "", ext.get("Artist", {}).get("value", ""))[:80],
        })
    return results


def download(url, path):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    path.write_bytes(data)
    return len(data)


def pick_best(results, actor_name):
    name_parts = actor_name.lower().replace(".", "").split()
    scored = []
    for r in results:
        title = r["title"].lower()
        score = sum(1 for p in name_parts if p in title) * 10
        score += min(r["width"], r["height"]) / 200
        if "portrait" in title or "cropped" in title:
            score += 5
        if r["license"] and ("cc" in r["license"].lower() or "public" in r["license"].lower()):
            score += 3
        scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


def main():
    manifest = []
    
    for i, actor in enumerate(ACTORS):
        name = actor["name"]
        print(f"\n[{i+1}/{len(ACTORS)}] {name}", flush=True)
        
        # Search THEN
        print(f"  Search: {actor['then_query']}...", flush=True)
        time.sleep(DELAY)
        try:
            then_results = search_wikimedia(actor["then_query"])
            print(f"    Found {len(then_results)} results", flush=True)
        except Exception as e:
            print(f"    FAIL: {e}", flush=True)
            then_results = []
        
        # Search NOW
        print(f"  Search: {actor['now_query']}...", flush=True)
        time.sleep(DELAY)
        try:
            now_results = search_wikimedia(actor["now_query"])
            print(f"    Found {len(now_results)} results", flush=True)
        except Exception as e:
            print(f"    FAIL: {e}", flush=True)
            now_results = []
        
        then_pick = pick_best(then_results, name)
        now_pick = pick_best(now_results, name)
        
        if not then_pick:
            print(f"  SKIP: No THEN photo", flush=True)
            continue
        if not now_pick:
            print(f"  SKIP: No NOW photo", flush=True)
            continue
        
        safe = name.lower().replace(" ", "_").replace(".", "")
        # Extract extension from URL path (strip query string first)
        def get_ext(url):
            path = url.split("?")[0]
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else "jpg"
            return ext if ext in ("jpg", "jpeg", "png", "webp") else "jpg"
        then_path = PHOTOS / f"{safe}_then.{get_ext(then_pick['thumb'])}"
        now_path = PHOTOS / f"{safe}_now.{get_ext(now_pick['thumb'])}"
        
        # Download THUMBNAILS (small, fast, Wikimedia-friendly)
        print(f"  Download THEN thumbnail...", flush=True)
        time.sleep(DELAY)
        try:
            sz = download(then_pick["thumb"], then_path)
            print(f"    {sz:,} bytes -> {then_path.name}", flush=True)
        except Exception as e:
            print(f"    FAIL: {e}", flush=True)
            continue
            
        print(f"  Download NOW thumbnail...", flush=True)
        time.sleep(DELAY)
        try:
            sz = download(now_pick["thumb"], now_path)
            print(f"    {sz:,} bytes -> {now_path.name}", flush=True)
        except Exception as e:
            print(f"    FAIL: {e}", flush=True)
            continue
        
        manifest.append({
            "name": name,
            "then_photo": then_path.name,
            "now_photo": now_path.name,
            "then_source": then_pick["url"],
            "now_source": now_pick["url"],
            "then_license": then_pick["license"],
            "now_license": now_pick["license"],
            "then_artist": then_pick["artist"],
            "now_artist": now_pick["artist"],
        })
        print(f"  OK!", flush=True)
    
    out = PROJECT / "actors.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\n{'='*50}", flush=True)
    print(f"  Done! {len(manifest)} actors ready", flush=True)
    print(f"  {out}", flush=True)
    print(f"{'='*50}", flush=True)


if __name__ == "__main__":
    main()
