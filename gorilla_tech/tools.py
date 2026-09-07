"""
Tool registry for the autonomous episode agent (`agent.py`).

Each tool wraps one pipeline stage so the LLM can decide *what* to do while the
code guarantees *how* it is done (research, script, assets, narration, render,
package). Results are JSON strings, truncated by the agent loop.
"""

from __future__ import annotations

import json
from pathlib import Path

import assets as assets_mod
import config
import music
import packaging
import render
import research
import scripting
import subtitles
import util
import voice

TOOL_SCHEMAS: list[dict] = []
TOOL_FUNCTIONS: dict = {}


def register_tool(name: str, description: str, parameters: dict):
    def decorator(func):
        TOOL_SCHEMAS.append({"type": "function",
                             "function": {"name": name, "description": description,
                                          "parameters": parameters}})
        TOOL_FUNCTIONS[name] = func
        return func
    return decorator


def _j(**kwargs) -> str:
    return json.dumps(kwargs, ensure_ascii=False, default=str)


# ── state shared by the tools of one agent run ────────────────
STATE: dict = {"project": None, "script": None, "timing": None, "facts": None}


def _project() -> Path:
    if not STATE["project"]:
        raise RuntimeError("call plan_episode first")
    return Path(STATE["project"])


@register_tool(
    name="plan_episode",
    description="Create the project workspace and run the research stage (Wikipedia + "
                "Wikimedia Commons, cached when offline). Must be called first.",
    parameters={
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "entities": {"type": "array", "items": {"type": "string"},
                         "description": "platforms / units to research"},
            "image_queries": {"type": "array", "items": {"type": "string"}},
            "lang": {"type": "string", "enum": sorted(config.LANGUAGES)},
            "minutes": {"type": "number"},
            "brand": {"type": "string"},
            "offline": {"type": "boolean"},
        },
        "required": ["topic"],
    },
)
def plan_episode(topic: str, entities: list | None = None, image_queries: list | None = None,
                 lang: str = "es", minutes: float = 12.0, brand: str = "GORIZON TECH",
                 offline: bool = False) -> str:
    project = config.PROJECTS_DIR / util.slugify(topic)
    for sub in ("research", "assets/images", "audio", "work/segments", "output"):
        (project / sub).mkdir(parents=True, exist_ok=True)
    STATE.update({"project": str(project), "lang": lang, "minutes": minutes,
                  "brand": brand, "script": None, "timing": None})
    facts_file = project / "research" / "facts.json"
    if facts_file.exists():
        facts = util.read_json(facts_file, {})
    elif offline or not util.probe_network():
        facts = util.read_json(config.CACHE_DIR / f"{util.slugify(topic)}.json") or \
            {"topic": topic, "entities": [], "images": [], "sources": []}
    else:
        try:
            facts = research.research_topic(topic=topic, entities=entities or [topic],
                                            lang=lang, project=project,
                                            image_queries=image_queries or (entities or [topic])[:4])
        except Exception as exc:
            facts = {"topic": topic, "entities": [], "images": [], "notes": [str(exc)]}
    STATE["facts"] = facts
    return _j(project=str(project), entities=len(facts.get("entities", [])),
              images=len(facts.get("images", [])), online=facts.get("online", False),
              notes=facts.get("notes", [])[:3])


