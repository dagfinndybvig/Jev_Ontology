import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

from json_store import WriteConflict, file_lock, load_json, save_json


class JsonStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "results.json"
        save_json(self.path, {"image_01": {"label": "human"}})

    def test_stale_writer_cannot_erase_another_writer(self):
        first = load_json(self.path)
        stale = load_json(self.path)
        first["image_02"] = {"label": "robot"}
        save_json(self.path, first)
        stale["image_01"]["label"] = "none"
        with self.assertRaises(WriteConflict):
            save_json(self.path, stale)
        self.assertEqual(load_json(self.path), first)

    def test_repeated_saves_update_revision(self):
        doc = load_json(self.path)
        for value in ("robot", "human"):
            doc["image_01"]["label"] = value
            save_json(self.path, doc)
        self.assertEqual(load_json(self.path), doc)

    def test_replace_failure_preserves_original_and_cleans_temp(self):
        before = self.path.read_bytes()
        with patch("json_store.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                save_json(self.path, {"replacement": True})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_serialization_failure_preserves_original(self):
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            save_json(self.path, {"invalid": float("nan")})
        self.assertEqual(self.path.read_bytes(), before)

    def test_new_file_conflict_and_utf8(self):
        path = self.path.parent / "new.json"
        first = load_json(path, missing_ok=True)
        second = load_json(path, missing_ok=True)
        first["text"] = "\u00e6"
        save_json(path, first)
        with self.assertRaises(WriteConflict):
            save_json(path, second)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), first)

    def test_wrong_destination_rejected(self):
        doc = load_json(self.path)
        with self.assertRaises(WriteConflict):
            save_json(self.path.parent / "other.json", doc)

    def test_os_lock_excludes_a_second_process(self):
        code = (
            "import sys; from json_store import file_lock, WriteConflict\n"
            "try:\n"
            "    with file_lock(sys.argv[1], timeout=0.1): pass\n"
            "except WriteConflict:\n"
            "    sys.exit(2)\n"
        )
        with file_lock(self.path):
            result = subprocess.run([sys.executable, "-B", "-c", code, str(self.path)],
                                    cwd=Path(__file__).parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)


if __name__ == "__main__":
    unittest.main()
