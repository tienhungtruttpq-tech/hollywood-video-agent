#!/usr/bin/env python3
"""
Phase 2: Call Fable 5.1 ONCE to generate narrative.json and render.py.
No search/download — only creative writing.
Expected token usage: ~10-15K (vs 100K+ with full agent loop).
"""

import json, urllib.request, sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent / "new_project"

API_URL = "https://api.experientiallabs.ai/v1/chat/completions"
API_KEY = "xpl_320150294b7bb52f84440d0116a33cea25b3f7e6"

actors = json.loads((PROJECT / "actors.json").read_text())
actor_names = [a["name"] for a in actors]

PROMPT = f"""You have 7 Hollywood actors with "then" and "now" photos ready. Write two things:

## ACTORS (with photos already downloaded):
{json.dumps(actor_names)}

## TASK 1: narrative.json
Write a JSON file with this structure:
```json
{{
  "title": "Hollywood Stars: Then & Now",
  "intro": "A short intro sentence",
  "actors": [
    {{
      "name": "Actor Name",
      "narration": "2-3 sentence narration about their career, mentioning notable films"
    }}
  ],
  "outro": "A short outro sentence"
}}
```

## TASK 2: render.py
Write a COMPLETE Python script that:
1. Reads actors.json and narrative.json from the current directory
2. For each actor, loads their then_photo and now_photo from assets/photos/
3. Renders a 1280x720 video at 30fps using Pillow and imageio-ffmpeg
4. Layout: dark background, THEN photo on left, NOW photo on right (each ~480x480)
5. Actor name in large white text centered above photos
6. Narration text in smaller text below photos
7. "THEN" and "NOW" labels above each photo
8. Smooth fade-in/fade-out transitions between actors (15 seconds per actor)
9. 5-second title card at start, 5-second outro card at end
10. Saves output to output/Hollywood_Then_Now.mp4
11. Uses only: Pillow, numpy, imageio-ffmpeg (no OpenCV needed)
12. Must work on Windows

Output EXACTLY in this format (no markdown, no explanation):

===NARRATIVE_JSON===
(the complete narrative.json content)
===RENDER_PY===
(the complete render.py content)
===END==="""

print("Calling Fable 5.1 for narrative + render script...", flush=True)

body = json.dumps({
    "model": "claude-fable-5.1",
    "messages": [{"role": "user", "content": PROMPT}],
    "max_tokens": 8000,
    "temperature": 1.0,
}).encode()

req = urllib.request.Request(API_URL, data=body, headers={
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}, method="POST")

try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read().decode())
except Exception as e:
    print(f"API Error: {e}", flush=True)
    sys.exit(1)

content = result["choices"][0]["message"]["content"]
usage = result.get("usage", {})
print(f"Tokens: {usage.get('prompt_tokens', '?')} prompt + {usage.get('completion_tokens', '?')} completion = {usage.get('total_tokens', '?')} total", flush=True)

# Parse response
if "===NARRATIVE_JSON===" in content and "===RENDER_PY===" in content:
    parts = content.split("===NARRATIVE_JSON===")[1]
    narrative_str = parts.split("===RENDER_PY===")[0].strip()
    render_str = parts.split("===RENDER_PY===")[1].split("===END===")[0].strip()
    
    # Save narrative.json
    (PROJECT / "narrative.json").write_text(narrative_str, encoding="utf-8")
    print(f"Saved: narrative.json ({len(narrative_str)} bytes)", flush=True)
    
    # Save render.py
    (PROJECT / "render.py").write_text(render_str, encoding="utf-8")
    print(f"Saved: render.py ({len(render_str)} bytes)", flush=True)
    
    print("\nDone! Next: python new_project/render.py", flush=True)
else:
    print("ERROR: Could not parse response. Raw output:", flush=True)
    print(content[:2000], flush=True)
    # Save raw for debugging
    (PROJECT / "raw_response.txt").write_text(content, encoding="utf-8")
