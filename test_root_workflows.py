import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import mvp_jev_ontology as mvp
import test_jev_api as smoke

ROOT = Path(__file__).resolve().parent


class RuntimeTests(unittest.TestCase):
    def test_all_entry_points_import_without_network(self):
        code = """
import importlib
from unittest.mock import patch
with patch('urllib.request.urlopen', side_effect=AssertionError('Network forbidden')) as network:
    for name in ('mvp_jev_ontology', 'convergence_experiment', 'heldout_experiment',
                 'heldout_variance', 'close_loop', 'generate_sessions', 'run_iter1',
                 'run_iter2', 'test_jev_api'):
        importlib.import_module(name)
    assert network.call_count == 0
"""
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_smoke_requires_key_and_propagates_failure(self):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}), \
                patch("urllib.request.urlopen") as network:
            with self.assertRaises(SystemExit):
                smoke.main()
            network.assert_not_called()
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "test"}), \
                patch("urllib.request.urlopen", side_effect=OSError("offline")):
            with self.assertRaises(OSError):
                smoke.main()

    def test_alternate_ontology_cannot_claim_default_version(self):
        tree = json.loads((ROOT / "ontology_v3.json").read_text(encoding="utf-8"))
        with patch.object(mvp, "USE_REAL_JEV", False):
            self.assertEqual(mvp.classify_item("payment failed", tree)["ontology_version"], "v3.0")
            del tree["_meta"]
            with self.assertRaises(ValueError):
                mvp.classify_item("payment failed", tree)
            self.assertEqual(mvp.classify_item("payment failed", tree, "v3.0")["ontology_version"], "v3.0")

    def test_choice_rejects_invalid_payloads(self):
        valid = {"choice": "a", "confidence": .8, "probabilities": {"a": .8, "b": .2}}
        mvp.validate_choice(valid, {"a", "b"})
        for update in ({"choice": "other"}, {"confidence": float("nan")},
                       {"confidence": True}, {"probabilities": {"a": .8}},
                       {"probabilities": {"a": 0, "b": 0}}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                mvp.validate_choice({**valid, **update}, {"a", "b"})


if __name__ == "__main__":
    unittest.main()
