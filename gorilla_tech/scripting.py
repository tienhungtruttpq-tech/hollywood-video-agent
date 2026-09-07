"""
Stage 2 — script & storyboard generation.

Primary path : LLM writes `script.json` following `prompts/script_system.txt`.
Fallback path: a deterministic builder assembles a script from the research bundle
               (used when no API key is configured or the gateway is unreachable).

The output is normalised so the renderer can always trust it: every scene has an id,
a beat, a known visual type and a duration estimate.
"""

from __future__ import annotations

import re
from pathlib import Path

import config
import llm as llm_mod
import util

PROMPT_FILE = config.PACKAGE_ROOT / "prompts" / "script_system.txt"

VALID_VISUALS = {"title", "chapter", "map", "photo", "image", "spec_card", "spec",
                 "stat", "timeline", "comparison", "quote", "text", "cta", "outro"}
VALID_BEATS = {"cold_open", "title", "setup", "reveal", "complication", "attempt_fail",
               "human", "escalation", "climax", "aftermath", "cost", "analysis", "cta",
               "chapter", "context", "detail"}


def style_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8")
    return "Write a military-tech documentary script as strict JSON."


def estimate_seconds(narration: str, lang: str = "es") -> float:
    """Rough speech duration used before real TTS timings exist."""
    chars = len((narration or "").strip())
    if not chars:
        return 6.0
    return max(4.0, chars / config.language(lang)["chars_per_sec"])


def word_count(narration: str) -> int:
    return len(re.findall(r"\S+", narration or ""))


# ─────────────────────────────────────────────────────────────
# LLM path
# ─────────────────────────────────────────────────────────────

def generate_script(topic: str, facts: dict, lang: str = "es", target_minutes: float = 13.0,
                    brand: str = "GORIZON TECH", client: llm_mod.LLM | None = None,
                    extra_notes: str = "") -> dict:
    client = client or llm_mod.LLM()
    lang_label = config.language(lang)["label"]
    research_text = _condense_research(facts)

    user_prompt = f"""TOPIC: {topic}
LANGUAGE OF THE VIDEO (narration + all on-screen text): {lang_label} ({lang})
TARGET_MINUTES: {target_minutes:g}
BRAND: {brand}
{('EXTRA NOTES: ' + extra_notes) if extra_notes else ''}

RESEARCH (the ONLY facts you may use; numbers must come from here):
{research_text}

Now produce the JSON object exactly as specified. Remember: JSON only."""

    messages = [
        {"role": "system", "content": style_prompt()},
        {"role": "user", "content": user_prompt},
    ]
    try:
        script = client.json(messages, json_mode=True, max_tokens=config.LLM_MAX_TOKENS)
    except llm_mod.LLMError as exc:
        util.warn("script", f"json_mode failed ({str(exc)[:80]}) — retrying without it")
        script = client.json(messages, max_tokens=config.LLM_MAX_TOKENS)
    if not isinstance(script, dict):
        raise llm_mod.LLMError("model did not return a JSON object")
    return normalize_script(script, lang=lang, target_minutes=target_minutes,
                            topic=topic, brand=brand)


def _condense_research(facts: dict, per_entity: int = 1400) -> str:
    if not facts:
        return "(no research available — write qualitatively, do not invent numbers)"
    parts = [f"TOPIC: {facts.get('topic', '?')}", f"SOURCE LANGUAGE: {facts.get('wiki_lang', 'en')}"]
    for entity in (facts.get("entities") or [])[:8]:
        text = re.sub(r"\s+", " ", entity.get("text") or entity.get("summary") or "").strip()
        parts.append(
            f"\n## {entity.get('title') or entity.get('query')}\n"
            f"URL: {entity.get('url', '')}\n{text[:per_entity]}"
        )
    images = facts.get("images") or []
    if images:
        lines = []
        for image in images[:14]:
            lines.append(f"- [{image.get('license')}] {image.get('title', '')[:80]} "
                         f"({image.get('width')}x{image.get('height')}) query='{image.get('query', '')}'")
        parts.append("\n## AVAILABLE CC/PD IMAGES (usable in `photo` scenes)\n" + "\n".join(lines))
    else:
        parts.append("\n## AVAILABLE CC/PD IMAGES: none — do NOT create `photo` scenes.")
    if facts.get("sources"):
        parts.append("\n## SOURCES\n" + "\n".join(
            f"- {s.get('title')}: {s.get('url')}" for s in facts["sources"][:10]))
    return "\n".join(parts)[:14000]


