import json
import tempfile
import unittest
from pathlib import Path

from media_publisher.shared.io import atomic_write_json, atomic_write_text


class AtomicIoTests(unittest.TestCase):
    def test_atomic_write_text_replaces_file_content(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            file_path = root / "report.txt"
            file_path.write_text("old", encoding="utf-8")

            atomic_write_text(file_path, "new-content", encoding="utf-8")
            self.assertEqual(file_path.read_text(encoding="utf-8"), "new-content")

            tmp_files = list(root.glob(".report.txt.*.tmp"))
            self.assertEqual(tmp_files, [])

    def test_atomic_write_json_serializes_payload(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "state.json"
            payload = {"status": "ok", "count": 2}
            atomic_write_json(file_path, payload)

            data = json.loads(file_path.read_text(encoding="utf-8"))
            self.assertEqual(data, payload)


if __name__ == "__main__":
    unittest.main()
