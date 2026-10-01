import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze_verified as av
import baseline_compare as bc
from measurement import load_baseline, threshold_summary


def answer():
    return {f: {"choice": c, "confidence": 1.0}
            for f, c in av.INTENDED["portrait_photo"].items()}


class MetricsTests(unittest.TestCase):
    def test_ece_uses_actual_mean_confidence(self):
        truth = av.INTENDED["portrait_photo"]
        labels = {"image_01": {"truth": truth}}
        self.assertEqual(bc.evaluate("perfect", {"image_01": answer()}, labels)["ece"], 0)
        predictions = answer()
        for rec in predictions.values():
            rec["confidence"] = 0.91
        self.assertAlmostEqual(bc.evaluate("near", {"image_01": predictions}, labels)["ece"], 0.09)

    def test_record_is_caught_by_any_low_confidence_facet(self):
        predictions = answer()
        predictions["contains_human"]["confidence"] = 0.5
        predictions["representation"]["choice"] = "illustration"
        ev = bc.evaluate("mixed", {"image_01": predictions},
                         {"image_01": {"truth": av.INTENDED["portrait_photo"]}})
        self.assertEqual((ev["caught"], ev["confident_wrong"]), (1, 0))

    def test_partial_coverage_uses_evaluated_denominator(self):
        predictions = answer()
        predictions["contains_human"]["confidence"] = 0.5
        labels = {k: {"truth": av.INTENDED["portrait_photo"]}
                  for k in ("image_01", "image_02")}
        ev = bc.evaluate("partial", {"image_01": predictions}, labels)
        self.assertEqual((ev["n_records"], ev["n_labeled"], ev["flag_rate"]), (1, 2, 1))

    def test_invalid_or_missing_confidence_fails(self):
        labels = {"image_01": {"truth": av.INTENDED["portrait_photo"]}}
        predictions = answer()
        predictions["contains_human"]["confidence"] = float("nan")
        with self.assertRaises(ValueError):
            bc.evaluate("invalid", {"image_01": predictions}, labels)
        del predictions["contains_human"]
        with self.assertRaises(ValueError):
            bc.evaluate("missing", {"image_01": predictions}, labels)

    def test_baseline_has_its_own_confidence(self):
        truth = {"image_01": av.INTENDED["portrait_photo"]}
        trial = answer()
        trial["representation"]["choice"] = "illustration"
        baseline = copy.deepcopy(trial)
        baseline["contains_human"]["confidence"] = 0.5
        self.assertEqual(threshold_summary({"image_01": trial}, truth)[2], set())
        self.assertEqual(threshold_summary({"image_01": baseline}, truth)[2], {"image_01"})

    def test_baseline_must_be_explicit_and_complete(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "baseline.json"
            path.write_text(json.dumps({}), encoding="utf-8")
            with patch.dict("os.environ", {"BASELINE_RESULTS": ""}):
                with self.assertRaises(ValueError):
                    load_baseline("source.json", [])
            with patch.dict("os.environ", {"BASELINE_RESULTS": str(path)}):
                with self.assertRaises(ValueError):
                    load_baseline(path, [])
                with self.assertRaises(ValueError):
                    load_baseline("source.json", ["image_01"])

    def test_replication_excludes_routed_errors(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = {
                "image_01": {"category": "portrait_photo", "verified": True},
                "image_02": {"category": "human_sculpture", "verified": True},
            }
            results = {}
            for name, rec in manifest.items():
                results[name] = {"status": "ok", "description": "Photograph.",
                                 **{f: {"choice": c, "confidence": 1.0}
                                    for f, c in av.INTENDED[rec["category"]].items()}}
            results["image_01"]["representation"] = {"choice": "other", "confidence": 0.5}
            mp = root / "manifest.json"
            mp.write_text(json.dumps(manifest), encoding="utf-8")
            (root / "replication_results_run1.json").write_text(
                json.dumps(results), encoding="utf-8")
            with patch.multiple(av, MANIFEST=str(mp), SCRIPT_DIR=str(root), RUNS=[1]):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    av.main()
                self.assertIn("auto-accept band: 0/1 mismatch", output.getvalue())
                results["image_02"]["contains_human"]["confidence"] = 0.5
                (root / "replication_results_run1.json").write_text(
                    json.dumps(results), encoding="utf-8")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    av.main()
                self.assertIn("auto-accept band: empty", output.getvalue())


if __name__ == "__main__":
    unittest.main()
