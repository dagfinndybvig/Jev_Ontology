"""Copy each image into PICTURES_DIR\\Humanoids, sorted by its pilot classification.

Reads the private humanoid_pilot_results.json (one record per image with
all five facet answers) and copies each source image -- originals are never
moved -- into:

    Humanoids/<primary_subject>/<representation>/<file>

Images hedging on any facet (confidence < REVIEW_THRESHOLD) are also copied
into Humanoids/_review/ for visual verification of the taxonomy's weak spots.
Records carrying a "manual_correction" (e.g. the screenshot-of-text false
positive) sort by their corrected labels and are always copied to _review/.
"""
import json
import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(SCRIPT_DIR, "humanoid_pilot_results.json")
PICTURES = os.environ.get("PICTURES_DIR", "")
DST = os.path.join(PICTURES, "Humanoids")

FACETS = ["contains_human", "contains_robot", "contains_android", "primary_subject", "representation"]
REVIEW_THRESHOLD = 0.7


def main():
    if not PICTURES or not os.path.isdir(PICTURES):
        raise SystemExit("Set PICTURES_DIR to the folder of classified images")

    with open(RESULTS, "r", encoding="utf-8") as f:
        data = json.load(f)

    copied = 0
    review_copied = 0
    missing = []
    for fname, r in data.items():
        if r.get("status") != "ok":
            continue
        src = os.path.join(PICTURES, fname)
        if not os.path.exists(src):
            missing.append(fname)
            continue

        corr = r.get("manual_correction") or {}
        subject = corr.get("primary_subject", r["primary_subject"]["choice"])
        rep = corr.get("representation", r["representation"]["choice"])
        folder = os.path.join(DST, subject, rep)
        os.makedirs(folder, exist_ok=True)
        shutil.copy2(src, os.path.join(folder, fname))
        copied += 1

        if corr or any(r[f]["confidence"] < REVIEW_THRESHOLD for f in FACETS):
            os.makedirs(os.path.join(DST, "_review"), exist_ok=True)
            shutil.copy2(src, os.path.join(DST, "_review", fname))
            review_copied += 1

    print(f"Records: {len(data)}")
    print(f"Copied into {DST}: {copied}")
    print(f"Review copies (any facet < {REVIEW_THRESHOLD}): {review_copied}")
    if missing:
        print(f"Missing source files ({len(missing)}):")
        for m in missing:
            print(f"  {m}")


if __name__ == "__main__":
    main()
