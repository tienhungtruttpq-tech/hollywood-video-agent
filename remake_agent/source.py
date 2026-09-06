"""Safe, metadata-only source inspection.

The inspector never downloads video, audio, captions, thumbnails, or media streams.
It only records small public page metadata to seed an original project brief.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from html import unescape
from html.parser import HTMLParser
from ipaddress import ip_address
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import socket

from .errors import RemakeAgentError

MAX_METADATA_BYTES = 512 * 1024
USER_AGENT = "SourceToOriginalVideoAgent/0.1 (+metadata-only)"


@dataclass
class SourceMetadata:
    url: str
    provider: str
    title: str | None = None
    author_name: str | None = None
    video_id: str | None = None
    fetched: bool = False
    fetch_warning: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _is_public_host(hostname: str) -> bool:
    if not hostname:
        return False
    lowered = hostname.rstrip(".").lower()
    if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith(".local"):
        return False
    try:
        candidates = socket.getaddrinfo(lowered, None, type=socket.SOCK_STREAM)
    except OSError:
        # An unresolvable hostname is not known to be private. Network access later
        # will produce a controlled warning.
        return True
    addresses = {candidate[4][0] for candidate in candidates}
    for address in addresses:
        ip = ip_address(address)
        if not ip.is_global:
            return False
    return True


def validate_source_url(raw_url: str) -> str:
    value = raw_url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise RemakeAgentError("Source URL must begin with http:// or https://.")
    if not parsed.netloc or parsed.username or parsed.password:
        raise RemakeAgentError("Source URL must use a normal public hostname (no credentials).")
    if not _is_public_host(parsed.hostname or ""):
        raise RemakeAgentError("Private, loopback, and local-network source URLs are not allowed.")
    return value


def _youtube_video_id(parsed) -> str | None:
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host == "youtu.be":
        return parsed.path.strip("/").split("/")[0] or None
    if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/"):
            return parsed.path.strip("/").split("/")[1]
    return None


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.title: str | None = None
        self._inside_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): (value or "") for key, value in attrs}
        if tag.lower() == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            content = values.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = unescape(content)
        if tag.lower() == "title":
            self._inside_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False
            title = "".join(self._title_parts).strip()
            if title:
                self.title = unescape(title)

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._title_parts.append(data)


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_source_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_text(url: str) -> str:
    opener = build_opener(_SafeRedirectHandler())
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.1"},
    )
    with opener.open(request, timeout=12) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/json", "application/xhtml+xml"}:
            raise RemakeAgentError(f"Metadata endpoint returned unsupported content type: {content_type}")
        data = response.read(MAX_METADATA_BYTES + 1)
    if len(data) > MAX_METADATA_BYTES:
        raise RemakeAgentError("Metadata page exceeds the safe inspection limit.")
    return data.decode("utf-8", errors="replace")


def _provider_for(parsed) -> str:
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}:
        return "youtube"
    if host in {"vimeo.com", "player.vimeo.com"}:
        return "vimeo"
    return "web"


def inspect_source(raw_url: str, *, allow_network: bool = True) -> SourceMetadata:
    """Validate a public link and fetch title/author metadata only.

    Network failures do not discard an otherwise valid project: the warning is saved
    and the user can supply --topic explicitly.
    """
    url = validate_source_url(raw_url)
    parsed = urlparse(url)
    provider = _provider_for(parsed)
    source = SourceMetadata(url=url, provider=provider, video_id=_youtube_video_id(parsed))
    if not allow_network:
        source.fetch_warning = "Metadata fetch disabled by --no-network."
        return source

    try:
        if provider == "youtube" and source.video_id:
            # oEmbed supplies title/author metadata; it has no downloadable media payload.
            import json

            oembed = "https://www.youtube.com/oembed?url=" + quote(url, safe="") + "&format=json"
            data = json.loads(_fetch_text(oembed))
            source.title = str(data.get("title") or "").strip() or None
            source.author_name = str(data.get("author_name") or "").strip() or None
        else:
            # Channels, playlists and normal web pages do not necessarily support
            # oEmbed. Parse only their small public HTML metadata fields.
            parser = _MetadataParser()
            parser.feed(_fetch_text(url))
            source.title = parser.meta.get("og:title") or parser.meta.get("twitter:title") or parser.title
            source.author_name = parser.meta.get("author") or parser.meta.get("article:author")
        source.fetched = True
    except (HTTPError, URLError, TimeoutError, ValueError, RemakeAgentError, OSError) as exc:
        source.fetch_warning = f"Metadata was not fetched: {str(exc)[:240]}"
    return source
