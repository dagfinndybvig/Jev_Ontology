import copy
import http.client
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from json_store import load_json, save_json
import review_ui as ui


def record():
    choices = dict(contains_human="yes", contains_robot="yes", contains_android="no",
                   primary_subject="robot", representation="photograph")
    return {"status": "ok", "description": "Robot with a background person.",
            **{key: {"choice": value, "confidence": 1.0}
               for key, value in choices.items()}}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "results.json"
        save_json(self.path, {"image_01.jpg": record()})
        self.patch = patch.object(ui, "RESULTS", str(self.path))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.server = ui.ThreadingHTTPServer(("127.0.0.1", 0), ui.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection(*self.server.server_address)
        try:
            conn.request(method, path, body=json.dumps(body) if body else None,
                         headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_confirm_preserves_raw_and_external_records(self):
        _, payload = self.request("GET", "/api/records")
        view = payload["records"][0]
        raw = copy.deepcopy(record())
        doc = load_json(self.path)
        doc["image_02.jpg"] = record()
        save_json(self.path, doc)
        status, result = self.request("POST", "/api/correct/image_01.jpg", {
            "revision": view["revision"],
            "correct": {f: raw[f]["choice"] for f in ui.FACETS}})
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])
        saved = load_json(self.path)
        self.assertIn("image_02.jpg", saved)
        self.assertEqual({f: saved["image_01.jpg"][f] for f in ui.FACETS},
                         {f: raw[f] for f in ui.FACETS})
        self.assertTrue(saved["image_01.jpg"]["manual_correction"]["raw_jev_preserved"])

    def test_stale_browser_cannot_replace_new_correction(self):
        _, payload = self.request("GET", "/api/records")
        body = {"revision": payload["records"][0]["revision"],
                "correct": {f: record()[f]["choice"] for f in ui.FACETS}}
        self.assertEqual(self.request("POST", "/api/correct/image_01.jpg", body)[0], 200)
        self.assertEqual(self.request("POST", "/api/correct/image_01.jpg", body)[0], 409)
        self.assertEqual(self.request("POST", "/api/uncorrect/image_01.jpg", body)[0], 409)

    def test_invalid_choice_rejected(self):
        _, payload = self.request("GET", "/api/records")
        correct = {f: record()[f]["choice"] for f in ui.FACETS}
        correct["contains_human"] = "maybe"
        status, _ = self.request("POST", "/api/correct/image_01.jpg",
                                 {"revision": payload["records"][0]["revision"],
                                  "correct": correct})
        self.assertEqual(status, 400)
        self.assertNotIn("manual_correction", load_json(self.path)["image_01.jpg"])

    def test_default_taxonomy_is_production(self):
        source = Path(ui.__file__).read_text(encoding="utf-8")
        self.assertIn('os.environ.get("TAXONOMY", "humanoid_taxonomy_v9.json")', source)

    def test_browser_flags_shortcuts_and_save(self):
        script = ui.PAGE.split("<script>")[1].split("</script>")[0].rsplit("init();", 1)[0]
        harness = Path(__file__).with_name("test_review_ui.js").read_text(encoding="utf-8")
        result = subprocess.run(["node", "-"], input=harness.replace(
            "/* APP_SCRIPT */", "vm.runInContext(" + json.dumps(script) + ", ctx);"),
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
