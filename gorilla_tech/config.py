"""
Gorilla Tech style agent — central configuration.

Everything here can be overridden with environment variables so the same code
runs on a laptop, in a sandbox and in GitHub Actions:

    GT_LLM_API_BASE / GT_LLM_API_KEY / GT_LLM_MODEL   LLM gateway (OpenAI-compatible)
    GT_TTS_PROVIDER                                   edge | elevenlabs | openai | none
    GT_RESOLUTION                                     720p | 1080p
    GT_TARGET_MINUTES                                 video length in minutes
    GT_LANG                                           es | en | vi
    GT_VOICE                                          override TTS voice name
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────
PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
PROJECTS_DIR = Path(os.environ.get("GT_PROJECTS_DIR", PACKAGE_ROOT / "projects"))
CACHE_DIR = PACKAGE_ROOT / "cache"
TEMPLATE_DIR = PACKAGE_ROOT / "templates"
FONT_DIRS = [
    Path(os.environ["GT_FONT_DIR"]) if os.environ.get("GT_FONT_DIR") else None,
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/dejavu"),
    Path("/Library/Fonts"),
    Path("C:/Windows/Fonts"),
    PACKAGE_ROOT / "assets" / "fonts",
]
FONT_DIRS = [p for p in FONT_DIRS if p]

# ── LLM (OpenAI-compatible gateway) ───────────────────────────
def _legacy_key() -> str:
    """Fall back to the key already used by the Hollywood agent in this repo."""
    try:
        import sys

        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        import config as legacy_config  # noqa: WPS433  (repo root config.py)

        return getattr(legacy_config, "API_KEY", "")
    except Exception:
        return ""


LLM_API_BASE = os.environ.get(
    "GT_LLM_API_BASE",
    os.environ.get("OPENAI_BASE_URL", "https://api.experientiallabs.ai/v1"),
).rstrip("/")
LLM_API_KEY = (
    os.environ.get("GT_LLM_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or _legacy_key()
)
LLM_MODEL = os.environ.get("GT_LLM_MODEL", "claude-fable-5.1")
LLM_MAX_TOKENS = int(os.environ.get("GT_LLM_MAX_TOKENS", "8000"))
LLM_TEMPERATURE = float(os.environ.get("GT_LLM_TEMPERATURE", "1.0"))
LLM_TIMEOUT = int(os.environ.get("GT_LLM_TIMEOUT", "240"))
LLM_RETRIES = 4

# ── Language profiles ─────────────────────────────────────────
# chars_per_sec is only used when no real TTS timing is available (offline mode).
LANGUAGES = {
    "es": {
        "label": "Español",
        "tts_voices": ["es-MX-JorgeNeural", "es-ES-AlvaroNeural", "es-AR-ElenaNeural"],
        "chars_per_sec": 16.0,
        "subtitle_lang": "es",
        "number_locale": "es",
    },
    "en": {
        "label": "English",
        "tts_voices": ["en-US-GuyNeural", "en-US-ChristopherNeural", "en-GB-RyanNeural"],
        "chars_per_sec": 15.2,
        "subtitle_lang": "en",
        "number_locale": "en",
    },
    "vi": {
        "label": "Tiếng Việt",
        "tts_voices": ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural"],
        "chars_per_sec": 13.5,
        "subtitle_lang": "vi",
        "number_locale": "vi",
    },
}
DEFAULT_LANG = os.environ.get("GT_LANG", "es")

# ── Text to speech ────────────────────────────────────────────
TTS_PROVIDER = os.environ.get("GT_TTS_PROVIDER", "edge")  # edge|elevenlabs|openai|none
TTS_VOICE = os.environ.get("GT_VOICE", "")  # empty -> first voice of the language
TTS_RATE = os.environ.get("GT_TTS_RATE", "-4%")  # documentary pacing
TTS_PITCH = os.environ.get("GT_TTS_PITCH", "-2Hz")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

# ── Video spec ────────────────────────────────────────────────
RESOLUTIONS = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "vertical": (1080, 1920),
}
RESOLUTION = os.environ.get("GT_RESOLUTION", "1080p")
FPS = int(os.environ.get("GT_FPS", "30"))
TARGET_MINUTES = float(os.environ.get("GT_TARGET_MINUTES", "13"))
XFADE_SEC = 0.6  # cross dissolve between scenes
SCENE_PAD_SEC = 0.35  # silence padding after each narration block
CRF = int(os.environ.get("GT_CRF", "22"))
X264_PRESET = os.environ.get("GT_PRESET", "veryfast")
RENDER_WORKERS = int(os.environ.get("GT_WORKERS", str(min(4, (os.cpu_count() or 2)))))

# ── Look & feel (channel-style palette) ───────────────────────
PALETTE = {
    "bg_top": (9, 12, 18),
    "bg_bottom": (3, 5, 8),
    "panel": (16, 21, 30),
    "panel_edge": (43, 54, 71),
    "grid": (35, 46, 62),
    "accent": (255, 92, 42),      # warm signal orange
    "accent_alt": (58, 190, 255),  # radar cyan
    "danger": (232, 54, 54),
    "friendly": (96, 214, 132),
    "text": (238, 242, 247),
    "muted": (154, 167, 184),
    "gold": (255, 199, 69),
}
FONT_BOLD = os.environ.get("GT_FONT_BOLD", "DejaVuSans-Bold.ttf")
FONT_REGULAR = os.environ.get("GT_FONT_REGULAR", "DejaVuSans.ttf")
FONT_MONO = os.environ.get("GT_FONT_MONO", "DejaVuSansMono-Bold.ttf")

# ── Research sources ──────────────────────────────────────────
USER_AGENT = "GorillaTechVideoAgent/1.0 (educational documentary; contact: repo owner)"
WIKIPEDIA_API = "https://{lang}.wikipedia.org/w/api.php"
WIKIPEDIA_REST = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HTTP_TIMEOUT = 20
HTTP_RETRIES = 3
IMAGE_MIN_WIDTH = 640
# Only these licences are acceptable for downloaded photos.
ALLOWED_LICENSES = (
    "cc0", "public domain", "cc-by-4.0", "cc-by-3.0", "cc-by-sa-4.0",
    "cc-by-sa-3.0", "cc-by-2.0", "cc-by-2.5", "gfdl",
)

# ── Image generation fallback (optional) ──────────────────────
# Used only when no CC photo matches a scene. Leave empty -> procedural graphics.
IMAGE_GEN_API_BASE = os.environ.get("GT_IMAGE_API_BASE", "")
IMAGE_GEN_API_KEY = os.environ.get("GT_IMAGE_API_KEY", "")
IMAGE_GEN_MODEL = os.environ.get("GT_IMAGE_MODEL", "")

# ── Agent safety ──────────────────────────────────────────────
MAX_AGENT_ITERATIONS = int(os.environ.get("GT_MAX_ITER", "40"))
MAX_TOOL_RESULT_CHARS = 1800
MAX_CONTEXT_MESSAGES = 18


def video_size(resolution: str | None = None) -> tuple[int, int]:
    return RESOLUTIONS.get(resolution or RESOLUTION, RESOLUTIONS["1080p"])


def language(lang: str | None = None) -> dict:
    return LANGUAGES.get((lang or DEFAULT_LANG).lower(), LANGUAGES["es"])


def voice_for(lang: str) -> str:
    if TTS_VOICE:
        return TTS_VOICE
    return language(lang)["tts_voices"][0]
