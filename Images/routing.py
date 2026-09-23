"""Option 2: review-always routing for the text-bearing family.

The vision model cannot distinguish "a photograph of a text-bearing
object" from "a flat digital capture" (measured: embedded clause,
physical-context clause, and an isolated binary question all failed --
see RESULTS.md). The remaining fix is routing, not perception.

The routing rule (adopted 2026-09-23, measured on the 85 labeled
records):
  route to review if
    - any facet confidence < 0.7 (the existing queue rule), OR
    - the description carries a text-bearing signal (is a screenshot,
      screenshot shows, consists of text, terminal, scan of, readout,
      interface) after stripping the vision prompt's preamble.

Measured trade-off (labeled 85 / full 218):
  current rule only:  burden 52% / 20%   catches 18/27 errors
  + text signal:      burden 86% / 72%   catches 25/27 errors
The cataloger chooses the trade; this script defaults to the adopted
rule. Prints the routed queue and writes routing_queue.json (private,
gitignored).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CASCADE_RESULTS = os.path.join(HERE, "humanoid_pilot_results.json")
OUT = os.path.join(HERE, "routing_queue.json")
FACETS = ["contains_human", "contains_robot", "contains_android",
          "primary_subject", "representation"]
THRESHOLD = 0.7

# Text-bearing signals in the description (the vision prompt states the
# medium first, so these phrases are reliable). The preamble line
# ("This image does not consist of text...") is stripped before matching.
TEXT_PATTERN = re.compile(
    r"is a screenshot|screenshot shows|consists of text|terminal|scan of|readout|interface"
)


def description_body(desc):
    lines = [ln for ln in desc.split("\n") if ln.strip()]
    if lines and lines[0].lower().startswith("this image does not consist"):
        lines = lines[1:]
    return " ".join(lines).lower()


def route_reason(rec):
    """None if the record auto-classifies; otherwise why it needs review."""
    if any(rec[f]["confidence"] < THRESHOLD for f in FACETS):
        return "low_confidence"
    if TEXT_PATTERN.search(description_body(rec.get("description", ""))):
        return "text_bearing"
    return None


def route(rec):
    """True if the record should be routed to human review."""
    return route_reason(rec) is not None


def main():
    if not os.path.exists(CASCADE_RESULTS):
        print("No humanoid_pilot_results.json")
        sys.exit(1)
    with open(CASCADE_RESULTS, "r", encoding="utf-8") as f:
        cascade = json.load(f)
    recs = {n: r for n, r in cascade.items() if r.get("status") == "ok"}

    queue = []
    for name, rec in sorted(recs.items()):
        reason = route_reason(rec)
        if reason:
            weak = [(f, rec[f]["choice"], round(rec[f]["confidence"], 3))
                    for f in FACETS if rec[f]["confidence"] < THRESHOLD]
            queue.append({
                "file": name,
                "reason": reason,
                "weak_facets": weak,
                "text_signal": reason == "text_bearing",
            })

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)

    low = sum(1 for q in queue if q["reason"] == "low_confidence")
    text = sum(1 for q in queue if q["reason"] == "text_bearing")
    print(f"Routed to review: {len(queue)} of {len(recs)} "
          f"({len(queue) / len(recs) * 100:.0f}%)")
    print(f"  low-confidence (<{THRESHOLD}): {low}")
    print(f"  text-bearing signal only: {text}")
    print(f"Written to {OUT}")


if __name__ == "__main__":
    main()
