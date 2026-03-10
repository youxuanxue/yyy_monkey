import unittest
from pathlib import Path

from media_publisher.core.browser import PlaywrightBrowser
from media_publisher.core.wechat import get_auth_file_path
from media_publisher.shared.security import sanitize_identifier


class SecurityValidationTests(unittest.TestCase):
    def test_sanitize_identifier_accepts_safe_value(self):
        self.assertEqual(sanitize_identifier("agent_01"), "agent_01")
        self.assertEqual(sanitize_identifier("奶奶讲故事"), "奶奶讲故事")

    def test_sanitize_identifier_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            sanitize_identifier("../evil")

        with self.assertRaises(ValueError):
            sanitize_identifier("a/b")

    def test_get_auth_file_path_rejects_unsafe_account(self):
        with self.assertRaises(ValueError):
            get_auth_file_path("../../x")

    def test_browser_rejects_unsafe_user_name(self):
        with self.assertRaises(ValueError):
            PlaywrightBrowser(platform_name="wechat", user_name="../x")

    def test_wechat_auth_path_uses_sanitized_account(self):
        p = get_auth_file_path("teamA_01")
        self.assertIsInstance(p, Path)
        self.assertIn("wechat_auth_teamA_01.json", str(p))


if __name__ == "__main__":
    unittest.main()
