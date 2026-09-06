#!/usr/bin/env python3
"""
Hollywood Video Production Agent — Token-Optimized
====================================================
Uses Claude Fable 5.1 (Experiential Labs) with aggressive token optimization:
- Compact system prompt
- Sliding context window (keeps only recent messages)
- Truncated tool results
- Rate limit auto-retry

Usage:
    python agent.py --topic "K-pop Stars"    # Specify topic
    python agent.py --test-api               # Test API connection
    python agent.py --dry-run                # Dry run (no rendering)
"""

import json, sys, argparse, urllib.request, time
from pathlib import Path
import config, tools

# ── Compact System Prompt (~500 tokens instead of ~1200) ──────

SYSTEM_PROMPT = """You are a video production agent. Create a "Then & Now" celebrity comparison video.

STEPS (in order):
1. PLAN: Pick 10 actors. Use report_status to announce.
2. PHOTOS: For each actor, search_wikimedia for 2 CC-licensed photos (early + recent). Download to new_project/assets/photos/.
3. METADATA: create_actors_json at new_project/actors.json.
4. NARRATIVE: write_file new_project/narrative.json with 2-sentence narration per person.
5. RENDER SCRIPT: write_file new_project/render.py (Pillow+OpenCV, 1280x720, 30fps, THEN left / NOW right, captions, transitions).
6. RUN: run_python_script to render (skip if dry-run).
7. DONE: report_status status=completed.

RULES:
- Only CC/PD photos. Skip actors without good photos.
- Do NOT read files from hollywood_full/ or hollywood_actresses/. They are reference only.
- Be concise. Minimize tool calls. Batch work when possible.
- Max 1-2 search_wikimedia calls per actor to avoid rate limits."""

# Max tokens to keep in tool results sent back to LLM
MAX_TOOL_RESULT_CHARS = 1500
# Sliding window: keep system + user + last N message pairs
MAX_CONTEXT_MESSAGES = 16

# ── API Client with Rate Limit Retry ──────────────────────────

def call_fable_api(messages: list, tools_list: list = None) -> dict:
    body = {
        "model": config.MODEL,
        "messages": messages,
        "max_tokens": config.MAX_TOKENS,
        "temperature": config.TEMPERATURE,
    }
    if tools_list:
        body["tools"] = tools_list
        body["tool_choice"] = "auto"

    data = json.dumps(body).encode("utf-8")

    for attempt in range(4):
        req = urllib.request.Request(
            f"{config.API_BASE_URL}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.API_KEY}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            if e.code == 429 and attempt < 3:
                wait = 30 * (attempt + 1)
                print(f"   [Rate limit] Waiting {wait}s before retry {attempt+2}/4...")
                time.sleep(wait)
                continue
            print(f"\nAPI Error {e.code}: {error_body[:300]}")
            raise
        except Exception as e:
            print(f"\nAPI Error: {e}")
            raise


def test_api_connection():
    print("Testing API connection to Fable 5.1...")
    try:
        result = call_fable_api([{"role": "user", "content": "Reply with exactly: API_OK"}])
        reply = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        print(f"OK! Model: {result.get('model')} | Tokens: {usage.get('total_tokens', '?')}")
        print(f"Response: {reply}")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False


# ── Sliding Window Context Manager ────────────────────────────

def trim_messages(messages: list) -> list:
    """Keep system + user prompt + last MAX_CONTEXT_MESSAGES messages."""
    if len(messages) <= MAX_CONTEXT_MESSAGES + 2:
        return messages
    # Always keep: messages[0] (system) and messages[1] (user prompt)
    # Then keep the last MAX_CONTEXT_MESSAGES messages
    kept = messages[:2] + messages[-(MAX_CONTEXT_MESSAGES):]
    return kept


def truncate_tool_result(result: str) -> str:
    """Truncate tool result to save tokens."""
    if len(result) <= MAX_TOOL_RESULT_CHARS:
        return result
    return result[:MAX_TOOL_RESULT_CHARS] + '\n... [truncated]'


# ── Agent Loop ────────────────────────────────────────────────

def run_agent(topic: str, dry_run: bool = False):
    print(f"\n{'='*50}")
    print(f"  Video Agent - Fable 5.1")
    print(f"  Topic: {topic}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'FULL RUN'}")
    print(f"{'='*50}\n")

    project_dir = Path(config.PROJECT_ROOT) / "new_project"
    project_dir.mkdir(exist_ok=True)
    (project_dir / "assets" / "photos").mkdir(parents=True, exist_ok=True)
    (project_dir / "output").mkdir(exist_ok=True)

    user_msg = f"Topic: {topic}. Working dir: {project_dir}."
    if dry_run:
        user_msg += " DRY RUN: skip actual video rendering."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    total_tokens = 0

    for iteration in range(config.MAX_AGENT_ITERATIONS):
        print(f"\n--- Iter {iteration+1}/{config.MAX_AGENT_ITERATIONS} ---")

        # Trim context window before each API call
        trimmed = trim_messages(messages)
        if len(trimmed) < len(messages):
            print(f"   [Context] Trimmed {len(messages)} -> {len(trimmed)} messages")

        try:
            response = call_fable_api(trimmed, tools.TOOL_SCHEMAS)
        except Exception as e:
            print(f"API failed: {e}")
            break

        choice = response["choices"][0]
        message = choice["message"]
        finish = choice.get("finish_reason", "")
        usage = response.get("usage", {})
        iter_tokens = usage.get("total_tokens", 0)
        total_tokens += iter_tokens

        print(f"   Tokens: {iter_tokens} (total: {total_tokens}) | Finish: {finish}")

        if message.get("content"):
            text = message["content"][:300]
            print(f"\n   Agent: {text}{'...' if len(message.get('content',''))>300 else ''}")

        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            if finish == "stop":
                print("\n   Agent finished.")
                break
            continue

        for tc in tool_calls:
            func_name = tc["function"]["name"]
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                func_args = {}

            print(f"   Tool: {func_name}({json.dumps(func_args, ensure_ascii=False)[:80]})")

            result = tools.execute_tool_call(func_name, func_args)
            truncated = truncate_tool_result(result)

            print(f"     -> {truncated[:150]}{'...' if len(truncated)>150 else ''}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": truncated,
            })

        # Check completion
        for tc in tool_calls:
            if tc["function"]["name"] == "report_status":
                try:
                    args = json.loads(tc["function"]["arguments"])
                    if args.get("status") == "completed":
                        print("\n   COMPLETED!")
                except:
                    pass
    else:
        print(f"\n   Hit max iterations ({config.MAX_AGENT_ITERATIONS}).")

    print(f"\n{'='*50}")
    print(f"  Done. Messages: {len(messages)} | Total tokens: {total_tokens}")
    print(f"{'='*50}\n")
    return messages


# ── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Hollywood Video Agent (Fable 5.1)")
    parser.add_argument("--topic", type=str, default=None)
    parser.add_argument("--test-api", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.test_api:
        sys.exit(0 if test_api_connection() else 1)

    topic = args.topic
    if not topic:
        topic = input("Enter topic: ").strip() or config.DEFAULT_TOPIC

    run_agent(topic, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
