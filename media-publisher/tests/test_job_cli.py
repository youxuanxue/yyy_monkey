import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from media_publisher.__main__ import run_job_cli


class JobCliTests(unittest.TestCase):
    def test_job_cli_dry_run_success(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            video = root / "demo.mp4"
            script = root / "script.json"
            job = root / "job.json"

            video.write_bytes(b"fake")
            script.write_text('{"wechat":{"title":"t","description":"d"}}', encoding="utf-8")
            job.write_text(
                json.dumps(
                    {
                        "mode": "legacy",
                        "platform": "wechat",
                        "video": str(video),
                        "script": str(script),
                        "dry_run": True,
                    }
                ),
                encoding="utf-8",
            )

            result = run_job_cli(
                Namespace(job_file=str(job), dry_run=False, result_file=None, json=True)
            )
            self.assertEqual(result["status"], "success")
            self.assertFalse(result["retryable"])
            self.assertTrue(result["metrics"]["dry_run"])

    def test_job_cli_rejects_unsafe_account(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            video = root / "demo.mp4"
            script = root / "script.json"
            job = root / "job.json"

            video.write_bytes(b"fake")
            script.write_text('{"wechat":{"title":"t","description":"d"}}', encoding="utf-8")
            job.write_text(
                json.dumps(
                    {
                        "mode": "legacy",
                        "platform": "wechat",
                        "video": str(video),
                        "script": str(script),
                        "account": "../../oops",
                    }
                ),
                encoding="utf-8",
            )

            result = run_job_cli(
                Namespace(job_file=str(job), dry_run=True, result_file=None, json=True)
            )
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"]["code"], "MP_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
