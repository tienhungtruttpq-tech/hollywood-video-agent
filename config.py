"""Configuration for the legacy Hollywood Video Agent.

Secrets are intentionally read from the environment so they are never committed.
"""

import os

# ── API Settings ────────────────────────────────────────────────────────────
API_BASE_URL = os.environ.get("EXPERIENTIAL_LABS_API_BASE_URL", "https://api.experientiallabs.ai/v1")
API_KEY = os.environ.get("EXPERIENTIAL_LABS_API_KEY")
MODEL = os.environ.get("EXPERIENTIAL_LABS_MODEL", "claude-fable-5.1")
MAX_TOKENS = 4096
TEMPERATURE = 1.0  # Fable 5.1 only supports temperature=1.0

# ── Project Settings ────────────────────────────────────────────────────────
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
