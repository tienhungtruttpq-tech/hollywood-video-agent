"""Rights assertions and conservative publishing gates.

This is deliberately evidence-oriented: software cannot decide copyright, fair use,
or YouTube eligibility. It can preserve declarations and stop an unsafe default flow.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

ALLOWED_RIGHTS: Final[set[str]] = {
    "owned",
    "licensed",
    "permission",
    "cc",
    "public-domain",
}

RIGHTS_LABELS: Final[dict[str, str]] = {
    "owned": "I own the source or control the rights needed for this use.",
    "licensed": "I have a license covering this planned use.",
    "permission": "The rights holder gave me written permission for this planned use.",
    "cc": "The source is under a Creative Commons license and I will meet its terms.",
    "public-domain": "The source is public domain and I have documented that status.",
}

REQUIRED_ASSET_COLUMNS: Final[tuple[str, ...]] = (
    "asset_id",
    "asset_type",
    "source_url",
    "rights_basis",
    "license_or_permission",
    "creator_or_rights_holder",
    "required_attribution",
    "used_in",
)


@dataclass(frozen=True)
class RightsDeclaration:
    basis: str
    confirmed: bool
    evidence: str | None = None

    def errors(self) -> list[str]:
        problems: list[str] = []
        if self.basis not in ALLOWED_RIGHTS:
            problems.append("Choose a recognised rights basis.")
        if not self.confirmed:
            problems.append("You must explicitly confirm that you have the necessary rights.")
        if self.basis in {"licensed", "permission", "cc", "public-domain"} and not self.evidence:
            problems.append(
                f"{self.basis} requires --rights-evidence (a local file or a stable evidence URL)."
            )
        return problems

    @property
    def is_acceptable(self) -> bool:
        return not self.errors()


def evidence_record(value: str | None, project_dir: Path) -> dict | None:
    """Store a non-sensitive reference to evidence; never copy private agreements."""
    if not value:
        return None
    path = Path(value).expanduser()
    if path.exists() and path.is_file():
        # Evidence documents can contain private names, email addresses, and contracts.
        # Keep a reproducible digest, not a duplicate of the document in a git project.
        import hashlib

        return {
            "kind": "local-file",
            "name": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "note": "Original evidence intentionally remains outside this project.",
        }
    return {"kind": "reference-url-or-id", "reference": value}


def compliance_checks(
    declaration: RightsDeclaration,
    *,
    source_media_downloaded: bool = False,
    original_voiceover: bool = False,
    asset_ledger_complete: bool = False,
    synthetic_realistic_content: bool = False,
) -> list[dict[str, str]]:
    """Return explicit checks rather than pretending a legal determination is possible."""
    checks = [
        {
            "id": "rights-attestation",
            "status": "pass" if declaration.is_acceptable else "fail",
            "detail": "; ".join(declaration.errors()) or RIGHTS_LABELS[declaration.basis],
        },
        {
            "id": "no-source-download",
            "status": "fail" if source_media_downloaded else "pass",
            "detail": (
                "The workflow must not fetch, rip, or reuse the source video/audio by default."
                if source_media_downloaded
                else "Only public page metadata may be inspected; source media is not downloaded."
            ),
        },
        {
            "id": "original-contribution",
            "status": "pass" if original_voiceover else "needs-review",
            "detail": (
                "Original narration/commentary is recorded as present."
                if original_voiceover
                else "Add a genuinely original voiceover or on-camera contribution before publishing."
            ),
        },
        {
            "id": "asset-rights-ledger",
            "status": "pass" if asset_ledger_complete else "needs-review",
            "detail": (
                "Every visual/audio asset is documented."
                if asset_ledger_complete
                else "Complete rights_ledger.csv for every visual, clip, music track, and voice asset."
            ),
        },
        {
            "id": "synthetic-disclosure",
            "status": "needs-review" if synthetic_realistic_content else "pass",
            "detail": (
                "Set YouTube's altered/synthetic-content disclosure if realistic AI material is used."
                if synthetic_realistic_content
                else "No realistic synthetic content has been declared for this draft."
            ),
        },
    ]
    return checks


def publishing_ready(checks: list[dict[str, str]]) -> bool:
    return all(check["status"] == "pass" for check in checks)
