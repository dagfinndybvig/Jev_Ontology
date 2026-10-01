"""Copy the images Jev classified as containing a human into PICTURES_DIR\\Humans."""
import json
import os
from pathlib import Path
from sort_humanoids import reconcile_copies
from json_store import file_lock

PICTURES = os.environ.get("PICTURES_DIR", "")  # folder of classified images
RESULTS = os.environ.get("SORT_RESULTS") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "image_human_results.json")
DST = os.path.join(PICTURES, "Humans")


def main():
    if not PICTURES or not os.path.isdir(PICTURES):
        raise SystemExit("Set PICTURES_DIR to the folder of classified images")
    if Path(DST).resolve().parent != Path(PICTURES).resolve():
        raise ValueError("Sorted root must be directly inside PICTURES_DIR")

    with open(RESULTS, "r", encoding="utf-8") as f:
        data = json.load(f)

    humans = [r["file"] for r in data.values() if r.get("status") == "ok" and r["choice"] == "yes"]
    os.makedirs(DST, exist_ok=True)

    copied = 0
    missing = []
    for r in data.values():
        if r.get("status") != "ok":
            continue
        name = r["file"]
        if os.path.basename(name) != name or "/" in name or "\\" in name:
            raise ValueError("Invalid image filename in sorting results")
        src = os.path.join(PICTURES, name)
        if os.path.exists(src):
            dest = os.path.join(DST, name)
            with file_lock(os.path.join(DST, ".sorting")):
                reconcile_copies(src, [dest] if r["choice"] == "yes" else [], [dest], DST)
            copied += r["choice"] == "yes"
        else:
            missing.append(name)

    print(f"Human-classified images: {len(humans)}")
    print(f"Copied to {DST}: {copied}")
    if missing:
        print(f"Missing source files ({len(missing)}):")
        for m in missing:
            print(f"  {m}")
        raise SystemExit("Sorting incomplete: source images are missing")


if __name__ == "__main__":
    main()
