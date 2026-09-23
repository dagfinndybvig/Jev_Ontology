"""Run the production pipeline on the stand-in library corpus and measure it.

For each image in library_manifest.json: Pixtral describes it (same prompt as
classify_images.py), Jev answers the five facets (v4 taxonomy, same call shape
as pilot_humanoid.py). Answers are compared to the labels the manifest
category implies; facets the category cannot determine are marked ambiguous
and excluded from strict agreement. Also applies routing.py's route_reason
and reports the burden per category.

Caveat: Commons categories are noisy labels (e.g. Category:Statues includes
non-humanoid statues); the per-image depicts statements would be precise once
that resolution works. Treat mismatches as review candidates, not verdicts.

Results are saved incrementally to library_standin_results.json (gitignored);
images with status ok are skipped. Requires MISTRAL_API_KEY and TYPESAFE_API_KEY.
"""
import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from classify_images import describe_image  # same vision prompt as the pipeline
from pilot_humanoid import jev_classify_facets, TAXONOMY  # v4 by default
from routing import route_reason  # the adopted rule: threshold OR text signal

MANIFEST = os.path.join(SCRIPT_DIR, "library_manifest.json")
RESULTS = os.path.join(SCRIPT_DIR, "library_standin_results.json")
IMAGES_DIR = os.environ.get("LIBRARY_STANDIN_DIR") or os.path.join(SCRIPT_DIR, "library_standin")

DELAY = 0.4

# Labels the manifest category implies. "ambiguous" = the category cannot
# determine the facet (excluded from strict agreement, reported separately).
INTENDED = {
    "statue": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "human", "representation": "statue_or_render",
    },
    "humanoid_robot": {
        "contains_human": "no", "contains_robot": "yes", "contains_android": "no",
        "primary_subject": "robot", "representation": "ambiguous",
    },
    "book_cover": {
        "contains_human": "ambiguous", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "ambiguous", "representation": "ambiguous",
    },
    "human_photo": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "human", "representation": "photograph",
    },
    "human_illustration": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "human", "representation": "illustration",
    },
    "ui_screenshot": {
        "contains_human": "ambiguous", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "ambiguous", "representation": "text_screenshot",
    },
}

FACETS = ["contains_human", "contains_robot", "contains_android",
          "primary_subject", "representation"]


def load_results():
    if os.path.exists(RESULTS):
        with open(RESULTS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_results(results):
    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    with open(TAXONOMY, "r", encoding="utf-8") as f:
        tax = json.load(f)
    facets = tax["facets"]

    with open(MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    items = [(k, v) for k, v in manifest.items() if v.get("status") == "ok"]
    print(f"Corpus images: {len(items)}")

    results = load_results()
    done = {k for k, r in results.items() if r.get("status") == "ok"}
    todo = [(k, v) for k, v in items if k not in done]
    print(f"Already done: {len(done)}, to process: {len(todo)}")

    for i, (fname, rec) in enumerate(todo, 1):
        path = os.path.join(IMAGES_DIR, rec["file"])
        out = {"category": rec["category"], "title": rec["title"], "status": "error"}
        try:
            desc = describe_image(path)
            out["description"] = desc
            state = (
                f"Image description (written by a vision model that examined the image):\n"
                f"\"{desc}\"\n\n"
                f"Classify the depicted content according to the questions."
            )
            out.update(jev_classify_facets(state, facets))
            out["status"] = "ok"
        except Exception as e:
            out["error"] = str(e)
        results[fname] = out
        save_results(results)
        if out["status"] == "ok":
            confs = [out[q]["confidence"] for q in FACETS]
            print(f"[{i}/{len(todo)}] {fname}: {out['primary_subject']['choice']}"
                  f" / {out['representation']['choice']} (min conf {min(confs):.3f})")
        else:
            print(f"[{i}/{len(todo)}] {fname}: ERROR {out['error'][:80]}")
        time.sleep(DELAY)

    # Comparison against the category-implied labels
    ok = {k: r for k, r in results.items() if r.get("status") == "ok"}
    if not ok:
        print("\nNothing measured.")
        return

    match = {q: 0 for q in FACETS}
    scored = {q: 0 for q in FACETS}
    per_cat = {}
    for fname, rec in sorted(ok.items()):
        want = INTENDED[rec["category"]]
        c = per_cat.setdefault(rec["category"], {"n": 0, "match": 0, "scored": 0})
        c["n"] += 1
        for q in FACETS:
            exp = want[q]
            if exp == "ambiguous":
                continue
            scored[q] += 1
            c["scored"] += 1
            if rec[q]["choice"] == exp:
                match[q] += 1
                c["match"] += 1

    print(f"\n=== Corpus vs. category-implied labels (n={len(ok)}) ===")
    for q in FACETS:
        n = scored[q]
        print(f"  {q}: {match[q]}/{n} ({match[q] / n * 100:.0f}%)" if n else f"  {q}: 0/0")

    print("\n=== Per category ===")
    for cat in sorted(per_cat):
        c = per_cat[cat]
        pct = f"{c['match'] / c['scored'] * 100:.0f}%" if c["scored"] else "n/a"
        print(f"  {cat}: {c['match']}/{c['scored']} ({pct}) of {c['n']} images")

    # Routing burden per category
    print("\n=== Routing (route_reason) ===")
    burden = {}
    for fname, rec in sorted(ok.items()):
        reason = route_reason(rec) or "auto-accept"
        burden.setdefault(rec["category"], {}).setdefault(reason, 0)
        burden[rec["category"]][reason] += 1
    total_routed = sum(n for d in burden.values()
                       for r, n in d.items() if r != "auto-accept")
    for cat in sorted(burden):
        print(f"  {cat}: {burden[cat]}")
    print(f"  TOTAL routed: {total_routed}/{len(ok)} ({total_routed / len(ok) * 100:.0f}%)")


if __name__ == "__main__":
    main()