# ─────────────────────────────────────────────────────────────
# Normalisation / validation
# ─────────────────────────────────────────────────────────────

def normalize_script(script: dict, lang: str = "es", target_minutes: float = 13.0,
                     topic: str = "", brand: str = "GORIZON TECH") -> dict:
    meta = dict(script.get("meta") or {})
    meta.setdefault("topic", topic or meta.get("topic", "Untitled"))
    meta.setdefault("lang", lang)
    meta.setdefault("brand", brand)
    meta.setdefault("target_minutes", target_minutes)
    meta.setdefault("title", meta.get("topic"))
    meta.setdefault("title_options", [])
    meta.setdefault("logline", "")
    meta.setdefault("description", "")
    meta.setdefault("hashtags", [])
    meta.setdefault("tags", [])

    scenes_raw = script.get("scenes") or []
    scenes = []
    for index, scene in enumerate(scenes_raw):
        if not isinstance(scene, dict):
            continue
        visual = dict(scene.get("visual") or {})
        kind = str(visual.get("type", "text")).lower()
        if kind not in VALID_VISUALS:
            visual["type"] = "text"
        narration = str(scene.get("narration") or "").strip()
        beat = str(scene.get("beat") or "").lower()
        if beat not in VALID_BEATS:
            beat = "context"
        chips = [str(c)[:44] for c in (scene.get("on_screen") or [])][:3]
        scenes.append({
            "id": str(scene.get("id") or f"s{index + 1:02d}"),
            "beat": beat,
            "chapter": str(scene.get("chapter") or ""),
            "narration": narration,
            "on_screen": chips,
            "visual": visual,
            "duration_hint": float(scene.get("duration_hint") or estimate_seconds(narration, lang)),
        })

    if not scenes:
        raise llm_mod.LLMError("script contains no scenes")

    # guarantee a closing card
    if str((scenes[-1]["visual"] or {}).get("type", "")).lower() not in ("cta", "outro"):
        scenes.append({
            "id": "s_outro", "beat": "cta", "chapter": "",
            "narration": _sign_off(lang),
            "on_screen": [],
            "visual": {"type": "cta", "title": _cta_title(lang),
                       "button": _cta_button(lang), "lines": _cta_lines(lang)},
            "duration_hint": 6.0,
        })

    total_hint = sum(s["duration_hint"] for s in scenes)
    target_seconds = target_minutes * 60.0
    script = {
        "meta": meta,
        "facts": script.get("facts") or [],
        "scenes": scenes,
        "stats": {
            "scene_count": len(scenes),
            "words": sum(word_count(s["narration"]) for s in scenes),
            "estimated_seconds": round(total_hint, 1),
            "target_seconds": round(target_seconds, 1),
            "deviation_pct": round((total_hint - target_seconds) / max(target_seconds, 1) * 100, 1),
        },
    }
    return script


def _sign_off(lang: str) -> str:
    return {"es": "Esto es todo. Cambio y fuera.",
            "en": "That's it. Over and out.",
            "vi": "Đến đây là hết. Kết thúc."}.get(lang, "That's it. Over and out.")


def _cta_title(lang: str) -> str:
    return {"es": "SUSCRÍBETE", "en": "SUBSCRIBE", "vi": "ĐĂNG KÝ KÊNH"}.get(lang, "SUBSCRIBE")


def _cta_button(lang: str) -> str:
    return {"es": "SUSCRIBIRSE", "en": "SUBSCRIBE", "vi": "ĐĂNG KÝ"}.get(lang, "SUBSCRIBE")


