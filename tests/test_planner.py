import csv
import json
import tempfile
import unittest
from pathlib import Path

from remake_agent.planner import CreateProjectRequest, create_project, ledger_is_complete, update_review
from remake_agent.rights import REQUIRED_ASSET_COLUMNS, RightsDeclaration
from remake_agent.source import SourceMetadata


class PlannerTests(unittest.TestCase):
    def test_creates_no_source_media_project_and_requires_final_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = CreateProjectRequest(
                source=SourceMetadata(
                    url="https://example.com/article",
                    provider="web",
                    title="A reference subject",
                    fetched=False,
                ),
                declaration=RightsDeclaration("owned", True),
                topic=None,
                angle="an independently researched explanation",
                language="en",
                duration_seconds=15,
                output_root=root,
                project_name="test-project",
            )
            project = create_project(request)
            source_record = json.loads((project / "source_record.json").read_text())
            report = json.loads((project / "compliance_report.json").read_text())
            self.assertFalse(any(value for value in source_record["media_handling"].values() if isinstance(value, bool)))
            self.assertFalse(report["publish_ready"])
            self.assertTrue((project / "rights_ledger.csv").exists())
            self.assertIn("not a transcript", (project / "script.md").read_text())

            with (project / "rights_ledger.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=REQUIRED_ASSET_COLUMNS)
                writer.writeheader()
                writer.writerow({field: "creator-owned" for field in REQUIRED_ASSET_COLUMNS})
            self.assertTrue(ledger_is_complete(project))
            reviewed = update_review(
                project,
                has_original_voiceover=True,
                assets_ledger_complete=True,
                realistic_ai=False,
            )
            self.assertTrue(reviewed["publish_ready"])

    def test_permission_without_evidence_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            request = CreateProjectRequest(
                source=SourceMetadata(url="https://example.com", provider="web"),
                declaration=RightsDeclaration("permission", True),
                topic="Topic",
                angle=None,
                language="vi",
                duration_seconds=15,
                output_root=Path(temp),
            )
            with self.assertRaisesRegex(Exception, "Compliance gate blocked"):
                create_project(request)
