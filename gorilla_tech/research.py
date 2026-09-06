"""
Stage 1 — research.

Collects verifiable facts (Wikipedia) and freely licensed photos (Wikimedia
Commons) for the entities that appear in a topic. Results are cached on disk so
a render can be repeated without hitting the network, and so the pipeline still
works inside a sandbox with no internet route (it falls back to `cache/*.json`).
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import config
import util

# ─────────────────────────────────────────────────────────────
# Wikipedia
# ─────────────────────────────────────────────────────────────

def wiki_search(query: str, lang: str = "en", limit: int = 5) -> list[dict]:
    params = {
        "action": "query", "format": "json", "list": "search",
        "srsearch": query, "srlimit": str(limit), "utf8": "1",
    }
    url = config.WIKIPEDIA_API.format(lang=lang) + "?" + util.urllib.parse.urlencode(params)
    data = util.http_get(url, as_json=True)
    return [
        {"title": hit["title"], "snippet": re.sub(r"<[^>]+>", "", hit.get("snippet", ""))}
        for hit in data.get("query", {}).get("search", [])
    ]


def wiki_summary(title: str, lang: str = "en") -> dict:
    url = config.WIKIPEDIA_REST.format(lang=lang).replace(
        "{title}", util.urllib.parse.quote(title.replace(" ", "_"))
    )
    data = util.http_get(url, as_json=True)
    return {
        "title": data.get("title", title),
        "summary": data.get("extract", ""),
        "url": (data.get("content_urls", {}).get("desktop", {}) or {}).get("page", ""),
        "thumbnail": (data.get("thumbnail") or {}).get("source", ""),
    }


def wiki_sections(title: str, lang: str = "en", max_chars: int = 6000) -> dict:
    """Full plain-text extract (intro + first sections) — used as LLM grounding."""
    params = {
        "action": "query", "format": "json", "prop": "extracts", "explaintext": "1",
        "exsectionformat": "plain", "titles": title, "redirects": "1", "utf8": "1",
        "exchars": str(max_chars),
    }
    url = config.WIKIPEDIA_API.format(lang=lang) + "?" + util.urllib.parse.urlencode(params)
    data = util.http_get(url, as_json=True)
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    return {
        "title": page.get("title", title),
        "text": page.get("extract", ""),
        "pageid": page.get("pageid"),
    }


# ─────────────────────────────────────────────────────────────
# Wikimedia Commons (photos)
# ─────────────────────────────────────────────────────────────

def commons_search(query: str, limit: int = 8, min_width: int | None = None) -> list[dict]:
    min_width = min_width or config.IMAGE_MIN_WIDTH
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}", "gsrlimit": str(min(limit, 20)),
        "gsrnamespace": "6", "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "1600",
        "iiextmetadatafilter": "LicenseShortName|Artist|UsageTerms|Credit",
    }
    url = config.COMMONS_API + "?" + util.urllib.parse.urlencode(params)
    data = util.http_get(url, as_json=True)
    results = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        ext = info.get("extmetadata", {}) or {}
        width, height = info.get("width", 0) or 0, info.get("height", 0) or 0
        if width < min_width or height < min_width * 0.5:
            continue
        license_name = str(ext.get("LicenseShortName", {}).get("value", ""))
        if license_name and not _license_ok(license_name):
            continue
        results.append({
            "title": page.get("title", ""),
            "page": f"https://commons.wikimedia.org/wiki/{util.urllib.parse.quote(page.get('title', '').replace(' ', '_'))}",
            "url": info.get("url", ""),
            "thumb": info.get("thumburl", info.get("url", "")),
            "width": width, "height": height,
            "license": license_name,
            "artist": re.sub(r"<[^>]+>", "", str(ext.get("Artist", {}).get("value", ""))).strip()[:120],
            "credit": re.sub(r"<[^>]+>", "", str(ext.get("Credit", {}).get("value", ""))).strip()[:120],
        })
    return results


def _license_ok(license_name: str) -> bool:
    lowered = license_name.lower()
    return any(token in lowered for token in config.ALLOWED_LICENSES)


# ─────────────────────────────────────────────────────────────
# Orchestrated research pass
# ─────────────────────────────────────────────────────────────

def research_topic(topic: str, entities: Iterable[str] | None = None, lang: str = "es",
                   wiki_lang: str | None = None, project: Path | None = None,
                   image_queries: Iterable[str] | None = None,
                   polite_delay: float = 1.2, use_cache: bool = True) -> dict:
    """Build a facts bundle. Never raises on network failure — degrades to cache."""
    wiki_lang = wiki_lang or ("en" if lang == "en" else lang)
    entities = list(entities or [])
    image_queries = list(image_queries or [])
    slug = util.slugify(topic)
    cache_file = config.CACHE_DIR / f"{slug}.json"
    project_file = (Path(project) / "research" / "facts.json") if project else None

    bundle: dict = {
        "topic": topic,
        "lang": lang,
        "wiki_lang": wiki_lang,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "online": False,
        "entities": [],
        "images": [],
        "sources": [],
        "notes": [],
    }

    online = util.probe_network("https://commons.wikimedia.org/favicon.ico")
    if not online:
        util.warn("research", "no network route — falling back to bundled cache")
        cached = util.read_json(cache_file) or (util.read_json(project_file) if project_file else None)
        if cached:
            cached["online"] = False
            cached["notes"] = (cached.get("notes") or []) + ["served from cache (offline mode)"]
            util.ok("research", f"cache hit: {len(cached.get('entities', []))} entities, "
                                f"{len(cached.get('images', []))} images")
            return cached
        bundle["notes"].append("offline and no cache available")
        return bundle

    bundle["online"] = True
    for name in entities:
        try:
            hits = wiki_search(name, wiki_lang, limit=3)
            title = hits[0]["title"] if hits else name
            time.sleep(polite_delay)
            detail = wiki_sections(title, wiki_lang)
            summary = wiki_summary(title, wiki_lang)
            bundle["entities"].append({
                "query": name,
                "title": detail.get("title", title),
                "summary": (summary.get("summary") or detail.get("text", ""))[:1800],
                "text": detail.get("text", "")[:5200],
                "url": summary.get("url", ""),
                "thumbnail": summary.get("thumbnail", ""),
            })
            if summary.get("url"):
                bundle["sources"].append({"title": detail.get("title", title),
                                          "url": summary["url"], "kind": "wikipedia"})
            util.ok("research", f"{name}: {len(detail.get('text', ''))} chars")
            time.sleep(polite_delay)
        except Exception as exc:
            util.warn("research", f"{name}: {exc}")
            bundle["notes"].append(f"entity '{name}' failed: {exc}")

    for query in image_queries:
        try:
            found = commons_search(query, limit=6)
            for item in found[:4]:
                item["query"] = query
            bundle["images"].extend(found[:4])
            util.ok("research", f"images '{query}': {len(found)} candidates")
            time.sleep(polite_delay)
        except Exception as exc:
            util.warn("research", f"images '{query}': {exc}")
            bundle["notes"].append(f"images '{query}' failed: {exc}")

    if project_file:
        util.write_json(project_file, bundle)
    util.write_json(cache_file, bundle)
    return bundle


def pick_image(bundle: dict, query_tokens: Iterable[str], exclude: set[str] | None = None) -> dict | None:
    """Choose the best cached/dowloaded image record matching some tokens."""
    exclude = exclude or set()
    tokens = [t.lower() for t in query_tokens if t]
    best, best_score = None, -1.0
    for item in bundle.get("images", []):
        if item.get("url") in exclude:
            continue
        title = item.get("title", "").lower()
        score = sum(3 for token in tokens if token in title)
        score += min(item.get("width", 0), item.get("height", 0) * 1.6) / 900.0
        if item.get("license", "").lower().startswith(("cc0", "public")):
            score += 2
        if "icon" in title or "logo" in title or "map" in title:
            score -= 4
        if score > best_score:
            best, best_score = item, score
    return best