def _cta_lines(lang: str) -> list[str]:
    return {
        "es": ["Nuevo análisis cada semana", "Tecnología militar explicada sin ruido",
               "Activa la campana para no perderte el próximo caso"],
        "en": ["A new analysis every week", "Military technology, explained without noise",
               "Hit the bell so you don't miss the next case"],
        "vi": ["Phân tích mới mỗi tuần", "Công nghệ quân sự, giải thích dễ hiểu",
               "Bật chuông để không bỏ lỡ tập tiếp theo"],
    }.get(lang, ["A new analysis every week"])


# ─────────────────────────────────────────────────────────────
# Offline / no-key fallback
# ─────────────────────────────────────────────────────────────

def fallback_script(topic: str, facts: dict, lang: str = "es", target_minutes: float = 8.0,
                    brand: str = "GORIZON TECH") -> dict:
    """Deterministic script built from research summaries — no LLM needed."""
    entities = (facts or {}).get("entities") or []
    images = (facts or {}).get("images") or []
    scenes: list[dict] = []

    scenes.append({
        "id": "s01", "beat": "cold_open",
        "chapter": _label(lang, "APERTURA"),
        "narration": _fallback_open(topic, lang),
        "on_screen": [topic.split()[0].upper() if topic else ""],
        "visual": {"type": "title", "kicker": _label(lang, "INFORME"), "title": topic,
                   "subtitle": _fallback_subtitle(lang)},
        "duration_hint": 10.0,
    })

    scenes.append({
        "id": "s02", "beat": "context", "chapter": _label(lang, "CONTEXTO"),
        "narration": _fallback_context(lang),
        "on_screen": [],
        "visual": {"type": "map", "title": _label(lang, "TEATRO DE OPERACIONES"),
                   "kicker": _label(lang, "MAPA"), "zoom_km": 120,
                   "route": [[0.12, 0.72], [0.38, 0.55], [0.62, 0.42], [0.86, 0.28]],
                   "drone_route": [[0.20, 0.20], [0.45, 0.40], [0.66, 0.52]],
                   "units": [{"at": [0.86, 0.28], "label": _label(lang, "OBJETIVO"),
                              "short": "TGT", "kind": "heli", "side": "hostile"},
                             {"at": [0.20, 0.20], "label": _label(lang, "DRON"),
                              "short": "UAV", "kind": "fpv", "side": "friendly"}],
                   "rings": [{"at": [0.86, 0.28], "km": 18, "label": "18 km"}],
                   "movers": [{"route": "route", "kind": "heli", "side": "hostile",
                               "start": 0.0, "end": 1.0},
                              {"route": "drone_route", "kind": "fpv", "side": "friendly",
                               "start": 0.15, "end": 0.95}],
                   "events": [{"at": 0.88, "at_xy": [0.86, 0.28], "kind": "impact"}],
                   "flash_on_impact": True, "draw_time": 0.8},
        "duration_hint": 26.0,
    })

    for index, entity in enumerate(entities[:4]):
        text = re.sub(r"\s+", " ", entity.get("summary") or entity.get("text") or "").strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 40]
        narration = " ".join(sentences[:4]) or text[:600]
        stats = _stats_from_text(narration, lang)
        image = None
        tokens = str(entity.get("title", "")).split()[:3]
        if images:
            for candidate in images:
                title = candidate.get("title", "").lower()
                if any(t.lower() in title for t in tokens if len(t) > 3):
                    image = candidate
                    break
        scene_id = f"s{index + 3:02d}"
        if image:
            scenes.append({
                "id": scene_id, "beat": "setup",
                "chapter": str(entity.get("title", ""))[:28].upper(),
                "narration": narration,
                "on_screen": [str(entity.get("title", ""))[:22]],
                "visual": {"type": "photo", "image_query": str(entity.get("title", "")),
                           "caption": str(entity.get("title", ""))[:60],
                           "credit": f"{image.get('artist', '')} · {image.get('license', '')}"[:100],
                           "hud": False, "zoom_from": 1.02, "zoom_to": 1.16,
                           "pan": [0.4, -0.3], "fallback": "spec_card",
                           "name": str(entity.get("title", "")), "stats": stats,
                           "icon": "heli"},
                "duration_hint": estimate_seconds(narration, lang),
            })
        else:
            scenes.append({
                "id": scene_id, "beat": "setup",
                "chapter": str(entity.get("title", ""))[:28].upper(),
                "narration": narration,
                "on_screen": [str(entity.get("title", ""))[:22]],
                "visual": {"type": "spec_card", "name": str(entity.get("title", "")),
                           "subtitle": _label(lang, "FICHA TÉCNICA"), "icon": "heli",
                           "stats": stats, "note": (entity.get("url") or "")[:80]},
                "duration_hint": estimate_seconds(narration, lang),
            })

    scenes.append({
        "id": "s_timeline", "beat": "escalation", "chapter": _label(lang, "CRONOLOGÍA"),
        "narration": _fallback_timeline(lang),
        "on_screen": [],
        "visual": {"type": "timeline", "title": _label(lang, "CRONOLOGÍA"),
                   "kicker": _label(lang, "SECUENCIA"), "mode": "clock",
                   "total_seconds": 540, "clock_label": _label(lang, "VENTANA"),
                   "events": [{"at": 0.05, "time": "T+0", "text": _label(lang, "DESPEGUE")},
                              {"at": 0.4, "time": "T+4", "text": _label(lang, "DETECCIÓN")},
                              {"at": 0.75, "time": "T+9", "text": _label(lang, "INTERCEPTACIÓN")},
                              {"at": 0.95, "time": "T+12", "text": _label(lang, "IMPACTO")}],
                   "note": _fallback_note(lang)},
        "duration_hint": 24.0,
    })

    scenes.append({
        "id": "s_quote", "beat": "human", "chapter": "",
        "narration": _fallback_quote_narration(lang),
        "on_screen": [],
        "visual": {"type": "quote", "text": _fallback_quote(lang),
                   "author": _label(lang, "OPERADOR")},
        "duration_hint": 14.0,
    })

    scenes.append({
        "id": "s_cost", "beat": "cost", "chapter": _label(lang, "BALANCE"),
        "narration": _fallback_cost(lang),
        "on_screen": [],
        "visual": {"type": "stat", "value": 1, "decimals": 0, "suffix": "",
                   "label": _label(lang, "COSTE / EFECTO"), "tone": "accent",
                   "note": _fallback_cost_note(lang)},
        "duration_hint": 18.0,
    })

    script = {
        "meta": {
            "topic": topic, "lang": lang, "brand": brand, "target_minutes": target_minutes,
            "title": topic, "title_options": [topic], "logline": _fallback_subtitle(lang),
            "description": _fallback_description(topic, lang, entities),
            "hashtags": _fallback_hashtags(topic), "tags": _fallback_tags(topic, entities),
            "generator": "fallback",
        },
        "facts": [{"statement": e.get("title", ""), "source": e.get("url", "wikipedia")}
                  for e in entities],
        "scenes": scenes,
    }
    normalized = normalize_script(script, lang=lang, target_minutes=target_minutes,
                                  topic=topic, brand=brand)
    normalized["meta"]["generator"] = "fallback"
    return normalized


