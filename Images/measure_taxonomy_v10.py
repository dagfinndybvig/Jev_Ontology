"""Held-out measurement of humanoid_taxonomy_v10 on the stand-in corpus.

Split-half protocol (same deterministic md5(filename) first-hex-char
parity as author_taxonomy_v9.py / author_taxonomy_v10.py): v10 was
authored from the authoring half's residuals (side A); this run
measures it on the measurement half (side M), which no authoring has
ever seen. The `side` function must stay identical to the authoring
scripts'.

One Jev call per record carries the five facet questions with the v10
criteria, on the same descriptions and in the same call shape as
measure_taxonomy_v9.py. No vision calls. Results are saved
incrementally to taxonomy_v10_halfM_results.json (private,
gitignored); records with status ok are skipped on re-run.

The comparison baseline is v9's stored answers in
library_standin_results.json (the answers the review judged).

Requires TYPESAFE_API_KEY.
"""
import hashlib
import json
import os
import sys
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY = os.path.join(SCRIPT_DIR, os.environ.get("TAXONOMY", "humanoid_taxonomy_v10.json"))
SOURCE = os.path.join(SCRIPT_DIR, "library_standin_results.json")
RESULTS = os.path.join(SCRIPT_DIR, os.environ.get(
    "RESULTS_OUT", "taxonomy_v10_halfM_results.json"))

API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DELAY = 0.25
REVIEW_THRESHOLD = 0.7
FACETS = ["contains_human", "contains_robot", "contains_android",
          "primary_subject", "representation"]


def side(name):
    """Must match author_taxonomy_v9.py / author_taxonomy_v10.py."""
    return "A" if int(hashlib.md5(name.encode()).hexdigest()[0], 16) % 2 == 0 else "M"


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
        with open(RESULTS, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_results(results):
    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def main():
    if not API_KEY:
        print("Missing TYPESAFE_API_KEY")
        sys.exit(1)

    with open(TAXONOMY, encoding="utf-8") as f:
        tax = json.load(f)
    facets = tax["facets"]

    with open(SOURCE, encoding="utf-8") as f:
        source = json.load(f)
    items = [(name, rec) for name, rec in source.items()
             if rec.get("manual_correction") and side(name) == "M"]
    print(f"Measurement half (side M): {len(items)} labeled records")

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
        out_rec = {"file": name, "category": rec["category"], "status": "error"}
        try:
            out_rec.update(jev_classify_facets(state, facets))
            out_rec["status"] = "ok"
        except Exception as e:
            out_rec["error"] = str(e)
        results[name] = out_rec
        save_results(results)
        if out_rec["status"] == "ok":
            confs = [out_rec[q]["confidence"] for q in FACETS]
            print(f"[{i}/{len(todo)}] {name}: {out_rec['primary_subject']['choice']}"
                  f" / {out_rec['representation']['choice']} (min conf {min(confs):.3f})")
        else:
            print(f"[{i}/{len(todo)}] {name}: ERROR {out_rec['error'][:80]}")
        time.sleep(DELAY)

    # Comparison: v10 answers vs manual corrections, v9 stored answers vs
    # manual corrections, on the same records.
    ok = {n: r for n, r in results.items() if r.get("status") == "ok"}
    print(f"\nMeasured: {len(ok)}/{len(items)}")

    def score(pick):
        per_facet = {}
        pooled_a = pooled_n = 0
        for facet in FACETS:
            a = n = 0
            for name, rec in ok.items():
                label = source[name]["manual_correction"]["correct"].get(facet)
                if label is None:
                    continue
                n += 1
                if pick(name, rec)[facet] == label:
                    a += 1
            per_facet[facet] = (a, n)
            pooled_a += a
            pooled_n += n
        return per_facet, pooled_a, pooled_n

    v10 = lambda name, rec: {q: rec[q]["choice"] for q in FACETS}
    v9 = lambda name, rec: {q: source[name][q]["choice"] for q in FACETS}

    version = tax["_meta"]["version"]
    for label, pick in ((version, v10), ("v9 (stored)", v9)):
        per_facet, pa, pn = score(pick)
        print(f"\n{label}: pooled {pa}/{pn} ({100 * pa / pn:.0f}%)")
        for facet, (a, n) in per_facet.items():
            print(f"  {facet}: {a}/{n} ({100 * a / n:.0f}%)")

    # Per-record fixes and breaks (v10 vs v9 stored, against the corrections).
    fixes = breaks = 0
    for name, rec in ok.items():
        v10_wrong = any(v10(name, rec)[q] != source[name]["manual_correction"]["correct"].get(q)
                        for q in FACETS
                        if source[name]["manual_correction"]["correct"].get(q) is not None)
        v9_wrong = any(v9(name, rec)[q] != source[name]["manual_correction"]["correct"].get(q)
                       for q in FACETS
                       if source[name]["manual_correction"]["correct"].get(q) is not None)
        if v9_wrong and not v10_wrong:
            fixes += 1
        elif v10_wrong and not v9_wrong:
            breaks += 1
    print(f"\nPer-record: v10 fixes {fixes} / breaks {breaks} (vs v9 stored)")

    # Errors (records with at least one wrong facet) and burden.
    for label, pick in ((version, v10), ("v9 (stored)", v9)):
        errors = [name for name, rec in ok.items()
                  if any(pick(name, rec)[q] != source[name]["manual_correction"]["correct"].get(q)
                         for q in FACETS
                         if source[name]["manual_correction"]["correct"].get(q) is not None)]
        routed = [name for name, rec in ok.items()
                  if any(rec[q]["confidence"] < REVIEW_THRESHOLD for q in FACETS)]
        caught = [name for name in errors if name in set(routed)]
        print(f"{label}: {len(errors)} wrong records, {len(routed)} routed "
              f"({100 * len(routed) / len(ok):.0f}% burden), {len(caught)} caught")


if __name__ == "__main__":
    main()