@register_tool(
    name="write_script",
    description="Write script.json (narration + storyboard) with the LLM writer, or with the "
                "deterministic fallback when no LLM is reachable. Returns the beat/visual summary.",
    parameters={
        "type": "object",
        "properties": {
            "notes": {"type": "string", "description": "extra editorial instructions"},
            "template": {"type": "string", "description": "optional committed template name"},
        },
    },
)
def write_script(notes: str = "", template: str = "") -> str:
    project = _project()
    lang = STATE.get("lang", "es")
    minutes = float(STATE.get("minutes", 12))
    brand = STATE.get("brand", "GORIZON TECH")
    if template:
        loaded = scripting.load_template(template)
        if loaded:
            script = scripting.normalize_script(loaded, lang=loaded.get("meta", {}).get("lang", lang),
                                                target_minutes=minutes,
                                                topic=STATE["facts"].get("topic", ""), brand=brand)
            script["meta"]["generator"] = f"template:{template}"
            STATE["script"] = script
            util.write_json(project / "script.json", script)
            return _j(ok=True, generator=script["meta"]["generator"], **script.get("stats", {}))
    import llm as llm_mod

    client = llm_mod.LLM()
    try:
        script = scripting.generate_script(topic=STATE["facts"].get("topic", ""), facts=STATE["facts"],
                                           lang=lang, target_minutes=minutes, brand=brand,
                                           client=client, extra_notes=notes)
        script["meta"]["generator"] = f"llm:{client.model}"
    except Exception as exc:
        util.warn("agent", f"LLM writer failed ({str(exc)[:120]}), using fallback")
        script = scripting.fallback_script(topic=STATE["facts"].get("topic", ""), facts=STATE["facts"],
                                           lang=lang, target_minutes=minutes, brand=brand)
    STATE["script"] = script
    util.write_json(project / "script.json", script)
    return _j(ok=True, generator=script["meta"]["generator"], **script.get("stats", {}))


@register_tool(
    name="inspect_script",
    description="Return the current script summary: scenes, beats, visuals, words, est. runtime.",
    parameters={"type": "object", "properties": {}},
)
def inspect_script() -> str:
    script = STATE.get("script")
    if not script:
        return _j(ok=False, error="no script yet")
    return _j(ok=True, meta={k: script["meta"].get(k) for k in ("title", "lang", "brand")},
              stats=script.get("stats"),
              scenes=[{"id": s["id"], "beat": s["beat"],
                       "visual": s["visual"].get("type"),
                       "seconds": round(s.get("duration_hint", 0), 1),
                       "words": scripting.word_count(s["narration"])} for s in script["scenes"]])


@register_tool(
    name="patch_scene",
    description="Merge a patch into one scene of script.json (e.g. fix narration, visual, chips).",
    parameters={
        "type": "object",
        "properties": {
            "scene_id": {"type": "string"},
            "patch": {"type": "object", "description": "fields to merge into the scene"},
        },
        "required": ["scene_id", "patch"],
    },
)
def patch_scene(scene_id: str, patch: dict) -> str:
    script = STATE.get("script")
    if not script:
        return _j(ok=False, error="no script yet")
    for scene in script["scenes"]:
        if scene["id"] == scene_id:
            for key, value in patch.items():
                if key == "visual" and isinstance(value, dict):
                    scene["visual"].update(value)
                else:
                    scene[key] = value
            util.write_json(_project() / "script.json", script)
            return _j(ok=True, scene=scene_id)
    return _j(ok=False, error=f"unknown scene {scene_id}")


@register_tool(
    name="gather_assets",
    description="Download CC/PD photos for the photo scenes (Wikimedia Commons, optional AI "
                "fallback). Writes assets/images.json and the credit metadata.",
    parameters={"type": "object", "properties": {"offline": {"type": "boolean"}}},
)
def gather_assets(offline: bool = False) -> str:
    info = assets_mod.resolve_scene_images(STATE["script"], STATE["facts"], _project(),
                                           live_search=not offline)
    used = [r["scene_id"] for r in info["records"] if r.get("origin") != "none"]
    return _j(ok=True, images=used)


@register_tool(
    name="generate_narration",
    description="Synthesise per-scene narration (edge/elevenlabs/openai/none) and build timing.json.",
    parameters={
        "type": "object",
        "properties": {
            "provider": {"type": "string", "enum": ["edge", "elevenlabs", "openai", "none"]},
            "voice_name": {"type": "string", "description": "e.g. es-MX-JorgeNeural"},
        },
    },
)
def generate_narration(provider: str = "edge", voice_name: str = "") -> str:
    timing = voice.synthesise_scenes(STATE["script"], _project(), provider=provider,
                                     voice=voice_name or None)
    STATE["timing"] = timing
    return _j(ok=True, seconds=timing["total_seconds"], provider=timing["provider"],
              voice=timing["voice"])


