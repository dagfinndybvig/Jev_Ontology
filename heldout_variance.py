"""
Measure run-to-run variance of Jev on the held-out set.

The held-out experiment showed holdout mean confidence moving 0.928 -> 0.932
after a train-only revision. But the tickets that improved were in branches
the revision did not touch (billing), while the one ticket in the touched
branch (Stripe IntegrationProblem) got slightly worse. That pattern suggests
the +0.004 is Jev's sampling variance, not real generalization.

This script classifies the SAME held-out set against the SAME ontology
(v2.0) N times and retains the raw paths plus descriptive variance.
An observed range is not a statistical noise bound or an accuracy measure.
The original reported repeats were not retained; new runs are new evidence.

Requires TYPESAFE_API_KEY.
"""

import json
import argparse
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heldout_experiment import API_KEY, TICKETS, load_ontology, classify_item, get_split
import heldout_experiment
from experiment_state import run_experiment, save_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=int, nargs="?", default=5)
    parser.add_argument("ontology_file", nargs="?", default="ontology.json")
    args = parser.parse_args()
    N = args.runs
    if N < 1:
        parser.error("Run count must be positive")
    split = get_split()
    holdout = [TICKETS[i] for i in split["holdout"]]
    ontology, ver = load_ontology(args.ontology_file)
    groups, document = run_experiment(
        "variance.results.json",
        {f"run_{i + 1}": {"tickets": holdout, "ontology": ontology, "version": ver} for i in range(N)},
        classify_item, API_KEY, __file__, heldout_experiment.__file__,
        config={"split": dict(split), "runs": N})

    means = []
    mins = []
    for run, results in enumerate(groups.values()):
        confs = [r["overall_confidence"] for r in results]
        means.append(sum(confs) / len(confs))
        mins.append(min(confs))
        print(f"run {run+1}: mean={means[-1]:.4f}  min={mins[-1]:.4f}")

    print(f"\nOntology {ver}, {N} runs, {len(holdout)} holdout tickets")
    print(f"mean confidence: min={min(means):.4f} max={max(means):.4f} "
          f"spread={max(means)-min(means):.4f} std={statistics.pstdev(means):.4f}")
    summary = {
        "ontology_file": args.ontology_file,
        "version": ver,
        "runs": N,
        "holdout_n": len(holdout),
        "means": means,
        "mins": mins,
        "spread": max(means) - min(means),
        "std": statistics.pstdev(means),
    }
    save_summary(document, summary)
    print(f"\nSaved to {document.path}")


if __name__ == "__main__":
    main()
