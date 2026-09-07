#!/usr/bin/env python3
"""
fetch_photos_wikimedia.py — Tải ảnh THEN/NOW từ Wikimedia Commons (CC/PD) cho cả tập.
Chạy trên máy có mạng tới commons.wikimedia.org. Ghi assets/photos/licenses.json.

Usage:
  python fetch_photos_wikimedia.py            # tất cả 50 người
  python fetch_photos_wikimedia.py --only 1-8 # pilot
"""
import argparse, json, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "GoldenHourEpisodeBot/1.0 (educational documentary; contact: your@email)"}
OUT = os.path.join(HERE, "assets", "photos")
ALLOWED = ("CC BY", "CC0", "Public domain", "PD", "CC BY-SA")

def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def search(query, limit=8):
    d = api({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}", "gsrlimit": limit, "gsrnamespace": 6,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|Artist|DateTimeOriginal",
    })
    pages = d.get("query", {}).get("pages", {})
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {}) or {}
        lic = md.get("LicenseShortName", {}).get("value", "")
        if not any(a.lower() in lic.lower() for a in ALLOWED):
            continue
        w, h = ii.get("width", 0), ii.get("height", 0)
        if w < 500 or h < 500:
            continue
        artist = re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", ""))[:120]
        out.append({
            "title": p.get("title", ""), "url": ii.get("url"),
            "thumb": ii.get("thumburl") or ii.get("url"),
            "license": lic, "artist": artist,
            "date": md.get("DateTimeOriginal", {}).get("value", "")[:60],
            "w": w, "h": h,
        })
    return out

def download(url, path):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
        f.write(r.read())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=str, default=None, help="vd: 1-8 hoặc 3,7,9")
    args = ap.parse_args()
    ep = json.load(open(os.path.join(HERE, "episode.json"), encoding="utf-8"))
    stars = ep["stars"]
    if args.only:
        m = re.match(r"(\d+)-(\d+)", args.only)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            stars = [s for s in stars if lo <= s["no"] <= hi]
        else:
            keep = {int(x) for x in args.only.split(",")}
            stars = [s for s in stars if s["no"] in keep]
    os.makedirs(OUT, exist_ok=True)
    licenses = {}
    if os.path.exists(os.path.join(OUT, "licenses.json")):
        licenses = json.load(open(os.path.join(OUT, "licenses.json"), encoding="utf-8"))
    for s in stars:
        for phase in ("then", "now"):
            q = s["photos"][f"{phase}_query"]
            dest = os.path.join(OUT, f"{s['slug']}_{phase}.jpg")
            if os.path.exists(dest):
                print(f"[skip] {s['slug']}_{phase} (đã có)")
                continue
            try:
                results = search(q)
            except Exception as e:
                print(f"[ERR ] {s['slug']}_{phase}: {e}")
                continue
            if not results:
                print(f"[none] {s['slug']}_{phase} — không tìm thấy ảnh license mở cho '{q}'")
                continue
            pick = results[0]
            try:
                download(pick["thumb"], dest)
            except Exception as e:
                print(f"[ERR ] download {s['slug']}_{phase}: {e}")
                continue
            licenses[f"{s['slug']}_{phase}"] = pick
            print(f"[ok  ] {s['slug']}_{phase}  {pick['license']}  {pick['w']}x{pick['h']}  {pick['title'][:60]}")
    json.dump(licenses, open(os.path.join(OUT, "licenses.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("Đã lưu licenses.json")

if __name__ == "__main__":
    main()
