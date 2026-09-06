"""Command-line interface for the source-to-original workflow."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .errors import RemakeAgentError
from .planner import CreateProjectRequest, create_project, ledger_is_complete, update_review
from .renderer import render_project
from .rights import ALLOWED_RIGHTS, RightsDeclaration
from .source import inspect_source


def _json_print(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _remake_command(args: argparse.Namespace) -> int:
    declaration = RightsDeclaration(args.rights, args.confirm_rights, args.rights_evidence)
    source = inspect_source(args.url, allow_network=not args.no_network)
    request = CreateProjectRequest(
        source=source,
        declaration=declaration,
        topic=args.topic,
        angle=args.angle,
        language=args.language,
        duration_seconds=args.duration,
        output_root=Path(args.output_root),
        project_name=args.project_name,
    )
    project = create_project(request)
    result = {
        "project": str(project),
        "metadata_fetched": source.fetched,
        "metadata_warning": source.fetch_warning,
        "next": "Run `python -m remake_agent review --project PROJECT ...` after you add original narration and your asset ledger.",
    }
    if args.render:
        result["draft_video"] = str(render_project(project, duration_seconds=args.duration, resolution=args.resolution, fps=args.fps))
    _json_print(result)
    return 0


def _render_command(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    output = render_project(project, duration_seconds=args.duration, resolution=args.resolution, fps=args.fps)
    _json_print({"draft_video": str(output), "notice": "Silent procedural draft only; it is not upload-ready."})
    return 0


def _review_command(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    actual_ledger_complete = ledger_is_complete(project)
    report = update_review(
        project,
        has_original_voiceover=args.has_original_voiceover,
        assets_ledger_complete=args.assets_ledger_complete and actual_ledger_complete,
        realistic_ai=args.realistic_ai,
    )
    report["ledger_file_complete"] = actual_ledger_complete
    if args.assets_ledger_complete and not actual_ledger_complete:
        report["ledger_warning"] = "--assets-ledger-complete was supplied, but rights_ledger.csv is empty or has missing required fields."
    _json_print(report)
    return 0 if report["publish_ready"] else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="remake-agent",
        description="Create an original, rights-gated video project from a public reference URL without downloading source media.",
    )
    parser.add_argument("--version", action="version", version=f"remake-agent {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    remake = commands.add_parser("remake", help="create a safe original-first project from a reference URL")
    remake.add_argument("url", help="Public http(s) link. Metadata only; video/audio/captions/thumbnails are never downloaded.")
    remake.add_argument("--rights", required=True, choices=sorted(ALLOWED_RIGHTS), help="Your rights basis for planned use.")
    remake.add_argument("--confirm-rights", action="store_true", help="Required explicit attestation that you have the necessary rights.")
    remake.add_argument("--rights-evidence", help="Local evidence file or stable reference URL/ID. Required for licensed, permission, cc, and public-domain claims.")
    remake.add_argument("--topic", help="Working topic. Defaults to safe public metadata when available.")
    remake.add_argument("--angle", help="Your independent editorial angle (not a source-video rewrite).")
    remake.add_argument("--language", choices=["vi", "en"], default="vi")
    remake.add_argument("--duration", type=int, default=45, help="Draft duration in seconds, 15–3600 (default: 45).")
    remake.add_argument("--output-root", default="projects", help="Folder in which a new project directory is made.")
    remake.add_argument("--project-name", help="Optional readable project folder prefix.")
    remake.add_argument("--no-network", action="store_true", help="Do not fetch public metadata; useful for offline/CI use.")
    remake.add_argument("--render", action="store_true", help="Immediately render a silent, procedural MP4 draft.")
    remake.add_argument("--resolution", default="1280x720", help="Render resolution, e.g. 1280x720.")
    remake.add_argument("--fps", type=int, default=24, help="Render frame rate (12–60).")
    remake.set_defaults(handler=_remake_command)

    render = commands.add_parser("render", help="render the project’s media-free visual draft")
    render.add_argument("--project", required=True, help="Project folder created by the remake command.")
    render.add_argument("--duration", type=int, help="Override configured duration, in seconds (5–3600).")
    render.add_argument("--resolution", default="1280x720")
    render.add_argument("--fps", type=int, default=24)
    render.set_defaults(handler=_render_command)

    review = commands.add_parser("review", help="update the transparent pre-publish gate")
    review.add_argument("--project", required=True, help="Project folder created by the remake command.")
    review.add_argument("--has-original-voiceover", action="store_true", help="Attest that final narration/commentary is genuinely original and rights-cleared.")
    review.add_argument("--assets-ledger-complete", action="store_true", help="Request asset-ledger validation; all required CSV fields must be filled.")
    review.add_argument("--realistic-ai", action="store_true", help="Mark that realistic/meaningful AI material is present; a Studio disclosure remains required.")
    review.set_defaults(handler=_review_command)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        status = args.handler(args)
    except RemakeAgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        status = 2
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        status = 130
    raise SystemExit(status)
