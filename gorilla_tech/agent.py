#!/usr/bin/env python3
"""
agent.py — autonomous episode producer.

The LLM drives the pipeline through tools (research → script → assets →
narration → render → package). For a hands-off, deterministic run use
`make_video.py` instead; this agent exists for the cases where the story needs
editorial judgement between stages.

    python agent.py --topic "El Orlan-10 que vio demasiado" --lang es --minutes 10
    python agent.py --test-api
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import llm as llm_mod
import tools
import util

SYSTEM_PROMPT = """You are an autonomous producer of military-technology storytelling videos
(channel format: calm narrated tactical reconstructions, see STYLE_GUIDE.md).

WORKFLOW (call tools in this order; report_status between major steps):
1. plan_episode(topic, entities, image_queries, lang, minutes)
2. write_script()  — the LLM writer already follows the channel contract
3. inspect_script() — sanity check: 18-26 scenes, words ≈ minutes*150, at least
   2 map / 2 spec_card / 1 timeline / 1 comparison / 1 stat / 1 quote / 1 cta.
   Fix problems with patch_scene (never rewrite the whole script).
4. gather_assets()
5. generate_narration(provider="edge")  — if it reports provider=silence, continue anyway
6. render_video(preview_seconds=45) first as a smoke test, then render_video(preview_seconds=0)
7. package_episode()
8. report_status(status="completed", message=...) with the output paths.

RULES:
- Be concise. One tool call per message unless they are independent.
- Never invent facts in patch_scene narration: only restructure text that is already there.
- If a tool returns an error once, retry once with smaller scope; twice, report_status(error).
- Total runtime budget: prefer 1080p only for the final render, 720p for the smoke test.
"""


def run_agent(topic: str, lang: str = "es", minutes: float = 12.0,
              entities: str = "", brand: str = "GORIZON TECH",
              preview: float = 0.0, dry_run: bool = False) -> int:
    client = llm_mod.LLM()
    if not client.available:
        util.fail("agent", "no LLM credentials — use make_video.py (deterministic pipeline)")
        return 2

    user_msg = (f"Produce one episode.\nTopic: {topic}\nLanguage: {lang}\nTarget minutes: {minutes}\n"
                f"Brand: {brand}\nEntities to research: {entities or topic}\n"
                f"Smoke-test preview seconds: {preview or 45}\n"
                + ("DRY RUN: stop after package_episode is described, do not render." if dry_run else ""))

    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}]
    total_tokens = 0

    for iteration in range(config.MAX_AGENT_ITERATIONS):
        util.log("agent", f"iter {iteration + 1}/{config.MAX_AGENT_ITERATIONS}")
        trimmed = messages[:2] + messages[-config.MAX_CONTEXT_MESSAGES:]
        try:
            choice = client.chat(trimmed, tools=tools.TOOL_SCHEMAS)
        except llm_mod.LLMError as exc:
            util.fail("agent", str(exc)[:200])
            break
        message = choice["message"]
        total_tokens += 0
        if message.get("content"):
            util.log("agent", message["content"][:280].replace("\n", " "))
        messages.append(message)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            if choice.get("finish_reason") == "stop":
                util.ok("agent", "agent finished")
                break
            continue
        done = False
        for call in tool_calls:
            name = call["function"]["name"]
            try:
                arguments = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = {}
            util.log("tool", f"{name}({json.dumps(arguments, ensure_ascii=False)[:110]})")
            result = tools.execute_tool_call(name, arguments)
            util.log("tool", f"-> {result[:180]}")
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": result[:config.MAX_TOOL_RESULT_CHARS]})
            if name == "report_status" and arguments.get("status") == "completed":
                done = True
        if done:
            break
    else:
        util.warn("agent", f"hit max iterations ({config.MAX_AGENT_ITERATIONS})")

    util.ok("agent", f"tokens total: {client.total_tokens} over {client.calls} calls")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous Gorilla Tech episode agent")
    parser.add_argument("--topic", default="")
    parser.add_argument("--entities", default="")
    parser.add_argument("--lang", default=config.DEFAULT_LANG, choices=sorted(config.LANGUAGES))
    parser.add_argument("--minutes", type=float, default=config.TARGET_MINUTES)
    parser.add_argument("--brand", default="GORIZON TECH")
    parser.add_argument("--preview", type=float, default=45.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-api", action="store_true")
    args = parser.parse_args()

    if args.test_api:
        return 0 if llm_mod.test_connection() else 1
    if not args.topic:
        print("error: --topic is required", file=sys.stderr)
        return 2
    return run_agent(args.topic, args.lang, args.minutes, args.entities, args.brand,
                     args.preview, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
