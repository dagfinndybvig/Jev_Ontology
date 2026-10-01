"""Copy each image into PICTURES_DIR\\Humanoids, sorted by its pilot classification.

Reads the private humanoid_pilot_results.json (one record per image with
all five facet answers) and copies each source image -- originals are never
moved -- into:

    Humanoids/<primary_subject>/<representation>/<file>

Images hedging on any facet (confidence < REVIEW_THRESHOLD) or carrying
a text-bearing signal (the Option 2 routing rule, routing.py) are also
copied into Humanoids/_review/ for visual verification of the taxonomy's
weak spots. Records carrying a "manual_correction" (e.g. the
screenshot-of-text false positive) sort by their corrected labels and are
always copied to _review/.
"""
import json
import os
import shutil
import sys
from pathlib import Path
from json_store import file_lock
from run_state import file_digest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from routing import route_reason

RESULTS = os.environ.get("SORT_RESULTS") or os.path.join(SCRIPT_DIR, "humanoid_pilot_results.json")
PICTURES = os.environ.get("PICTURES_DIR", "")
DST = os.path.join(PICTURES, "Humanoids")

FACETS = ["contains_human", "contains_robot", "contains_android", "primary_subject", "representation"]
REVIEW_THRESHOLD = 0.7
TAXONOMY = os.path.join(SCRIPT_DIR, os.environ.get("TAXONOMY", "humanoid_taxonomy_v9.json"))


def reconcile_copies(source, desired, known, root):
    """Remove only obsolete byte-identical copies inside the managed tree."""
    source, root = Path(source), Path(root).resolve()
    desired = {Path(p) for p in desired}
    known = {Path(p) for p in known} | desired
    source_hash = file_digest(source)
    for path in known:
        if not path.resolve().is_relative_to(root):
            raise ValueError("Sorted destination escapes the managed tree")
        if path.exists() and (not path.is_file() or file_digest(path) != source_hash):
            raise ValueError("A sorted copy differs from its source; preserve it before re-sorting")
    for path in desired:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            shutil.copy2(source, path)
    for path in known - desired:
        if path.is_file():
            path.unlink()


def main():
    if not PICTURES or not os.path.isdir(PICTURES):
        raise SystemExit("Set PICTURES_DIR to the folder of classified images")

    if Path(DST).resolve().parent != Path(PICTURES).resolve():
        raise ValueError("Sorted root must be directly inside PICTURES_DIR")
    with file_lock(os.path.join(DST, ".sorting")):
        with file_lock(RESULTS):
            with open(RESULTS, "r", encoding="utf-8") as f:
                data = json.load(f)
            sort_records(data)


def sort_records(data):
    with open(TAXONOMY, encoding="utf-8") as f:
        facets = json.load(f)["facets"]
    subjects = facets["primary_subject"]["criteria"]
    representations = facets["representation"]["criteria"]

    copied = 0
    review_copied = 0
    missing = []
    for fname, r in data.items():
        if r.get("status") != "ok":
            continue
        if os.path.basename(fname) != fname or "/" in fname or "\\" in fname:
            raise ValueError("Invalid image filename in sorting results")
        src = os.path.join(PICTURES, fname)
        if not os.path.exists(src):
            missing.append(fname)
            continue

        corr = (r.get("manual_correction") or {}).get("correct") or {}
        subject = corr.get("primary_subject", r["primary_subject"]["choice"])
        rep = corr.get("representation", r["representation"]["choice"])
        if subject not in subjects or rep not in representations:
            raise ValueError("Invalid corrected classification for sorting")
        folder = os.path.join(DST, subject, rep)
        desired = {os.path.join(folder, fname)}
        review = os.path.join(DST, "_review", fname)
        needs_review = bool(corr) or route_reason(r) is not None
        if needs_review:
            desired.add(review)
        known = {os.path.join(DST, s, p, fname) for s in subjects for p in representations}
        known.add(review)
        reconcile_copies(src, desired, known, DST)
        copied += 1

        if needs_review:
            review_copied += 1

    print(f"Records: {len(data)}")
    print(f"Copied into {DST}: {copied}")
    print(f"Review copies (routing rule: any facet < {REVIEW_THRESHOLD} or text-bearing): {review_copied}")
    if missing:
        print(f"Missing source files ({len(missing)}):")
        for m in missing:
            print(f"  {m}")
        raise SystemExit("Sorting incomplete: source images are missing")


if __name__ == "__main__":
    main()
