"""Summarize image_human_results.json into a sorted human / no-human list."""
import json
import os

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_human_results.json")

with open(RESULTS, "r", encoding="utf-8") as f:
    data = json.load(f)

ok = [r for r in data.values() if r.get("status") == "ok"]
yes = sorted([r for r in ok if r["choice"] == "yes"], key=lambda r: -r["confidence"])
no = sorted([r for r in ok if r["choice"] == "no"], key=lambda r: -r["confidence"])

print(f"TOTAL OK: {len(ok)}   HUMAN: {len(yes)}   NO-HUMAN: {len(no)}\n")

print("=" * 70)
print(f"CONTAINS HUMAN ({len(yes)})")
print("=" * 70)
for r in yes:
    print(f"  {r['confidence']:.3f}  {r['file']}")

print()
print("=" * 70)
print(f"NO HUMAN ({len(no)})")
print("=" * 70)
for r in no:
    print(f"  {r['confidence']:.3f}  {r['file']}")
