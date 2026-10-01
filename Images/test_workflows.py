import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import backfill_descriptions
from corpus_state import SealedManifestError, require_sealed
import fetch_replication_corpus as fetcher
from json_store import fingerprint, load_json, save_json
import measure_replication as replication
import pilot_humanoid as pilot
from run_state import file_digest, prepare_run, source_digest
import sort_humanoids as sorter
from test_review_ui import record
import verify_replication as verifier


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "results.json"

    def test_resume_identity_and_incremental_extension(self):
        config, inputs = {"taxonomy": "v9"}, {"image_01": "description"}
        stamps = prepare_run({}, config, inputs)
        results = {"image_01": {"status": "ok", "_provenance": stamps["image_01"]}}
        self.assertEqual(prepare_run(results, config, inputs), stamps)
        self.assertIn("image_02", prepare_run(
            results, config, {**inputs, "image_02": "new"}))
        results["image_01"]["manual_correction"] = {"correct": {"contains_human": "no"}}
        self.assertEqual(prepare_run(results, config, inputs), stamps)
        for changed_config, changed_inputs in (
            ({"taxonomy": "v10"}, inputs), (config, {"image_01": "changed"}),
            (config, {"image_02": "new"}),
        ):
            with self.assertRaises(ValueError):
                prepare_run(results, changed_config, changed_inputs)
        with self.assertRaises(ValueError):
            prepare_run({"image_01": {"status": "ok"}}, config, inputs)

    def test_code_identity_ignores_line_endings_not_behavior(self):
        source = self.root / "source.py"
        source.write_bytes(b"value = 1\n")
        before = source_digest(source)
        source.write_bytes(b"value = 1\r\n")
        self.assertEqual(before, source_digest(source))
        source.write_bytes(b"value = 2\r\n")
        self.assertNotEqual(before, source_digest(source))

    def test_pilot_new_resume_and_changed_input(self):
        source = self.root / "source.json"
        save_json(source, {"image_01": {"status": "ok", "description": "Photograph.",
                                      "choice": "yes"}})
        def classify(state, facets):
            return {f: record()[f] for f in facets}
        with patch.multiple(pilot, SOURCE=str(source), RESULTS=str(self.path), API_KEY="test"), \
                patch.object(pilot, "jev_classify_facets", side_effect=classify) as api, \
                patch.object(pilot.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            pilot.main()
            self.assertEqual(api.call_count, 1)
            self.assertIn("_provenance", load_json(self.path)["image_01"])
            pilot.main()
            self.assertEqual(api.call_count, 1)
            saved = self.path.read_bytes()
            doc = load_json(source)
            doc["image_01"]["description"] = "Changed."
            save_json(source, doc)
            with self.assertRaises(ValueError):
                pilot.main()
            self.assertEqual(api.call_count, 1)
            self.assertEqual(self.path.read_bytes(), saved)

    def test_failed_run_exits_nonzero_and_resumes_saved_progress(self):
        source = self.root / "source.json"
        save_json(source, {"image_01": {"status": "ok", "description": "Photograph.",
                                      "choice": "yes"}})
        with patch.multiple(pilot, SOURCE=str(source), RESULTS=str(self.path), API_KEY="test"), \
                patch.object(pilot, "jev_classify_facets", side_effect=RuntimeError("API unavailable")) as api, \
                patch.object(pilot.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                pilot.main()
            self.assertEqual(load_json(self.path)["image_01"]["status"], "error")
            api.side_effect = lambda state, facets: {f: record()[f] for f in facets}
            pilot.main()
            self.assertEqual(api.call_count, 2)
            self.assertEqual(load_json(self.path)["image_01"]["status"], "ok")

    def test_sort_reconciles_corrections_and_review_copies(self):
        image = self.root / "image_01.jpg"
        image.write_bytes(b"synthetic")
        rec = record()
        rec["contains_human"]["confidence"] = 0.5
        save_json(self.path, {image.name: rec})
        dst = self.root / "Humanoids"
        with patch.multiple(sorter, PICTURES=str(self.root), DST=str(dst),
                            RESULTS=str(self.path)), contextlib.redirect_stdout(io.StringIO()):
            sorter.main()
            self.assertTrue((dst / "_review" / image.name).exists())
            doc = load_json(self.path)
            doc[image.name]["manual_correction"] = {"correct": {
                "primary_subject": "human", "representation": "illustration"}}
            save_json(self.path, doc)
            sorter.main()
            self.assertFalse((dst / "robot" / "photograph" / image.name).exists())
            self.assertTrue((dst / "human" / "illustration" / image.name).exists())
            doc = load_json(self.path)
            del doc[image.name]["manual_correction"]
            doc[image.name]["contains_human"]["confidence"] = 1
            save_json(self.path, doc)
            sorter.main()
            self.assertFalse((dst / "_review" / image.name).exists())
            self.assertFalse((dst / "human" / "illustration" / image.name).exists())
            self.assertEqual(image.read_bytes(), b"synthetic")

    def test_sort_refuses_to_delete_edited_or_external_files(self):
        source = self.root / "image_01.jpg"
        source.write_bytes(b"original")
        stale = self.root / "sorted" / "image_01.jpg"
        stale.parent.mkdir()
        stale.write_bytes(b"edited")
        with self.assertRaises(ValueError):
            sorter.reconcile_copies(source, [], [stale], stale.parent)
        self.assertEqual(stale.read_bytes(), b"edited")
        with self.assertRaises(ValueError):
            sorter.reconcile_copies(source, [], [source], stale.parent)

    def test_fetch_failed_ids_do_not_satisfy_quota(self):
        save_json(self.path, {
            "portrait_photo_001": {"category": "portrait_photo", "si_id": "failed", "status": "error"},
            "portrait_photo_002": {"category": "portrait_photo", "si_id": "old", "status": "ok"},
        })
        candidates = [{"idsId": "failed"}, {"idsId": "old"}, {"idsId": "new"}]
        with patch.multiple(fetcher, MANIFEST=str(self.path), IMAGES_DIR=str(self.root),
                            PER_CATEGORY=2), \
                patch.object(fetcher.sys, "argv", ["fetch", "portrait_photo"]), \
                patch.object(fetcher, "iter_records", return_value=iter(candidates)), \
                patch.object(fetcher, "matches", return_value=True), \
                patch.object(fetcher, "cc0_image", side_effect=lambda r: r), \
                patch.object(fetcher.random.Random, "shuffle"), \
                patch.object(fetcher, "record_fields", side_effect=lambda rec, cat, img: {
                    "category": cat, "si_id": img["idsId"], "image_url": "synthetic"}), \
                patch.object(fetcher, "download", return_value=".jpg") as download, \
                patch.object(fetcher.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            fetcher.main()
            self.assertEqual(download.call_count, 1)
        self.assertEqual(sum(v.get("status") == "ok" for v in load_json(self.path).values()), 2)

    def test_sealed_fetch_backfill_and_verification_do_not_write(self):
        save_json(self.path, {"_sealing": {}, "image_01": {
            "category": "portrait_photo", "status": "ok", "verified": True}})
        before = self.path.read_bytes()
        with patch.multiple(fetcher, MANIFEST=str(self.path), IMAGES_DIR=str(self.root)), \
                patch.object(fetcher.sys, "argv", ["fetch"]), \
                patch.object(fetcher, "iter_records") as network:
            with self.assertRaises(SealedManifestError):
                fetcher.main()
            network.assert_not_called()
        with patch.object(backfill_descriptions, "MANIFEST", str(self.path)), \
                patch.object(backfill_descriptions, "get") as network:
            with self.assertRaises(SealedManifestError):
                backfill_descriptions.main()
            network.assert_not_called()
        handler = object.__new__(verifier.Handler)
        handler.path = "/verify"
        form = b"fname=image_01&verdict=wrong&corrected=exclude"
        handler.headers = {"Content-Length": str(len(form))}
        handler.rfile = io.BytesIO(form)
        replies = []
        handler._send = lambda code, *args: replies.append(code)
        with patch.object(verifier, "MANIFEST", str(self.path)):
            handler.do_POST()
        self.assertEqual(replies, [409])
        self.assertEqual(self.path.read_bytes(), before)

    def test_frozen_configuration_and_sealing(self):
        taxonomy = json.loads(Path(replication.TAXONOMY).read_text(encoding="utf-8"))
        replication.require_frozen(taxonomy)
        taxonomy["_meta"]["version"] = "different"
        with self.assertRaises(ValueError):
            replication.require_frozen(taxonomy)
        with self.assertRaises(SealedManifestError):
            require_sealed({})
        with self.assertRaises(SealedManifestError):
            require_sealed({"_sealing": {}, "image_01": {
                "status": "ok", "category": "portrait_photo", "verified": None}})
        with self.assertRaises(ValueError):
            replication.results_path("..")


if __name__ == "__main__":
    unittest.main()
