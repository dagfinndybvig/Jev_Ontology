from contextlib import redirect_stdout
from copy import deepcopy
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from experiment_state import run_experiment, save_summary
from Images.json_store import WriteConflict, load_json, save_json
import heldout_experiment as heldout

TREE = {"id": "root", "label": "Root", "definition": "Root",
        "children": [{"id": "leaf", "label": "Leaf", "definition": "Leaf"}]}


def answer(model="test-model"):
    return {"path": [{"node": "leaf", "confidence": 1, "distribution": {"leaf": 1},
                      "model": model}], "leaf": "leaf", "overall_confidence": 1, "tokens": 1}


class ExperimentStateTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "run.results.json"
        env = patch.dict(os.environ, {"RESULTS_OUT": str(self.path)})
        env.start()
        self.addCleanup(env.stop)
        self.batches = {"run": {"tickets": ["first", "second"], "ontology": TREE, "version": "test"}}

    def run_batch(self, classify, key="test", batches=None):
        return run_experiment("unused.results.json", batches or self.batches, classify, key, __file__)

    def test_fresh_run_and_no_key_resume_preserve_raw_evidence(self):
        classify = Mock(side_effect=lambda *args: answer())
        groups, document = self.run_batch(classify)
        self.assertEqual(classify.call_count, 2)
        self.assertEqual(groups["run"][0]["path"][0]["model"], "test-model")
        self.assertEqual(document["_meta"]["identity"]["batches"]["run"]["ontology"], TREE)
        before = self.path.read_bytes()
        self.run_batch(classify, key="")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(classify.call_count, 2)

    def test_failed_ticket_resumes_without_repeating_completed_tickets(self):
        classify = Mock(side_effect=[answer(), OSError("offline")])
        with self.assertRaises(OSError):
            self.run_batch(classify)
        records = load_json(self.path)["records"]
        self.assertEqual([records[f"run:{i}"]["status"] for i in range(2)], ["ok", "error"])
        retry = Mock(return_value=answer())
        self.run_batch(retry)
        self.assertEqual(retry.call_args.args[0], "second")
        retry.assert_called_once()

    def test_changed_input_ontology_config_and_legacy_refused_before_calls(self):
        self.run_batch(Mock(return_value=answer()))
        before = self.path.read_bytes()
        for field, value in (("tickets", ["changed", "second"]), ("version", "changed"),
                             ("ontology", {**TREE, "definition": "changed"})):
            batches = deepcopy(self.batches)
            batches["run"][field] = value
            classify = Mock()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.run_batch(classify, batches=batches)
            classify.assert_not_called()
            self.assertEqual(self.path.read_bytes(), before)
        save_json(self.path, {"legacy": {"status": "ok"}})
        before = self.path.read_bytes()
        classify = Mock()
        with self.assertRaises(ValueError):
            self.run_batch(classify)
        classify.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_key_and_protected_filename_do_not_write(self):
        classify = Mock()
        with self.assertRaises(SystemExit):
            self.run_batch(classify, key="")
        self.assertFalse(self.path.exists())
        with patch.dict(os.environ, {"RESULTS_OUT": str(self.path.with_name("heldout_results.json"))}):
            with self.assertRaises(ValueError):
                self.run_batch(classify)
        classify.assert_not_called()

    def test_invalid_output_and_changed_model_remain_errors(self):
        invalid = {**answer(), "overall_confidence": 2}
        with self.assertRaises(ValueError):
            self.run_batch(Mock(return_value=invalid))
        self.assertEqual(load_json(self.path)["records"]["run:0"]["status"], "error")
        with self.assertRaises(ValueError):
            self.run_batch(Mock(side_effect=[answer(), answer("different-model")]))
        records = load_json(self.path)["records"]
        self.assertEqual(records["run:1"]["status"], "error")
        self.assertEqual(records["run:1"]["partial_result"]["path"][0]["model"], "different-model")

    def test_nonfinite_payload_is_saved_as_error_not_invalid_json(self):
        with self.assertRaises(ValueError):
            self.run_batch(Mock(return_value={**answer(), "overall_confidence": float("nan")}))
        record = load_json(self.path)["records"]["run:0"]
        self.assertEqual(record["status"], "error")
        self.assertIn("nan", record["invalid_result_repr"])

    def test_implementation_change_refuses_resume(self):
        source = self.path.with_name("implementation.py")
        source.write_text("VALUE = 1\n", encoding="utf-8")
        classify = Mock(return_value=answer())
        run_experiment("unused.results.json", self.batches, classify, "test", str(source))
        before = self.path.read_bytes()
        source.write_text("VALUE = 2\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            run_experiment("unused.results.json", self.batches, classify, "test", str(source))
        self.assertEqual(classify.call_count, 2)
        self.assertEqual(self.path.read_bytes(), before)

    def test_concurrent_writer_and_stale_summary_are_not_overwritten(self):
        def concurrent(*args):
            save_json(self.path, {"other_writer": True})
            return answer()
        with self.assertRaises(WriteConflict):
            self.run_batch(concurrent)
        self.assertEqual(load_json(self.path), {"other_writer": True})
        self.path.unlink()
        _, document = self.run_batch(Mock(return_value=answer()))
        newer = load_json(self.path)
        newer["summary"] = {"newer": True}
        save_json(self.path, newer)
        with self.assertRaises(WriteConflict):
            save_summary(document, {"stale": True})
        self.assertEqual(load_json(self.path)["summary"], {"newer": True})


class SplitTests(unittest.TestCase):
    def test_historical_split_is_read_only_and_exactly_bound(self):
        path = Path(heldout.SPLIT_PATH)
        before = path.read_bytes()
        split = heldout.get_split()
        self.assertEqual((len(split["train"]), len(split["holdout"])), (36, 16))
        self.assertEqual(path.read_bytes(), before)
        with patch.object(heldout, "TICKETS", list(reversed(heldout.TICKETS))), self.assertRaises(ValueError):
            heldout.get_split()

    def test_new_split_rejects_overlap_duplicates_bool_and_changed_corpus(self):
        with tempfile.TemporaryDirectory() as td, patch.object(heldout, "SPLIT_PATH", str(Path(td) / "split.json")), \
                patch.object(heldout, "TICKETS", ["one", "two", "three", "four"]):
            split = heldout.get_split()
            self.assertIn("corpus_sha256", split["_meta"])
            for train, hold in (([0, 1], [1, 2, 3]), ([0, 0], [1, 2, 3]),
                                ([False, 1], [2, 3]), ([0, 1], [2]), ([], [0, 1, 2, 3])):
                save_json(heldout.SPLIT_PATH, {**split, "train": train, "holdout": hold})
                with self.subTest(train=train, hold=hold), self.assertRaises(ValueError):
                    heldout.get_split()
            save_json(heldout.SPLIT_PATH, dict(split))
            with patch.object(heldout, "TICKETS", ["changed", "two", "three", "four"]), self.assertRaises(ValueError):
                heldout.get_split()


class EntryPointTests(unittest.TestCase):
    def test_experiments_fresh_resume_and_legacy_refusal_with_mocked_http(self):
        cases = [
            ("convergence_experiment", []), ("heldout_experiment", ["ontology.json"]),
            ("heldout_experiment", ["ontology.json", "--stage", "holdout"]),
            ("heldout_experiment", ["ontology.json", "--stage", "both"]),
            ("heldout_variance", ["2"]), ("generate_sessions", []),
            ("close_loop", []), ("run_iter1", []), ("run_iter2", []),
        ]
        def response(request, **kwargs):
            criteria = json.loads(request.data)["questions"]["classify"]["criteria"]
            choice = next(iter(criteria))
            payload = {"model": "test-model", "usage": {"input_tokens": 1},
                       "answers": {"classify": {"choice": choice, "confidence": 1,
                                               "probabilities": {k: int(k == choice) for k in criteria}}}}
            return io.BytesIO(json.dumps(payload).encode("utf-8"))
        for name, args in cases:
            with self.subTest(name=name, args=args), tempfile.TemporaryDirectory() as td:
                module = importlib.import_module(name)
                key_module = module.ce if name.startswith("run_iter") else module
                output = Path(td) / "run.results.json"
                with patch.dict(os.environ, {"RESULTS_OUT": str(output)}), \
                        patch.object(sys, "argv", [name, *args]), \
                        patch.object(key_module, "API_KEY", "test"), \
                        patch("urllib.request.urlopen", side_effect=response) as network, \
                        redirect_stdout(io.StringIO()) as stdout:
                    module.main()
                    saved = load_json(output)
                    count = network.call_count
                    self.assertGreater(count, 0)
                    self.assertTrue(all(r["status"] == "ok" for r in saved["records"].values()))
                    if name == "heldout_experiment" and args == ["ontology.json"]:
                        self.assertNotIn("HOLDOUT", stdout.getvalue())
                        self.assertEqual(len(saved["records"]), 36)
                    with patch.object(key_module, "API_KEY", ""):
                        module.main()
                    self.assertEqual(network.call_count, count)
                    self.assertEqual(load_json(output), saved)
                    save_json(output, {"legacy": True})
                    before = output.read_bytes()
                    with self.assertRaises(ValueError):
                        module.main()
                    self.assertEqual(network.call_count, count)
                    self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