@register_tool(
    name="render_video",
    description="Render scene segments, burn subtitles and mux the audio mix into the final MP4.",
    parameters={
        "type": "object",
        "properties": {
            "resolution": {"type": "string", "enum": sorted(config.RESOLUTIONS)},
            "fps": {"type": "integer"},
            "workers": {"type": "integer"},
            "preview_seconds": {"type": "number", "description": "0 = full render"},
            "with_music": {"type": "boolean"},
            "burn_subs": {"type": "boolean"},
        },
    },
)
def render_video(resolution: str = "1080p", fps: int = 30, workers: int = 2,
                 preview_seconds: float = 0.0, with_music: bool = True,
                 burn_subs: bool = True) -> str:
    project = _project()
    script, timing = STATE["script"], STATE["timing"]
    if not timing:
        return _j(ok=False, error="run generate_narration first")
    size = config.video_size(resolution)
    cues = subtitles.build_cues(timing)
    name = util.slugify(script["meta"].get("title") or "video", 40)
    subs = subtitles.write_subtitles(cues, project, name, size)
    mix = None
    if with_music:
        risers, impacts = music.sfx_accents(project, timing)
        score = project / "audio" / "score.wav"
        music.render_score(float(timing["total_seconds"]) + 1.0, score,
                           seed=int(script["meta"].get("seed", 2024)),
                           risers=risers, impacts=impacts)
        narration = voice.build_narration_track(timing, project)
        mix = music.mix_audio(narration, score, project / "audio" / "mix.wav")
    segments = render.render_scenes(script, timing, project, size, fps, workers=workers,
                                    preview_seconds=preview_seconds or None)
    raw = project / "work" / "video_raw.mp4"
    render.concat_segments(segments, raw)
    final = raw
    if burn_subs:
        fonts = util.find_font(config.FONT_BOLD)
        final = render.burn_subtitles(raw, Path(subs["ass"]),
                                      project / "work" / "video_subs.mp4",
                                      fonts.parent if fonts else None)
    destination = project / "output" / f"{name}.mp4"
    render.mux(final, mix, destination)
    STATE["video"] = str(destination)
    STATE["subs"] = subs
    report = render.validate(destination, min(float(timing["total_seconds"]),
                                              preview_seconds or 10 ** 6), size, project)
    return _j(ok=True, video=str(destination), duration=report["duration_sec"],
              passed=report["passed"])


@register_tool(
    name="package_episode",
    description="Build the YouTube package: thumbnail, title/description/tags, chapters, CREDITS.md.",
    parameters={"type": "object", "properties": {}},
)
def package_episode() -> str:
    project = _project()
    thumb = packaging.build_thumbnail(STATE["script"], project)
    package = packaging.build_package(STATE["script"], STATE["timing"], project,
                                      Path(STATE.get("video", "")), STATE.get("subs", {}), thumb)
    return _j(ok=True, title=package["title"], chapters=len(package["chapters"]),
              files=package["files"])


@register_tool(
    name="report_status",
    description="Report progress or completion to the user.",
    parameters={
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["in_progress", "completed", "error",
                                                  "waiting_for_input"]},
            "message": {"type": "string"},
            "next_steps": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["status", "message"],
    },
)
def report_status(status: str, message: str, next_steps: list | None = None) -> str:
    util.log("agent", f"[{status}] {message}", "ok" if status == "completed" else "info")
    return _j(status=status, message=message, next_steps=next_steps or [])


def execute_tool_call(name: str, arguments: dict) -> str:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return _j(error=f"unknown tool {name}")
    try:
        return func(**arguments)
    except TypeError as exc:
        return _j(error=f"bad arguments for {name}: {exc}")
    except Exception as exc:
        return _j(error=f"{name} failed: {str(exc)[:300]}")
