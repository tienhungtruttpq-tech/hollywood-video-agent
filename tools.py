"""
Tool functions that the AI Agent can invoke via function calling.
Each tool is exposed to the LLM as an OpenAI-compatible function schema.
"""

import os
import json
import subprocess
import sys
import urllib.request
import urllib.parse
import re
from pathlib import Path

import config

# ─────────────────────────────────────────────────────────────
# Tool Registry
# ─────────────────────────────────────────────────────────────

TOOL_SCHEMAS = []
TOOL_FUNCTIONS = {}


def register_tool(name: str, description: str, parameters: dict):
    """Decorator to register a tool function with its JSON schema."""
    def decorator(func):
        TOOL_SCHEMAS.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            }
        })
        TOOL_FUNCTIONS[name] = func
        return func
    return decorator


# ─────────────────────────────────────────────────────────────
# Tool Implementations
# ─────────────────────────────────────────────────────────────

@register_tool(
    name="list_directory",
    description="List files and directories at the given path. Returns names and types.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to list. Relative paths are resolved from project root."
            }
        },
        "required": ["path"]
    }
)
def list_directory(path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = Path(config.PROJECT_ROOT) / p
    if not p.exists():
        return json.dumps({"error": f"Path does not exist: {p}"})
    if not p.is_dir():
        return json.dumps({"error": f"Not a directory: {p}"})

    items = []
    for child in sorted(p.iterdir()):
        entry = {"name": child.name, "type": "dir" if child.is_dir() else "file"}
        if child.is_file():
            entry["size_bytes"] = child.stat().st_size
        items.append(entry)
    return json.dumps({"path": str(p), "items": items}, ensure_ascii=False)


@register_tool(
    name="read_file",
    description="Read the contents of a text file (UTF-8). Returns the first 10000 characters.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read."
            }
        },
        "required": ["path"]
    }
)
def read_file(path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = Path(config.PROJECT_ROOT) / p
    if not p.exists():
        return json.dumps({"error": f"File not found: {p}"})
    try:
        content = p.read_text(encoding="utf-8", errors="replace")[:3000]
        return json.dumps({"content": content, "truncated": len(content) == 3000}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@register_tool(
    name="write_file",
    description="Write text content to a file. Creates parent directories if needed.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write."
            },
            "content": {
                "type": "string",
                "description": "The text content to write."
            }
        },
        "required": ["path", "content"]
    }
)
def write_file(path: str, content: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = Path(config.PROJECT_ROOT) / p
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return json.dumps({"success": True, "path": str(p), "bytes_written": len(content.encode("utf-8"))})
    except Exception as e:
        return json.dumps({"error": str(e)})


@register_tool(
    name="run_command",
    description="Run a shell command and return stdout/stderr. Timeout is 120 seconds.",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to execute."
            },
            "cwd": {
                "type": "string",
                "description": "Working directory. Defaults to project root."
            }
        },
        "required": ["command"]
    }
)
def run_command(command: str, cwd: str = None) -> str:
    work_dir = cwd or config.PROJECT_ROOT
    try:
        result = subprocess.run(
            command, shell=True, cwd=work_dir,
            capture_output=True, text=True, timeout=120
        )
        output = {
            "returncode": result.returncode,
            "stdout": result.stdout[:2000] if result.stdout else "",
            "stderr": result.stderr[:1000] if result.stderr else "",
        }
        return json.dumps(output, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Command timed out after 120 seconds."})
    except Exception as e:
        return json.dumps({"error": str(e)})


@register_tool(
    name="run_python_script",
    description="Run a Python script with optional arguments. Returns stdout/stderr.",
    parameters={
        "type": "object",
        "properties": {
            "script_path": {
                "type": "string",
                "description": "Path to the Python script."
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Command-line arguments for the script."
            }
        },
        "required": ["script_path"]
    }
)
def run_python_script(script_path: str, args: list = None) -> str:
    p = Path(script_path)
    if not p.is_absolute():
        p = Path(config.PROJECT_ROOT) / p
    if not p.exists():
        return json.dumps({"error": f"Script not found: {p}"})
    cmd = [sys.executable, str(p)] + (args or [])
    try:
        result = subprocess.run(
            cmd, cwd=str(p.parent),
            capture_output=True, text=True, timeout=300
        )
        return json.dumps({
            "returncode": result.returncode,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:1000],
        }, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Script timed out after 300 seconds."})
    except Exception as e:
        return json.dumps({"error": str(e)})


@register_tool(
    name="search_wikimedia",
    description="Search Wikimedia Commons for freely-licensed photos. Returns up to 10 results with URLs and metadata.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g. 'Tom Cruise 1989 portrait'"
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default 10, max 20)."
            }
        },
        "required": ["query"]
    }
)
def search_wikimedia(query: str, limit: int = 5) -> str:
    limit = min(limit, 10)
    params = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": limit,
        "gsrnamespace": 6,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|Artist",
    })
    url = f"https://commons.wikimedia.org/w/api.php?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HollywoodAgentBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        pages = data.get("query", {}).get("pages", {})
        results = []
        for page in pages.values():
            ii = (page.get("imageinfo") or [{}])[0]
            ext = ii.get("extmetadata", {})
            results.append({
                "title": page.get("title", "")[:60],
                "url": ii.get("url", ""),
                "license": ext.get("LicenseShortName", {}).get("value", ""),
                "artist": re.sub(r"<[^>]+>", "", ext.get("Artist", {}).get("value", ""))[:60],
            })
        return json.dumps({"count": len(results), "results": results}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@register_tool(
    name="download_image",
    description="Download an image from a URL and save it locally.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL of the image to download."
            },
            "save_path": {
                "type": "string",
                "description": "Local path to save the image."
            }
        },
        "required": ["url", "save_path"]
    }
)
def download_image(url: str, save_path: str) -> str:
    p = Path(save_path)
    if not p.is_absolute():
        p = Path(config.PROJECT_ROOT) / p
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={
            "User-Agent": "HollywoodAgentBot/1.0 (archival photo documentary)"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        p.write_bytes(data)
        return json.dumps({"success": True, "path": str(p), "size_bytes": len(data)})
    except Exception as e:
        return json.dumps({"error": str(e)})


@register_tool(
    name="create_actors_json",
    description="Create or update the actors.json manifest with a list of persons, their photo URLs, dates, and attribution.",
    parameters={
        "type": "object",
        "properties": {
            "output_path": {
                "type": "string",
                "description": "Path to write the actors.json file."
            },
            "actors": {
                "type": "array",
                "description": "List of actor records.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "then_year": {"type": "integer"},
                        "now_year": {"type": "integer"},
                        "then_photo_url": {"type": "string"},
                        "now_photo_url": {"type": "string"},
                        "then_source": {"type": "string"},
                        "now_source": {"type": "string"},
                        "then_license": {"type": "string"},
                        "now_license": {"type": "string"},
                        "then_artist": {"type": "string"},
                        "now_artist": {"type": "string"},
                    },
                    "required": ["name", "then_year", "now_year"]
                }
            }
        },
        "required": ["output_path", "actors"]
    }
)
def create_actors_json(output_path: str, actors: list) -> str:
    p = Path(output_path)
    if not p.is_absolute():
        p = Path(config.PROJECT_ROOT) / p
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(actors, indent=2, ensure_ascii=False), encoding="utf-8")
        return json.dumps({"success": True, "path": str(p), "actor_count": len(actors)})
    except Exception as e:
        return json.dumps({"error": str(e)})


