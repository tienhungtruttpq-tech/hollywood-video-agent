import unittest

from remake_agent.rights import RightsDeclaration, compliance_checks, publishing_ready


class RightsDeclarationTests(unittest.TestCase):
    def test_permission_requires_evidence(self):
        declaration = RightsDeclaration("permission", True, None)
        self.assertFalse(declaration.is_acceptable)
        self.assertIn("requires --rights-evidence", declaration.errors()[0])

    def test_owned_declaration_can_pass_creation_gate(self):
        declaration = RightsDeclaration("owned", True)
        self.assertTrue(declaration.is_acceptable)
        checks = compliance_checks(declaration)
        self.assertFalse(publishing_ready(checks))
        self.assertEqual(checks[0]["status"], "pass")
        self.assertEqual(checks[2]["status"], "needs-review")

    def test_publish_is_ready_only_when_every_check_passes(self):
        declaration = RightsDeclaration("owned", True)
        checks = compliance_checks(
            declaration,
            original_voiceover=True,
            asset_ledger_complete=True,
            synthetic_realistic_content=False,
        )
        self.assertTrue(publishing_ready(checks))
