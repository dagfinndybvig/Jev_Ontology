"""Copy the images Jev classified as containing a human into PICTURES_DIR\\Humans."""
import json
import os
import shutil

PICTURES = os.environ.get("PICTURES_DIR", "")  # folder of classified images
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_human_results.json")
DST = os.path.join(PICTURES, "Humans")


def main():
    if not PICTURES or not os.path.isdir(PICTURES):
        raise SystemExit("Set PICTURES_DIR to the folder of classified images")

    with open(RESULTS, "r", encoding="utf-8") as f:
        data = json.load(f)

    humans = [r["file"] for r in data.values() if r.get("status") == "ok" and r["choice"] == "yes"]
    os.makedirs(DST, exist_ok=True)

    copied = 0
    missing = []
    for name in humans:
        src = os.path.join(PICTURES, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(DST, name))
            copied += 1
        else:
            missing.append(name)

    print(f"Human-classified images: {len(humans)}")
    print(f"Copied to {DST}: {copied}")
    if missing:
        print(f"Missing source files ({len(missing)}):")
        for m in missing:
            print(f"  {m}")


if __name__ == "__main__":
    main()
