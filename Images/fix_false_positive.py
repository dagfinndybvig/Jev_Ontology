"""Remove a false positive (screenshot of text) from the Humans folder and correct the records."""
import json
import os

PICTURES = r"C:\Users\you\Pictures"
HUMANS = os.path.join(PICTURES, "Humans")
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_human_results.json")
TARGET = "[redacted]"

# 1. Remove the copy from the Humans folder (original stays in Pictures root).
fp = os.path.join(HUMANS, TARGET)
if os.path.exists(fp):
    os.remove(fp)
    print(f"Removed {TARGET} from Humans folder")
else:
    print(f"{TARGET} not found in Humans folder")

# 2. Correct the record in the results JSON.
with open(RESULTS, "r", encoding="utf-8") as f:
    data = json.load(f)

if TARGET in data:
    rec = data[TARGET]
    rec["choice"] = "no"
    rec["confidence"] = 1.0
    rec["probabilities"] = {"yes": 0.0, "no": 1.0}
    rec["corrected"] = True
    rec["note"] = "Manual correction: image is a screenshot of text describing a photo, not a photo of a human."
    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Corrected record for {TARGET} in results JSON")
else:
    print(f"{TARGET} not found in results JSON")

# 3. Report new counts.
ok = [r for r in data.values() if r.get("status") == "ok"]
yes = [r for r in ok if r["choice"] == "yes"]
no = [r for r in ok if r["choice"] == "no"]
print(f"OK={len(ok)}  human={len(yes)}  no-human={len(no)}")
