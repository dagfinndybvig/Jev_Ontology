"""Measure humanoid_taxonomy_v7 on the personal collection's labeled records.

The v7 adoption decision was made on the stand-in corpus's held-out
batch (89% vs v4's 85%). This run re-measures v7 on the personal
collection's 85 labeled records (manual_correction blocks in
humanoid_pilot_results.json) before touching the script defaults:
if v7 holds there too, its default can be switched everywhere; if it
regresses, the gains are corpus-specific.

One Jev call per record on the stored descriptions (no vision calls);
the baseline is v4's stored answers, the answers the review judged.
Results are saved incrementally to taxonomy_v7_personal_results.json
(private, gitignored); records with status ok are skipped on re-run.

Requires TYPESAFE_API_KEY.
"""
import json
import os
import sys
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY = os.path.join(SCRIPT_DIR, os.environ.get("TAXONOMY", "humanoid_taxonomy_v7.json"))
SOURCE = os.path.join(SCRIPT_DIR, "humanoid_pilot_results.json")
RESULTS = os.path.join(SCRIPT_DIR, os.environ.get(
    "RESULTS_OUT", "taxonomy_v7_personal_results.json"))

API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DELAY = 0.25
REVIEW_THRESHOLD = 0.7
FACETS = ["contains_human", "contains_robot", "contains_android",
          "primary_subject", "representation"]


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
    version = tax["_meta"]["version"]
    print(f"Measuring {version} on the personal collection's labeled records")

    with open(SOURCE, encoding="utf-8") as f:
        source = json.load(f)
    items = [(name, rec) for name, rec in source.items()
             if "manual_correction" in rec]
    print(f"Labeled records: {len(items)}")

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
        out_rec = {"file": name, "status": "error"}
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

    # Comparison: this version's answers vs manual corrections, v4's
    # stored answers vs manual corrections, on the same records.
    ok = {n: r for n, r in results.items() if r.get("status") == "ok"}
    print(f"\nMeasured: {len(ok)}/{len(items)}")

    def report(label, choice_of, conf_of):
        per = {}
        pa = pn = 0
        wrong = set()
        for name in ok:
            lm = source[name]["manual_correction"]["correct"]
            for facet in FACETS:
                lab = lm.get(facet)
                if lab is None:
                    continue
                per.setdefault(facet, [0, 0])
                per[facet][1] += 1
                pn += 1
                if choice_of(name)[facet] == lab:
                    per[facet][0] += 1
                    pa += 1
                else:
                    wrong.add(name)
        routed = {n for n in ok if any(conf_of(n)[q] < REVIEW_THRESHOLD for q in FACETS)}
        print(f"\n{label}: pooled {pa}/{pn} ({100 * pa / pn:.0f}%), "
              f"{len(wrong)} wrong, {len(routed)} threshold-routed "
              f"({100 * len(routed) / len(ok):.0f}%), {len(wrong & routed)} caught")
        for facet in FACETS:
            a, n = per[facet]
            print(f"  {facet}: {a}/{n} ({100 * a / n:.0f}%)")
        return wrong

    new_choice = lambda n: {q: ok[n][q]["choice"] for q in FACETS}
    new_conf = lambda n: {q: ok[n][q]["confidence"] for q in FACETS}
    v4_choice = lambda n: {q: source[n][q]["choice"] for q in FACETS}
    v4_conf = lambda n: {q: source[n][q]["confidence"] for q in FACETS}

    w_new = report(version, new_choice, new_conf)
    w_v4 = report("v4 (stored)", v4_choice, v4_conf)
    print(f"\n{version} fixes (v4 wrong, new right): {len(w_v4 - w_new)}")
    print(f"{version} breaks (v4 right, new wrong): {len(w_new - w_v4)}")


if __name__ == "__main__":
    main()
