"""
Configuration for the Hollywood Video Agent.
Uses Claude Fable 5.1 via Experiential Labs (OpenAI-compatible gateway).
"""

# ── API Settings ──────────────────────────────────────────────
API_BASE_URL = "https://api.experientiallabs.ai/v1"
API_KEY = "xpl_320150294b7bb52f84440d0116a33cea25b3f7e6"
MODEL = "claude-fable-5.1"
MAX_TOKENS = 4096
TEMPERATURE = 1.0  # Fable 5.1 only supports temperature=1.0

# ── Project Settings ──────────────────────────────────────────
import os
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Default topic if none provided
DEFAULT_TOPIC = "Hollywood Actors Then and Now"

# Video output settings
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS = 30
VIDEO_DURATION_SEC = 480  # 8 minutes

# Max agent iterations (safety limit)
MAX_AGENT_ITERATIONS = 30
