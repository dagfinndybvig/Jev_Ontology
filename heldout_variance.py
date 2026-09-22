"""
Measure run-to-run variance of Jev on the held-out set.

The held-out experiment showed holdout mean confidence moving 0.928 -> 0.932
after a train-only revision. But the tickets that improved were in branches
the revision did not touch (billing), while the one ticket in the touched
branch (Stripe IntegrationProblem) got slightly worse. That pattern suggests
the +0.004 is Jev's sampling variance, not real generalization.

This script classifies the SAME held-out set against the SAME ontology
(v2.0) N times and reports the spread of mean confidence, establishing the
noise floor.

Requires TYPESAFE_API_KEY.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heldout_experiment import TICKETS, load_ontology, classify_item, get_split

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
onto_file = sys.argv[2] if len(sys.argv) > 2 else "ontology.json"

split = get_split()
holdout = [TICKETS[i] for i in split["holdout"]]
ontology, ver = load_ontology(onto_file)

means = []
mins = []
for run in range(N):
    confs = []
    for t in holdout:
        r = classify_item(t, ontology)
        confs.append(r["overall_confidence"])
    means.append(sum(confs) / len(confs))
    mins.append(min(confs))
    print(f"run {run+1}: mean={means[-1]:.4f}  min={mins[-1]:.4f}")

print(f"\nOntology {ver}, {N} runs, {len(holdout)} holdout tickets")
print(f"mean confidence: min={min(means):.4f} max={max(means):.4f} "
      f"spread={max(means)-min(means):.4f} std={__import__('statistics').pstdev(means):.4f}")
