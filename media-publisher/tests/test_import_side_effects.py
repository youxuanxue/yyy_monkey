import os
import subprocess
import sys
import unittest
from pathlib import Path


class ImportSideEffectsTests(unittest.TestCase):
    def test_import_media_publisher_does_not_mutate_proxy_env(self):
        repo_root = Path(__file__).resolve().parents[1]
        src_dir = repo_root / "src"
        env = os.environ.copy()
        env.pop("HTTP_PROXY", None)
        env.pop("HTTPS_PROXY", None)
        env["USE_PROXY"] = "true"

        code = (
            "import os, sys;"
            f"sys.path.insert(0, {str(src_dir)!r});"
            "import media_publisher;"
            "print((os.environ.get('HTTP_PROXY'), os.environ.get('HTTPS_PROXY')))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertIn("(None, None)", result.stdout.strip())

    def test_import_media_publisher_core_does_not_mutate_proxy_env(self):
        repo_root = Path(__file__).resolve().parents[1]
        src_dir = repo_root / "src"
        env = os.environ.copy()
        env.pop("HTTP_PROXY", None)
        env.pop("HTTPS_PROXY", None)
        env["USE_PROXY"] = "true"

        code = (
            "import os, sys;"
            f"sys.path.insert(0, {str(src_dir)!r});"
            "import media_publisher.core;"
            "print((os.environ.get('HTTP_PROXY'), os.environ.get('HTTPS_PROXY')))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertIn("(None, None)", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
