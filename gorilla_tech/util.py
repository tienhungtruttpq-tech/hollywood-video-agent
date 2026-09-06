"""Shared helpers: logging, JSON IO, resilient HTTP, ffmpeg & font discovery."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

import config

# ── Logging ───────────────────────────────────────────────────

_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def log(stage: str, message: str = "", level: str = "info") -> None:
    colors = {"info": "36", "ok": "32", "warn": "33", "error": "31", "step": "35"}
    stamp = time.strftime("%H:%M:%S")
    tag = _c(colors.get(level, "37"), f"{stage:<12}")
    line = f"[{stamp}] {tag} {message}"
    print(line, flush=True)


def ok(stage: str, message: str = "") -> None:
    log(stage, message, "ok")


def warn(stage: str, message: str = "") -> None:
    log(stage, message, "warn")


def fail(stage: str, message: str = "") -> None:
    log(stage, message, "error")


def step(message: str) -> None:
    print("\n" + _c("1;35", "═" * 68), flush=True)
    print(_c("1;35", f"  {message}"), flush=True)
    print(_c("1;35", "═" * 68), flush=True)


# ── JSON / filesystem ─────────────────────────────────────────

def read_json(path: Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        warn("json", f"cannot parse {path.name}: {exc}")
        return default


def write_json(path: Path, data: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_text(path: Path, text: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def slugify(text: str, max_len: int = 48) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "video"


def file_hash(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()[:16]


def data_hash(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()[:16]


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.0f}{unit}" if unit == "B" else f"{num_bytes:.1f}{unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f}TB"


def clock(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    minutes, secs = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:d}:{secs:02d}"


def srt_time(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ── Number formatting (locale aware, dependency free) ─────────

_THOUSANDS = {"es": ".", "en": ",", "vi": "."}
_DECIMALS = {"es": ",", "en": ".", "vi": ","}


def format_number(value: float, lang: str = "es", decimals: int | None = None) -> str:
    locale = config.language(lang).get("number_locale", lang)
    group = _THOUSANDS.get(locale, ".")
    point = _DECIMALS.get(locale, ",")
    if decimals is None:
        decimals = 0 if abs(value - round(value)) < 1e-9 else 2
    negative = value < 0
    integer, _, fraction = f"{abs(value):.{decimals}f}".partition(".")
    groups: list[str] = []
    rest = integer
    while rest:
        groups.insert(0, rest[-3:])
        rest = rest[:-3]
    grouped = group.join(groups) or "0"
    text = grouped + (point + fraction if fraction else "")
    return ("-" if negative else "") + text


# ── HTTP with retries + offline detection ─────────────────────

class OfflineError(RuntimeError):
    """Raised when the sandbox/runner has no usable network route."""


_NET_STATE = {"online": None, "checked_at": 0.0}


def probe_network(url: str = "https://pypi.org/simple/", timeout: float = 6.0) -> bool:
    """Cheap connectivity probe; result cached for 5 minutes."""
    if _NET_STATE["online"] is not None and time.time() - _NET_STATE["checked_at"] < 300:
        return bool(_NET_STATE["online"])
    try:
        request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            online = response.status < 500
    except Exception:
        online = False
    _NET_STATE.update({"online": online, "checked_at": time.time()})
    return online


def http_get(url: str, timeout: int | None = None, as_json: bool = False,
             headers: dict | None = None, retries: int | None = None) -> Any:
    """GET a URL. Raises OfflineError when the network is unavailable."""
    timeout = timeout or config.HTTP_TIMEOUT
    retries = config.HTTP_RETRIES if retries is None else retries
    head = {"User-Agent": config.USER_AGENT}
    if headers:
        head.update(headers)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=head)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
            if as_json:
                return json.loads(payload.decode("utf-8"))
            return payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in (403, 404, 410):
                raise
            time.sleep(1.5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(1.0 * (attempt + 1))
    raise OfflineError(f"GET failed for {url}: {last_error}")


def http_post_json(url: str, body: dict, timeout: int | None = None,
                   headers: dict | None = None, retries: int | None = None) -> dict:
    timeout = timeout or config.LLM_TIMEOUT
    retries = config.LLM_RETRIES if retries is None else retries
    head = {"Content-Type": "application/json", "User-Agent": config.USER_AGENT}
    if headers:
        head.update(headers)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, data=data, headers=head, method="POST")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400] if exc.fp else ""
            last_error = RuntimeError(f"HTTP {exc.code}: {detail}")
            if exc.code == 429 or exc.code >= 500:
                wait = 20 * (attempt + 1)
                warn("http", f"{exc.code} — retrying in {wait}s ({attempt + 1}/{retries})")
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise OfflineError(f"POST failed for {url}: {last_error}")


def download_file(url: str, destination: Path, min_bytes: int = 1024) -> Path:
    payload = http_get(url, timeout=60)
    if len(payload) < min_bytes:
        raise OfflineError(f"{url} returned only {len(payload)} bytes")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return destination


# ── ffmpeg / fonts ────────────────────────────────────────────

_FFMPEG: str | None = None


def ffmpeg_exe() -> str:
    global _FFMPEG
    if _FFMPEG:
        return _FFMPEG
    found = shutil.which("ffmpeg")
    if not found:
        try:
            import imageio_ffmpeg

            found = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "ffmpeg not found. Install ffmpeg or `pip install imageio-ffmpeg`."
            ) from exc
    _FFMPEG = found
    return found


def ffprobe_exe() -> str | None:
    return shutil.which("ffprobe")


def run_ffmpeg(args: Iterable[str], quiet: bool = True, timeout: int = 3600) -> subprocess.CompletedProcess:
    command = [ffmpeg_exe(), "-hide_banner", *(["-loglevel", "error", "-nostats"] if quiet else []), *args]
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def media_duration(path: Path) -> float:
    """Duration of an audio/video file, measured with ffmpeg (no ffprobe needed)."""
    result = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, timeout=120,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


_FONT_CACHE: dict[str, Path] = {}


def find_font(name: str) -> Path | None:
    if name in _FONT_CACHE:
        return _FONT_CACHE[name]
    for directory in config.FONT_DIRS:
        candidate = Path(directory) / name
        if candidate.exists():
            _FONT_CACHE[name] = candidate
            return candidate
    for directory in config.FONT_DIRS:
        directory = Path(directory)
        if not directory.exists():
            continue
        for candidate in directory.rglob(name):
            _FONT_CACHE[name] = candidate
            return candidate
    _FONT_CACHE[name] = None  # type: ignore[assignment]
    return None


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)
