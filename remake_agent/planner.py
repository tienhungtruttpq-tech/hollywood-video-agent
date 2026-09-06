"""Create a transparent, original-first project pack from a reference URL."""
from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import RemakeAgentError
from .rights import REQUIRED_ASSET_COLUMNS, RightsDeclaration, compliance_checks, evidence_record, publishing_ready
from .source import SourceMetadata

PROJECT_SCHEMA_VERSION = "1.0"


@dataclass
class CreateProjectRequest:
    source: SourceMetadata
    declaration: RightsDeclaration
    topic: str | None
    angle: str | None
    language: str
    duration_seconds: int
    output_root: Path
    project_name: str | None = None


def _one_line(value: str | None, limit: int = 140) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "")).strip()
    return cleaned[:limit]


def slugify(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (result or "original-video")[:60]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _story(topic: str, angle: str, language: str) -> tuple[str, list[dict[str, str]]]:
    """Draft an original *structure*, never a reconstruction of source material.

    The draft intentionally contains no source transcript, scene sequence, quotes, or
    copied visual/audio plan. The creator must replace fact prompts after research.
    """
    if language == "vi":
        title = f"{topic}: một góc nhìn mới"
        cards = [
            {
                "kicker": "BẢN THẢ GỐC",
                "headline": title,
                "body": "Một video mới được xây từ câu hỏi riêng, không sao chép cảnh, âm thanh hay lời thoại của video tham chiếu.",
            },
            {
                "kicker": "CÂU HỎI",
                "headline": "Ta thực sự cần hiểu điều gì?",
                "body": f"Góc tiếp cận: {angle}. Hãy nêu vấn đề bằng trải nghiệm và lập luận của chính bạn.",
            },
            {
                "kicker": "NGHIÊN CỨU",
                "headline": "Ba lăng kính độc lập",
                "body": "Thay các ô này bằng dữ kiện đã kiểm chứng, nguồn gốc rõ ràng và ví dụ do bạn tự sản xuất hoặc có giấy phép.",
            },
            {
                "kicker": "GIÁ TRỊ MỚI",
                "headline": "Phân tích, không lặp lại",
                "body": "Đưa ra so sánh, bài học hoặc phản biện mới. Ghi âm lời bình nguyên bản bằng giọng của bạn hoặc người đã cấp quyền.",
            },
            {
                "kicker": "KẾT",
                "headline": "Một kết luận của riêng bạn",
                "body": "Kiểm tra lần cuối: từng hình, nhạc và đoạn tiếng đều có quyền sử dụng; mô tả rõ đóng góp gốc của kênh.",
            },
        ]
        narration = "\n\n".join(
            [
                f"[MỞ ĐẦU — viết mới] Hôm nay, chúng ta nhìn {topic} từ một góc khác: {angle}.",
                "[LUẬN ĐIỂM 1 — bổ sung dữ kiện đã kiểm chứng] Không lặp lại cấu trúc, lời thoại hoặc trình tự của video tham chiếu.",
                "[LUẬN ĐIỂM 2 — phân tích của bạn] Nêu ví dụ mà bạn tự quay, tự thiết kế hoặc có giấy phép sử dụng thương mại rõ ràng.",
                "[KẾT — viết mới] Mời khán giả đánh giá lập luận này và xem các nguồn được ghi minh bạch bên dưới.",
            ]
        )
    else:
        title = f"{topic}: a new perspective"
        cards = [
            {
                "kicker": "ORIGINAL DRAFT",
                "headline": title,
                "body": "This is a newly structured video. It does not copy scenes, audio, or wording from the reference video.",
            },
            {
                "kicker": "THE QUESTION",
                "headline": "What is worth understanding?",
                "body": f"Approach: {angle}. Frame the subject through your own experience and reasoning.",
            },
            {
                "kicker": "RESEARCH",
                "headline": "Three independent lenses",
                "body": "Replace these prompts with verified facts, clear sources, and examples you created or licensed yourself.",
            },
            {
                "kicker": "NEW VALUE",
                "headline": "Analyse, do not repeat",
                "body": "Add a genuinely new comparison, lesson, or critique. Record original commentary in your own voice or with permission.",
            },
            {
                "kicker": "CLOSE",
                "headline": "Reach your own conclusion",
                "body": "Before publishing, confirm the rights for every visual, music cue, and spoken segment and explain your original contribution.",
            },
        ]
        narration = "\n\n".join(
            [
                f"[OPEN — write fresh] Today we explore {topic} through a different lens: {angle}.",
                "[POINT ONE — add verified facts] Do not repeat the reference video’s wording, structure, or sequence.",
                "[POINT TWO — your analysis] Use examples you filmed, designed, or licensed with commercial-use terms.",
                "[CLOSE — write fresh] Invite viewers to assess this argument and consult the transparently listed sources below.",
            ]
        )
    return narration, cards


def _project_readme(project_name: str) -> str:
    return f"""# {project_name}

This project was generated by **Source-to-Original Video Agent**. It uses the supplied URL as a reference record only. The workflow does **not** download, extract, transcribe, or reuse source video/audio/captions/thumbnails.

## Before a public upload

1. Replace the prompts in `script.md` with independently researched, original narration.
2. Add every visual, clip, track and voice asset to `rights_ledger.csv`; retain your underlying licence/permission evidence privately.
3. Add substantial original commentary, analysis or an on-camera contribution. Permission alone does not make a minimal edit safe for YouTube reused-content/YPP review.
4. From the repository checkout (or after installing the CLI), run `python -m remake_agent review --project /absolute/path/to/this-project --has-original-voiceover --assets-ledger-complete`.
5. If you used realistic or meaningfully altered AI content, run review with `--realistic-ai` and select YouTube Studio's altered/synthetic-content disclosure during upload.
6. Do a final human legal, factual, Community Guidelines, and Copyright review. This tool cannot make a legal determination or guarantee monetisation/Content ID outcomes.

## Render a fast visual draft

```bash
python -m remake_agent render --project /absolute/path/to/this-project --duration 45
```

The renderer creates procedural typography/motion backgrounds only. It never uses the source’s media. The silent output is a **draft**, not an upload-ready substitute for original narration, licensed assets, and a human review.

## Important project files

- `source_record.json` — metadata-only source record and your rights declaration.
- `compliance_report.json` — transparent gate status; update it with `review`.
- `script.md` — original-first script structure, not a rewritten transcript.
- `render_config.json` — editable card copy for the safe, media-free draft renderer.
- `rights_ledger.csv` — required attribution and licence ledger.
- `publish_checklist.md` — manual upload checks.
"""


def _publish_checklist(language: str) -> str:
    # Bilingual labels work well for teams whose project language varies.
    return """# Publish checklist / Danh sách kiểm tra trước khi đăng

- [ ] I confirmed that I have all required rights for every element in the final export. A credit or a disclaimer alone is not permission.
- [ ] I did not use a downloaded/ripped source video, its audio, captions, thumbnail, or a near-identical scene-by-scene/script rewrite unless my documented licence explicitly permits it.
- [ ] The final video adds substantial original commentary, analysis, education, entertainment value, or creator participation; it is not a mass-produced template variant.
- [ ] `rights_ledger.csv` lists every third-party visual, footage clip, music track, voice, font, and AI asset together with its terms and attribution.
- [ ] I checked factual claims, privacy, defamation, safety, Community Guidelines, and local law.
- [ ] If realistic or meaningfully altered/synthetic people, events, places, music, or voices appear, I will select YouTube Studio’s altered/synthetic-content disclosure.
- [ ] I understand this tool’s pass state is a workflow check, not a legal opinion, a copyright clearance, a YouTube approval, or a YPP monetisation guarantee.

## Official references (check before every release)

- YouTube channel monetisation policies: https://support.google.com/youtube/answer/1311392
- Copyright myths and permissions: https://support.google.com/youtube/answer/2797449
- Altered/synthetic content disclosure: https://support.google.com/youtube/answer/14328491
"""


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def create_project(request: CreateProjectRequest) -> Path:
    errors = request.declaration.errors()
    if errors:
        raise RemakeAgentError("Compliance gate blocked project creation: " + " ".join(errors))
    if request.language not in {"vi", "en"}:
        raise RemakeAgentError("--language currently supports vi or en.")
    if not 15 <= request.duration_seconds <= 3600:
        raise RemakeAgentError("--duration must be between 15 and 3600 seconds.")

    inferred = request.source.title or request.source.author_name or "Untitled topic"
    topic = _one_line(request.topic or inferred, 140)
    if not topic:
        raise RemakeAgentError("Supply --topic because a topic could not be inferred from source metadata.")
    angle = _one_line(request.angle or "a practical, independent explanation", 180)
    name = request.project_name or slugify(topic)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    project_dir = request.output_root.expanduser().resolve() / f"{slugify(name)}-{timestamp}"
    if project_dir.exists():
        raise RemakeAgentError(f"Project directory already exists: {project_dir}")
    (project_dir / "assets").mkdir(parents=True)
    (project_dir / "output").mkdir()

    narration, cards = _story(topic, angle, request.language)
    evidence = evidence_record(request.declaration.evidence, project_dir)
    checks = compliance_checks(request.declaration)
    source_record = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "created_at": _now(),
        "source": request.source.to_dict(),
        "rights_declaration": {
            "basis": request.declaration.basis,
            "confirmed": request.declaration.confirmed,
            "statement": "Creator attests they have the necessary rights for their planned use.",
            "evidence": evidence,
        },
        "media_handling": {
            "source_video_downloaded": False,
            "source_audio_downloaded": False,
            "source_captions_downloaded": False,
            "source_thumbnail_downloaded": False,
            "note": "Only metadata was requested. Source media must never be copied by this workflow.",
        },
    }
    report = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "updated_at": _now(),
        "publish_ready": publishing_ready(checks),
        "manual_review_required": True,
        "checks": checks,
        "disclaimer": "This report is not a legal opinion, a copyright clearance, or a guarantee of YouTube/YPP approval.",
    }
    brief = f"""# Creative brief

**Working topic:** {topic}

**Independent angle:** {angle}

**Reference handling:** The URL in `source_record.json` is a traceability record only. This project must not reproduce the reference video’s clips, soundtrack, captions, thumbnail, scene order, distinctive script wording, or voice.

**Original-value target:** Build a stand-alone argument with independently checked facts, a clearly different structure, original narration/commentary, and creator-made or properly licensed assets.

**Required research before recording:** Verify each factual assertion with authoritative sources. Keep research links and asset terms in `rights_ledger.csv` or your production records.
"""
    script = f"""# Original narration draft — requires creator rewrite and fact review

The following is a new structural starting point based on the *topic only*. It is not a transcript, translation, scene list, or paraphrase of the reference.

{narration}

## Recording direction

- Use a human creator voice or a voice for which you have explicit commercial-use rights.
- Add your own examples, commentary, analysis, and verified citations.
- Do not imitate a living person’s voice or make a real person appear to say something they did not say.
- Replace all bracketed prompts before recording.
"""
    render_config = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "title": topic,
        "language": request.language,
        "draft_duration_seconds": request.duration_seconds,
        "cards": cards,
        "renderer_notice": "Procedural background and original project copy only. No source media is used.",
    }

    _write_json(project_dir / "source_record.json", source_record)
    _write_json(project_dir / "compliance_report.json", report)
    _write_json(project_dir / "render_config.json", render_config)
    (project_dir / "creative_brief.md").write_text(brief, encoding="utf-8")
    (project_dir / "script.md").write_text(script, encoding="utf-8")
    (project_dir / "publish_checklist.md").write_text(_publish_checklist(request.language), encoding="utf-8")
    (project_dir / "README.md").write_text(_project_readme(name), encoding="utf-8")
    (project_dir / "assets" / "README.md").write_text(
        "Add only assets you created or have documented rights to use. Log every asset in ../rights_ledger.csv.\n",
        encoding="utf-8",
    )
    (project_dir / "output" / ".gitkeep").write_text("", encoding="utf-8")
    with (project_dir / "rights_ledger.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_ASSET_COLUMNS)
        writer.writeheader()
    return project_dir


def read_project_json(project_dir: Path, name: str) -> dict[str, Any]:
    path = project_dir / name
    if not path.exists():
        raise RemakeAgentError(f"Missing required project file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RemakeAgentError(f"Invalid JSON in {path}: {exc}") from exc


def ledger_is_complete(project_dir: Path) -> bool:
    path = project_dir / "rights_ledger.csv"
    if not path.exists():
        return False
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    # No third-party assets may be used in the default procedural render. For a final
    # project, at least one documented asset is expected, and every schema field is set.
    return bool(rows) and all(all((row.get(column) or "").strip() for column in REQUIRED_ASSET_COLUMNS) for row in rows)


def update_review(
    project_dir: Path,
    *,
    has_original_voiceover: bool,
    assets_ledger_complete: bool,
    realistic_ai: bool,
) -> dict[str, Any]:
    source_record = read_project_json(project_dir, "source_record.json")
    declaration_data = source_record.get("rights_declaration", {})
    declaration = RightsDeclaration(
        basis=str(declaration_data.get("basis") or ""),
        confirmed=bool(declaration_data.get("confirmed")),
        # Evidence was checked when the project was created; a digest/reference is retained.
        evidence="retained" if declaration_data.get("evidence") else None,
    )
    checks = compliance_checks(
        declaration,
        source_media_downloaded=any(
            bool(value)
            for value in source_record.get("media_handling", {}).values()
            if isinstance(value, bool)
        ),
        original_voiceover=has_original_voiceover,
        asset_ledger_complete=assets_ledger_complete,
        synthetic_realistic_content=realistic_ai,
    )
    report = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "updated_at": _now(),
        "publish_ready": publishing_ready(checks),
        "manual_review_required": True,
        "checks": checks,
        "upload_action": (
            "Do not upload until human legal/factual/policy review is complete."
            if not publishing_ready(checks)
            else "Complete final human review and set altered/synthetic disclosure in Studio if applicable."
        ),
        "disclaimer": "This report is not a legal opinion, a copyright clearance, or a guarantee of YouTube/YPP approval.",
    }
    _write_json(project_dir / "compliance_report.json", report)
    return report