def _stats_from_text(text: str, lang: str) -> list[dict]:
    """Pull plausible spec rows out of a summary so offline spec cards are not empty."""
    patterns = [
        (r"(\d[\d.,]*)\s*km/h", "km/h", 400),
        (r"(\d[\d.,]*)\s*(?:km|kilómetros|kilometers)", "km", 2000),
        (r"(\d[\d.,]*)\s*(?:m\b|metros|meters)", "m", 5000),
        (r"(\d[\d.,]*)\s*(?:kg|toneladas|tonnes)", "kg", 12000),
        (r"(\d{4})", "año", 2025),
    ]
    rows: list[dict] = []
    for pattern, unit, ceiling in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        raw = match.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if value <= 0:
            continue
        rows.append({"label": unit.upper(), "value": f"{util.format_number(value, lang, 0)} {unit}",
                     "meter": round(min(1.0, value / ceiling), 2)})
        if len(rows) >= 5:
            break
    if not rows:
        rows = [{"label": _label(lang, "TIPO"), "value": _label(lang, "PLATAFORMA"), "meter": 0.5}]
    return rows


def _label(lang: str, key: str) -> str:
    table = {
        "es": {"APERTURA": "APERTURA", "INFORME": "INFORME", "CONTEXTO": "CONTEXTO",
               "MAPA": "MAPA TÁCTICO", "TEATRO DE OPERACIONES": "TEATRO DE OPERACIONES",
               "OBJETIVO": "OBJETIVO", "DRON": "DRON FPV", "FICHA TÉCNICA": "FICHA TÉCNICA",
               "CRONOLOGÍA": "CRONOLOGÍA", "SECUENCIA": "SECUENCIA", "VENTANA": "VENTANA DE TIEMPO",
               "DESPEGUE": "DESPEGUE", "DETECCIÓN": "DETECCIÓN",
               "INTERCEPTACIÓN": "INTERCEPTACIÓN", "IMPACTO": "IMPACTO",
               "OPERADOR": "OPERADOR", "BALANCE": "BALANCE",
               "COSTE / EFECTO": "COSTE / EFECTO", "TIPO": "TIPO", "PLATAFORMA": "PLATAFORMA"},
        "en": {}, "vi": {},
    }
    return table.get(lang, table["es"]).get(key, key)


