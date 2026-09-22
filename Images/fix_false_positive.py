"""Remove a false positive from the Humans folder and correct the record.

Usage: python fix_false_positive.py <filename>

The correction preserves Jev's raw output under the record's "jev" key, so the
manual override never destroys the model's actual answer. Idempotent: safe to
re-run; a record that is already corrected is left untouched.
"""
import json
import os
import sys

PICTURES = os.environ.get("PICTURES_DIR", "")  # folder of classified images
HUMANS = os.path.join(PICTURES, "Humans") if PICTURES else ""
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_human_results.json")

if len(sys.argv) < 2:
    raise SystemExit("usage: python fix_false_positive.py <filename>")
TARGET = sys.argv[1]

# 1. Remove the copy from the Humans folder (original stays in the image folder).
if HUMANS and os.path.isdir(HUMANS):
    fp = os.path.join(HUMANS, TARGET)
    if os.path.exists(fp):
        os.remove(fp)
        print(f"Removed {TARGET} from Humans folder")
    else:
        print(f"{TARGET} not found in Humans folder")
else:
    print("PICTURES_DIR not set; skipping Humans folder cleanup")

# 2. Correct the record, preserving the raw Jev output.
with open(RESULTS, "r", encoding="utf-8") as f:
    data = json.load(f)

if TARGET not in data:
    print(f"{TARGET} not found in results JSON")
else:
    rec = data[TARGET]
    if rec.get("corrected"):
        print(f"{TARGET} already corrected; nothing to do")
    else:
        rec["jev"] = {k: rec[k] for k in ("choice", "confidence", "probabilities")}
        rec["choice"] = "no"
        rec["confidence"] = 1.0
        rec["probabilities"] = {"yes": 0.0, "no": 1.0}
        rec["corrected"] = True
        rec["correction_note"] = (
            "Manual correction: the image does not contain a human. "
            "Jev's raw answer is preserved under 'jev'."
        )
        with open(RESULTS, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Corrected record for {TARGET} (raw Jev output preserved under 'jev')")

# 3. Report new counts.
ok = [r for r in data.values() if r.get("status") == "ok"]
yes = [r for r in ok if r["choice"] == "yes"]
no = [r for r in ok if r["choice"] == "no"]
print(f"OK={len(ok)}  human={len(yes)}  no-human={len(no)}")
