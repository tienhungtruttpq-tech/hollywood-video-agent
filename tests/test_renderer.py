import unittest

from remake_agent.errors import RemakeAgentError
from remake_agent.renderer import _parse_resolution


class RendererTests(unittest.TestCase):
    def test_parses_safe_resolution(self):
        self.assertEqual(_parse_resolution("1280x720"), (1280, 720))

    def test_rejects_invalid_resolution(self):
        with self.assertRaises(RemakeAgentError):
            _parse_resolution("not-a-resolution")
        with self.assertRaises(RemakeAgentError):
            _parse_resolution("100x100")