@register_tool(
    name="report_status",
    description="Report progress or final status to the user. Use this to communicate what has been done and what's next.",
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["in_progress", "completed", "error", "waiting_for_input"],
                "description": "Current status."
            },
            "message": {
                "type": "string",
                "description": "Human-readable status message."
            },
            "steps_completed": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of completed steps."
            },
            "next_steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of upcoming steps."
            }
        },
        "required": ["status", "message"]
    }
)
def report_status(status: str, message: str, steps_completed: list = None, next_steps: list = None) -> str:
    report = {
        "status": status,
        "message": message,
        "steps_completed": steps_completed or [],
        "next_steps": next_steps or [],
    }
    # Print to console for user visibility
    print(f"\n{'='*60}")
    print(f"  AGENT STATUS: {status.upper()}")
    print(f"  {message}")
    if steps_completed:
        print(f"  Completed: {', '.join(steps_completed)}")
    if next_steps:
        print(f"  Next: {', '.join(next_steps)}")
    print(f"{'='*60}\n")
    return json.dumps(report)


# ─────────────────────────────────────────────────────────────
# Helper: Execute a tool call from the LLM response
# ─────────────────────────────────────────────────────────────

def execute_tool_call(tool_name: str, arguments: dict) -> str:
    """Execute a registered tool and return the result as a string."""
    func = TOOL_FUNCTIONS.get(tool_name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        return func(**arguments)
    except TypeError as e:
        return json.dumps({"error": f"Invalid arguments for {tool_name}: {e}"})
    except Exception as e:
        return json.dumps({"error": f"Tool execution failed: {e}"})


# ─────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Registered {len(TOOL_SCHEMAS)} tools:")
    for t in TOOL_SCHEMAS:
        print(f"  - {t['function']['name']}: {t['function']['description'][:60]}...")
    print()

    # Test list_directory
    print("Testing list_directory('.'):")
    result = list_directory(".")
    data = json.loads(result)
    for item in data.get("items", [])[:5]:
        print(f"  {item['type']:4s}  {item['name']}")

    # Test search_wikimedia
    print("\nTesting search_wikimedia('Tom Cruise portrait'):")
    result = search_wikimedia("Tom Cruise portrait", limit=3)
    data = json.loads(result)
    for r in data.get("results", []):
        print(f"  {r['title'][:50]}  license={r['license']}")

    print("\nAll tools OK!")