def _fallback_open(topic: str, lang: str) -> str:
    return {
        "es": f"Lo que viene a continuación duró menos de quince minutos, y cambió la forma en que "
              f"se entiende la guerra de drones. Este es el caso de {topic}.",
        "en": f"What follows lasted less than fifteen minutes, and changed how drone warfare is "
              f"understood. This is the case of {topic}.",
        "vi": f"Những gì diễn ra tiếp theo kéo dài chưa tới mười lăm phút, và thay đổi cách người ta "
              f"hiểu về chiến tranh UAV. Đây là trường hợp của {topic}.",
    }.get(lang, "")


def _fallback_subtitle(lang: str) -> str:
    return {"es": "Análisis técnico de un engagement real",
            "en": "Technical analysis of a real engagement",
            "vi": "Phân tích kỹ thuật một trận đánh có thật"}.get(lang, "")


def _fallback_context(lang: str) -> str:
    return {"es": "Antes de entrar en los números, hay que entender el terreno. Una ruta de escape a "
                  "baja altura, radar apagado, y un cielo que parece vacío. Parece vacío.",
            "en": "Before the numbers, the terrain. A low-altitude escape route, radar off, and a sky "
                  "that looks empty. It looks empty.",
            "vi": "Trước khi nói về các con số, cần hiểu địa hình. Một tuyến bay thấp, radar tắt, "
                  "và một bầu trời trông có vẻ trống. Trông có vẻ trống."}.get(lang, "")


def _fallback_timeline(lang: str) -> str:
    return {"es": "Toda la operación cabe en una ventana de nueve minutos. Cada minuto consumido en "
                  "dudar es un kilómetro más de ventaja para el objetivo.",
            "en": "The whole operation fits inside a nine-minute window. Every minute spent hesitating "
                  "is one more kilometre of advantage for the target.",
            "vi": "Toàn bộ chiến dịch nằm trong cửa sổ chín phút. Mỗi phút do dự là thêm một kilômét "
                  "lợi thế cho mục tiêu."}.get(lang, "")


def _fallback_note(lang: str) -> str:
    return {"es": "Reconstrucción basada en fuentes abiertas.",
            "en": "Reconstruction based on open sources.",
            "vi": "Dựng lại dựa trên nguồn mở."}.get(lang, "")


def _fallback_quote(lang: str) -> str:
    return {"es": "Tenemos un observador.",
            "en": "We have an observer.",
            "vi": "Chúng ta có một trinh sát."}.get(lang, "")


