"""Pilot: re-classify the stored image descriptions against a humanoid taxonomy.

Uses humanoid_taxonomy_v2.json by default; set the TAXONOMY environment
variable (a bare filename in this directory) to run against another version.

One Jev call per image carries all five facet questions (contains_human,
contains_robot, contains_android, primary_subject, representation) in a
single parallel pass. Results are saved incrementally to
humanoid_pilot_results.json (private, gitignored) so the run can be resumed;
errored records are retried on the next run.

Also checks contains_human against the original run's raw Jev answer as a
consistency measure, and prints a review queue of low-confidence records.

Requires TYPESAFE_API_KEY. Reads the private image_human_results.json
(never pushed).
"""
import json
import os
import sys
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY = os.path.join(SCRIPT_DIR, os.environ.get("TAXONOMY", "humanoid_taxonomy_v2.json"))
SOURCE = os.path.join(SCRIPT_DIR, "image_human_results.json")
RESULTS = os.path.join(SCRIPT_DIR, "humanoid_pilot_results.json")

API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DELAY = 0.25  # seconds between images
REVIEW_THRESHOLD = 0.7


def jev_classify_facets(state, facets):
    body = {
        "model": "jev-latest",
        "state": state,
        "questions": facets,
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = {}
    for qname in facets:
        ans = data["answers"][qname]
        out[qname] = {
            "choice": ans["choice"],
            "confidence": ans["confidence"],
            "probabilities": ans["probabilities"],
        }
    out["usage"] = data.get("usage", {})
    return out


def load_results():
    if os.path.exists(RESULTS):
        with open(RESULTS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_results(results):
    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def main():
    if not API_KEY:
        print("Missing TYPESAFE_API_KEY")
        sys.exit(1)

    with open(TAXONOMY, "r", encoding="utf-8") as f:
        tax = json.load(f)
    facets = tax["facets"]

    with open(SOURCE, "r", encoding="utf-8") as f:
        source = json.load(f)
    items = [(name, rec) for name, rec in source.items() if rec.get("status") == "ok"]
    print(f"Source descriptions: {len(items)}")

    results = load_results()
    done = {n for n, r in results.items() if r.get("status") == "ok"}
    todo = [(n, r) for n, r in items if n not in done]
    print(f"Already done: {len(done)}, to process: {len(todo)}")

    for i, (name, rec) in enumerate(todo, 1):
        desc = rec["description"]
        state = (
            f"Image description (written by a vision model that examined the image):\n"
            f"\"{desc}\"\n\n"
            f"Classify the depicted content according to the questions."
        )
        out_rec = {"file": name, "description": desc, "status": "error"}
        try:
            out_rec.update(jev_classify_facets(state, facets))
            out_rec["status"] = "ok"
            # Consistency check against the original run's raw Jev answer.
            raw_prev = rec.get("jev", rec)
            out_rec["previous_contains_human"] = raw_prev.get("choice")
        except Exception as e:
            out_rec["error"] = str(e)
        results[name] = out_rec
        save_results(results)
        if out_rec["status"] == "ok":
            confs = [out_rec[q]["confidence"] for q in facets]
            print(f"[{i}/{len(todo)}] {name}: {out_rec['primary_subject']['choice']}"
                  f" / {out_rec['representation']['choice']} (min conf {min(confs):.3f})")
        else:
            print(f"[{i}/{len(todo)}] {name}: ERROR {out_rec['error'][:80]}")
        time.sleep(DELAY)

    # Summary
    ok = [r for r in results.values() if r.get("status") == "ok"]
    errors = [r for r in results.values() if r.get("status") != "ok"]
    print(f"\nDone. OK={len(ok)} errors={len(errors)}")

    def dist(qname):
        counts = {}
        for r in ok:
            counts[r[qname]["choice"]] = counts.get(r[qname]["choice"], 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    for qname in ("primary_subject", "representation", "contains_human",
                  "contains_robot", "contains_android"):
        print(f"\n{qname}: {dist(qname)}")

    # Consistency with the original run
    agree = sum(1 for r in ok if r["contains_human"]["choice"] == r.get("previous_contains_human"))
    have_prev = sum(1 for r in ok if r.get("previous_contains_human"))
    print(f"\ncontains_human agrees with original run: {agree}/{have_prev}")

    # Review queue: any question below threshold
    queue = []
    for r in ok:
        weak = [(q, r[q]["choice"], round(r[q]["confidence"], 3))
                for q in facets if r[q]["confidence"] < REVIEW_THRESHOLD]
        if weak:
            queue.append((min(w[2] for w in weak), r["file"], weak))
    queue.sort()
    print(f"\nReview queue (<{REVIEW_THRESHOLD} on any question): {len(queue)}")
    for minconf, name, weak in queue:
        details = ", ".join(f"{q}:{c}({cf})" for q, c, cf in weak)
        print(f"  {minconf:.3f}  {name}  [{details}]")


if __name__ == "__main__":
    main()
