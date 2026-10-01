import json
import importlib
import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import baseline_pixtral_direct as direct
from baseline_pixtral_direct import parse_answer
from json_store import load_json, save_json
from structured_vision import parse_fields


class VisionValidationTests(unittest.TestCase):
    def test_invalid_direct_output_remains_retryable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "image_01.jpg").write_bytes(b"synthetic")
            source, output = root / "source.json", root / "output.json"
            save_json(source, {"image_01.jpg": {"manual_correction": {"correct": {}}}})
            facets = json.loads(Path(direct.TAXONOMY).read_text(encoding="utf-8"))["facets"]
            valid = {key: {"choice": next(iter(spec["criteria"])), "confidence": .9}
                     for key, spec in facets.items()}
            with patch.multiple(direct, PICTURES=td, CASCADE_RESULTS=str(source),
                                RESULTS=str(output), MISTRAL_KEY="test"), \
                    patch.object(direct, "classify_image",
                                 side_effect=[("{}", {}), (json.dumps(valid), {})]) as api, \
                    patch("time.sleep"), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    direct.main()
                self.assertEqual(load_json(output)["image_01.jpg"]["status"], "error")
                direct.main()
                direct.main()
                self.assertEqual(load_json(output)["image_01.jpg"]["status"], "ok")
                self.assertEqual(api.call_count, 2)

    def test_missing_decision_key_prevents_paid_vision(self):
        for name in ("measure_edge_cases", "measure_library_standin", "measure_replication"):
            module = importlib.import_module(name)
            with self.subTest(name=name), \
                    patch.object(module.classify_images, "MISTRAL_KEY", "test"), \
                    patch.object(module.pilot_humanoid, "API_KEY", ""), \
                    patch.object(module, "describe_image") as vision, self.assertRaises(SystemExit):
                module.main()
            vision.assert_not_called()

    def test_direct_answer_requires_all_facets_and_valid_values(self):
        path = Path(__file__).with_name("humanoid_taxonomy_v4.json")
        facets = json.loads(path.read_text(encoding="utf-8"))["facets"]
        valid = {key: {"choice": next(iter(spec["criteria"])), "confidence": .9}
                 for key, spec in facets.items()}
        self.assertEqual(parse_answer(json.dumps(valid), facets), valid)
        for payload in ({}, {"primary_subject": valid["primary_subject"]}):
            with self.assertRaises(ValueError):
                parse_answer(json.dumps(payload), facets)
        for answer in ({"choice": "invalid", "confidence": 1},
                       {"choice": valid["primary_subject"]["choice"]},
                       {"choice": valid["primary_subject"]["choice"], "confidence": float("nan")},
                       {"choice": valid["primary_subject"]["choice"], "confidence": 2}):
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                parse_answer(json.dumps({**valid, "primary_subject": answer}), facets)

    def test_fields_validate_both_json_and_repair_paths(self):
        fields = {"medium": "photograph", "subjects": "", "text_in_image": "none",
                  "setting": "studio", "people": "none"}
        self.assertEqual(parse_fields(json.dumps(fields)), fields)
        for payload in ({}, {**fields, "medium": "poster"},
                        {**fields, "people": None}, {**fields, "setting": ""}):
            with self.assertRaises(ValueError):
                parse_fields(json.dumps(payload))
        raw = '{"medium":"photograph","subjects":"","text_in_image":"say "hello"\\nnow","setting":"studio","people":"none"}'
        self.assertIn('hello', parse_fields(raw)["text_in_image"])
        raw_newline = json.dumps({**fields, "text_in_image": "line\nbreak"}).replace("\\n", "\n")
        self.assertEqual(parse_fields(raw_newline)["text_in_image"], "line\nbreak")


if __name__ == "__main__":
    unittest.main()