def _fallback_quote_narration(lang: str) -> str:
    return {"es": "Cuatro palabras por radio. Sin subir la voz. Lo que viene después depende de un "
                  "piloto de veintitrés años y de una batería que dura la mitad de lo prometido.",
            "en": "Four words over the radio, without raising the voice. What comes next depends on a "
                  "twenty-three-year-old pilot and a battery that lasts half as long as advertised.",
            "vi": "Bốn từ qua bộ đàm, không lớn tiếng. Điều tiếp theo phụ thuộc vào một phi công "
                  "hai mươi ba tuổi và một cục pin chỉ trụ được nửa thời gian công bố."}.get(lang, "")


def _fallback_cost(lang: str) -> str:
    return {"es": "Al final, la cuenta importa más que la explosión. Un dron de unos pocos miles de "
                  "dólares contra una plataforma de decenas de millones. La proporción es el mensaje.",
            "en": "In the end the bill matters more than the explosion. A drone worth a few thousand "
                  "dollars against a platform worth tens of millions. The ratio is the message.",
            "vi": "Cuối cùng, bài toán chi phí quan trọng hơn vụ nổ. Một UAV vài nghìn đô so với một "
                  "tổ hợp hàng chục triệu đô. Tỷ lệ đó chính là thông điệp."}.get(lang, "")


def _fallback_cost_note(lang: str) -> str:
    return {"es": "Las cifras exactas se indican en el análisis del episodio.",
            "en": "Exact figures are given in the episode analysis.",
            "vi": "Số liệu chính xác được nêu trong phần phân tích."}.get(lang, "")


def _fallback_description(topic: str, lang: str, entities: list[dict]) -> str:
    names = ", ".join(str(e.get("title", "")) for e in entities[:4]) or topic
    if lang == "es":
        return (f"Análisis técnico de {topic}.\n\n"
                f"En este vídeo revisamos {names}: qué capacidades tiene, qué limitaciones reales "
                f"aparecen en combate y por qué el coste por efecto se ha convertido en la métrica "
                f"decisiva.\n\n"
                f"Reconstrucción basada en fuentes abiertas.")
    if lang == "vi":
        return (f"Phân tích kỹ thuật: {topic}.\n\n"
                f"Video xem xét {names}: năng lực, giới hạn thực tế trong chiến đấu, và vì sao "
                f"chi phí trên hiệu quả trở thành thước đo quyết định.\n\n"
                f"Dựng lại từ nguồn mở.")
    return (f"Technical analysis of {topic}.\n\n"
            f"This episode looks at {names}: capabilities, real combat limitations and why "
            f"cost-per-effect became the decisive metric.\n\n"
            f"Reconstruction based on open sources.")


def _fallback_hashtags(topic: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9]{4,}", topic)
    base = ["#MilitaryTechnology", "#DroneWarfare", "#ModernWarfare", "#TechAnalysis"]
    return [f"#{w.capitalize()}" for w in words[:4]] + base


def _fallback_tags(topic: str, entities: list[dict]) -> list[str]:
    tags = [topic.lower(), "military technology", "drone warfare", "modern warfare",
            "combat analysis", "defense technology"]
    for entity in entities[:6]:
        tags.append(str(entity.get("title", "")).lower())
    return [t for t in tags if t][:30]


# ─────────────────────────────────────────────────────────────
# Template scripts (committed, fully offline)
# ─────────────────────────────────────────────────────────────

def load_template(name: str) -> dict | None:
    path = config.TEMPLATE_DIR / f"{name}.json"
    if not path.exists():
        return None
    return util.read_json(path)


def script_summary(script: dict) -> str:
    stats = script.get("stats", {})
    beats = {}
    for scene in script.get("scenes", []):
        beats[scene["beat"]] = beats.get(scene["beat"], 0) + 1
    visuals = {}
    for scene in script.get("scenes", []):
        kind = scene["visual"].get("type", "text")
        visuals[kind] = visuals.get(kind, 0) + 1
    return (f"{stats.get('scene_count', len(script.get('scenes', [])))} scenes · "
            f"{stats.get('words', 0)} words · "
            f"{util.clock(stats.get('estimated_seconds', 0))} est · "
            f"beats={beats} visuals={visuals}")
