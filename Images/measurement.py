"""Shared historical-baseline loading and threshold evaluation."""
import os
from pathlib import Path

from json_store import load_json
from routing import FACETS, THRESHOLD


def load_baseline(source_path, names):
    path = os.environ.get("BASELINE_RESULTS")
    if not path:
        raise ValueError("Set BASELINE_RESULTS to a preserved baseline snapshot, "
                         "not the current production results")
    if Path(path).resolve() == Path(source_path).resolve():
        raise ValueError("BASELINE_RESULTS must be a separate preserved snapshot")
    baseline = load_json(path)
    for name in names:
        rec = baseline.get(name, {})
        if rec.get("status") != "ok" or not all(f in rec for f in FACETS):
            raise ValueError("Baseline snapshot does not cover all selected records")
        if not isinstance(rec.get("description"), str):
            raise ValueError("Baseline snapshot is missing source descriptions")
    return baseline


def threshold_summary(answers, truth):
    if not answers:
        raise ValueError("No measurements to compare")
    wrong = {name for name, rec in answers.items()
             if any(rec[f]["choice"] != truth[name][f]
                    for f in FACETS if truth[name].get(f) is not None)}
    routed = {name for name, rec in answers.items()
              if any(rec[f]["confidence"] < THRESHOLD for f in FACETS)}
    return wrong, routed, wrong & routed
