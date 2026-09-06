import unittest
from unittest.mock import patch

from remake_agent.errors import RemakeAgentError
from remake_agent.source import inspect_source, validate_source_url


class SourceTests(unittest.TestCase):
    def test_private_urls_are_rejected_before_fetch(self):
        for url in ("http://127.0.0.1/private", "http://localhost/private", "http://[::1]/private"):
            with self.subTest(url=url):
                with self.assertRaises(RemakeAgentError):
                    validate_source_url(url)

    @patch("remake_agent.source.socket.getaddrinfo")
    def test_youtube_id_and_offline_metadata_record(self, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("8.8.8.8", 0))]
        source = inspect_source("https://www.youtube.com/watch?v=abc-123", allow_network=False)
        self.assertEqual(source.provider, "youtube")
        self.assertEqual(source.video_id, "abc-123")
        self.assertFalse(source.fetched)
        self.assertIn("disabled", source.fetch_warning)

    def test_credentials_in_url_are_rejected(self):
        with self.assertRaises(RemakeAgentError):
            validate_source_url("https://user:password@example.com/video")
