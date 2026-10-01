"""Exercise each producer's fresh-run/resume wiring without network access."""
from contextlib import ExitStack, redirect_stdout
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from json_store import load_json, save_json
from test_review_ui import record


class PipelineRunTests(unittest.TestCase):
    def test_every_producer_stamps_and_resumes_without_api_calls(self):
        modules = (
            "classify_images", "pilot_humanoid", "baseline_pixtral_direct",
            "structured_vision", "capture_type", "measure_library_standin",
            "measure_edge_cases", "measure_replication", "measure_taxonomy_v6",
            "measure_taxonomy_v7_personal", "measure_taxonomy_v9",
            "measure_taxonomy_v10", "generate_edge_cases",
        )
        for name in modules:
            with self.subTest(script=name), tempfile.TemporaryDirectory() as td, ExitStack() as stack:
                module = importlib.import_module(name)
                root = Path(td)
                image_name = "image_01.jpg"
                key = "image_01" if name == "measure_replication" else image_name
                if name == "measure_edge_cases":
                    key = "statue"
                (root / image_name).write_bytes(b"synthetic image")
                raw = record()
                raw.update(file=image_name, category="human_photo",
                           manual_correction={"date": "2026-09-24",
                                              "correct": {f: record()[f]["choice"] for f in (
                                                  "contains_human", "contains_robot",
                                                  "contains_android", "primary_subject",
                                                  "representation")}})
                source, baseline = root / "source.json", root / "baseline.json"
                output, manifest = root / "output.json", root / "manifest.json"
                fields_path, generated = root / "fields.json", root / "generated.json"
                save_json(source, {key: raw})
                save_json(baseline, {key: raw})
                category = "portrait_photo" if name == "measure_replication" else "human_photo"
                save_json(manifest, {key: {"file": image_name, "file_ext": ".jpg", "status": "ok",
                                           "category": category, "title": "Synthetic", "verified": True},
                                     **({"_sealing": {}} if name == "measure_replication" else {})})
                save_json(generated, {key: {"status": "ok", "file": image_name, "prompt": "Synthetic"}})
                fields = dict(medium="photograph", subjects="robot", text_in_image="none",
                              setting="studio", people="individuals")
                save_json(fields_path, {key: {"status": "ok", "fields": fields}})
                replacements = {
                    "SOURCE": str(source), "CASCADE_RESULTS": str(source),
                    "RESULTS": str(output), "MANIFEST": str(manifest),
                    "STRUCTURED_RESULTS": str(fields_path), "GENERATED": str(generated),
                    "IMAGES_DIR": str(root), "PICTURES": str(root),
                    "API_KEY": "test", "MISTRAL_KEY": "test", "TYPESAFE_KEY": "test",
                }
                stack.enter_context(patch.multiple(module, **{
                    k: v for k, v in replacements.items() if hasattr(module, k)}))
                stack.enter_context(patch.dict("os.environ", {"BASELINE_RESULTS": str(baseline)}))
                stack.enter_context(patch.object(module.sys, "argv", [name, "1"]
                                                if name == "measure_replication" else [name]))
                stack.enter_context(patch("urllib.request.urlopen", side_effect=AssertionError("Network forbidden")))
                stack.enter_context(patch("time.sleep"))
                if hasattr(module, "side"):
                    stack.enter_context(patch.object(module, "side", return_value="M"))
                if name == "measure_replication":
                    stack.enter_context(patch.object(module, "results_path", return_value=str(output)))
                if name == "generate_edge_cases":
                    stack.enter_context(patch.object(module, "load_prompts",
                                                     return_value=[{"id": key, "prompt": "Synthetic"}]))
                    stack.enter_context(patch.object(module, "ensure_agent", return_value="test-agent"))
                answers = {f: raw[f] for f in (
                    "contains_human", "contains_robot", "contains_android",
                    "primary_subject", "representation")}
                mocks = []
                call_values = {
                    "describe_image": "Photograph of a robot.",
                    "jev_classify": {"choice": "yes", "confidence": 1, "probabilities": {}},
                    "jev_classify_facets": (answers, {}) if name in ("structured_vision", "capture_type") else answers,
                    "classify_image": (json.dumps(answers), {}),
                    "extract_fields": (fields, "{}", {}),
                    "ask_capture": ("photo_of_physical", "{}", {}),
                    "generate_one": ("test-file", "image.jpg", {}),
                    "download_file": b"\xff\xd8\xffsynthetic",
                }
                for function, value in call_values.items():
                    if hasattr(module, function):
                        mocks.append(stack.enter_context(patch.object(module, function, return_value=value)))
                with redirect_stdout(io.StringIO()):
                    module.main()
                saved = load_json(output)
                self.assertEqual(len(saved), 1)
                self.assertTrue(all(r.get("status") == "ok" and "_provenance" in r
                                    for r in saved.values()))
                before = [mock.call_count for mock in mocks]
                self.assertGreater(sum(before), 0)
                with redirect_stdout(io.StringIO()):
                    module.main()
                self.assertEqual([mock.call_count for mock in mocks], before)
                self.assertEqual(load_json(output), saved)
                legacy = load_json(output)
                del legacy[key]["_provenance"]
                save_json(output, legacy)
                before_bytes = output.read_bytes()
                with redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                    module.main()
                self.assertEqual([mock.call_count for mock in mocks], before)
                self.assertEqual(output.read_bytes(), before_bytes)
                if name.startswith("measure_taxonomy"):
                    with patch.object(module.sys, "argv", [name, "--report-only"]), \
                            patch.object(module, "API_KEY", ""), redirect_stdout(io.StringIO()):
                        module.main()
                    self.assertEqual([mock.call_count for mock in mocks], before)
                    self.assertEqual(output.read_bytes(), before_bytes)


if __name__ == "__main__":
    unittest.main()
