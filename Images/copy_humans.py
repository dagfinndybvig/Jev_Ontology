"""Copy the images Jev classified as containing a human into Pictures\Humans."""
import json
import os
import shutil

PICTURES = r"C:\Users\you\Pictures"
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_human_results.json")
DST = os.path.join(PICTURES, "Humans")

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
