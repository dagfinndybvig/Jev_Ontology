"""Verified-subset analysis for the replication corpus (protocol step 4/5).

Compares the three existing runs (replication_results_run{1,2,3}.json)
against the hand-verified ground truth in replication_manifest.json. No API
calls. Ground truth derivation:

    verified True                  -> effective category = manifest category
    verified False, not "exclude"  -> effective category = verified_category
    verified False, "exclude"      -> excluded from scoring
    verified None (dead links)     -> excluded (never measured)

Facets the effective category cannot determine are ambiguous and excluded
from strict agreement (same INTENDED table as measure_replication.py).
Reports per-facet, pooled, per-category, routing burden, and the auto-accept
band mismatch with a Wilson 95% CI.

Usage:
    python analyze_verified.py
"""
import json
import math
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from routing import route_reason  # the adopted rule: threshold OR text signal

MANIFEST = os.path.join(SCRIPT_DIR, "replication_manifest.json")
RUNS = [1, 2, 3]

INTENDED = {
    "portrait_photo": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "human", "representation": "photograph",
    },
    "human_painting": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "human", "representation": "illustration",
    },
    "human_sculpture": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "human", "representation": "statue_or_render",
    },
    "graphic_design": {
        "contains_human": "ambiguous", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "ambiguous", "representation": "ambiguous",
    },
}

FACETS = ["contains_human", "contains_robot", "contains_android",
          "primary_subject", "representation"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d * 100, (c + h) / d * 100)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    recs = {k: v for k, v in manifest.items()
            if isinstance(v, dict) and "category" in v}

    effective = {}
    excluded = set()
    counts = {}
    for k, v in recs.items():
        ver = v.get("verified")
        if ver is True:
            effective[k] = v["category"]
        elif ver is False:
            vc = v.get("verified_category")
            if vc == "exclude":
                excluded.add(k)
            else:
                effective[k] = vc
        else:
            excluded.add(k)
        c = v["category"]
        counts.setdefault(c, {"correct": 0, "corrected": 0, "excluded": 0})
        if ver is True:
            counts[c]["correct"] += 1
        elif ver is False:
            counts[c]["excluded" if v.get("verified_category") == "exclude"
                      else "corrected"] += 1

    print("=== Verification decisions (manifest) ===")
    for c in sorted(counts):
        print("  %s: %s" % (c, counts[c]))
    n_eff = len(effective)
    n_exc = len(excluded)
    print("  effective ground truth: %d records, %d excluded" % (n_eff, n_exc))

    for run in RUNS:
        path = os.path.join(SCRIPT_DIR, "replication_results_run%d.json" % run)
        with open(path, encoding="utf-8") as f:
            results = json.load(f)
        ok = {k: r for k, r in results.items()
              if r.get("status") == "ok" and k in effective}

        match = {q: 0 for q in FACETS}
        scored = {q: 0 for q in FACETS}
        per_cat = {}
        band_n = band_miss = 0
        routed = 0
        for fname, rec in sorted(ok.items()):
            want = INTENDED[effective[fname]]
            c = per_cat.setdefault(effective[fname], {"n": 0, "match": 0, "scored": 0})
            c["n"] += 1
            is_routed = False
            for q in FACETS:
                exp = want[q]
                if exp == "ambiguous":
                    continue
                scored[q] += 1
                c["scored"] += 1
                if rec[q]["choice"] == exp:
                    match[q] += 1
                    c["match"] += 1
            if route_reason(rec):
                routed += 1
            if not is_routed:
                band_n += 1
                if any(want[q] != "ambiguous" and rec[q]["choice"] != want[q]
                       for q in FACETS):
                    band_miss += 1

        pooled_m = sum(match.values())
        pooled_s = sum(scored.values())
        print("\n=== Run %d vs. verified labels (n=%d) ===" % (run, len(ok)))
        for q in FACETS:
            n = scored[q]
            if n:
                print("  %s: %d/%d (%.0f%%)" % (q, match[q], n, match[q] / n * 100))
        print("  pooled: %d/%d (%.1f%%)" % (pooled_m, pooled_s, pooled_m / pooled_s * 100))
        print("  --- per category ---")
        for cat in sorted(per_cat):
            c = per_cat[cat]
            pct = ("%.0f%%" % (c["match"] / c["scored"] * 100)) if c["scored"] else "n/a"
            print("  %s: %d/%d (%s) of %d images" % (cat, c["match"], c["scored"], pct, c["n"]))
        print("  routing burden: %d/%d (%.0f%%)" % (routed, len(ok), routed / len(ok) * 100))
        lo, hi = wilson(band_miss, band_n)
        print("  auto-accept band: %d/%d mismatch (%.0f%%, Wilson 95%% CI %.0f-%.0f%%)"
              % (band_miss, band_n, band_miss / band_n * 100, lo, hi))

    # human_sculpture both ways (run 1)
    with open(os.path.join(SCRIPT_DIR, "replication_results_run1.json"), encoding="utf-8") as f:
        r1 = json.load(f)
    kept = {k: v for k, v in recs.items()
            if k in effective and effective[k] == "human_sculpture" and k in r1
            and r1[k].get("status") == "ok"}
    m = s = 0
    for k in kept:
        want = INTENDED["human_sculpture"]
        for q in FACETS:
            if want[q] == "ambiguous":
                continue
            s += 1
            if r1[k][q]["choice"] == want[q]:
                m += 1
    print("\n=== human_sculpture, verified subset only (run 1) ===")
    print("  %d/%d (%.0f%%) -- the %d excluded animal-sculpture records are out"
          % (m, s, m / s * 100, counts["human_sculpture"]["excluded"]))


if __name__ == "__main__":
    main()
