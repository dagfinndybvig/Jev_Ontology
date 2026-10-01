"""Run the production pipeline on the fresh replication corpus and measure it
(REPLICATION_PROTOCOL.md step 7).

For each image in replication_manifest.json: Pixtral describes it (same prompt
as classify_images.py), Jev answers the five facets (v9 taxonomy, same call
shape as pilot_humanoid.py). Answers are compared to the labels the manifest
category implies; facets the category cannot determine are marked ambiguous
and excluded from strict agreement. Also applies routing.py's route_reason
and reports the burden per category.

Frozen configuration (protocol step 6): v9 taxonomy, 0.7 threshold,
text-bearing routing rule, Pixtral prompt as-is. Nothing here is tuned.

Each invocation writes ONE run's results to a fresh file -- the measure
scripts skip records with status ok, so re-using a file would silently do
nothing (the v6 resume trap). Run-to-run variance needs 3 fresh files:

    python measure_replication.py 1    # replication_results_run1.json
    python measure_replication.py 2    # replication_results_run2.json
    python measure_replication.py 3    # replication_results_run3.json

Requires MISTRAL_API_KEY and TYPESAFE_API_KEY.
"""
import json
import os
import sys
import time
from json_store import load_json, save_json
from json_store import fingerprint
from run_state import file_digest, source_digest, prepare_run, require_complete
from corpus_state import require_sealed
import classify_images
import pilot_humanoid
import routing

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from classify_images import describe_image  # same vision prompt as the pipeline
from pilot_humanoid import jev_classify_facets, TAXONOMY  # v9 by default
from routing import route_reason  # the adopted rule: threshold OR text signal

MANIFEST = os.environ.get("REPLICATION_MANIFEST") or os.path.join(SCRIPT_DIR, "replication_manifest.json")
IMAGES_DIR = os.environ.get("REPLICATION_DIR") or os.path.join(SCRIPT_DIR, "replication_corpus")

DELAY = 0.4

# Labels the manifest category implies (REPLICATION_PROTOCOL.md "Final
# category definitions"). "ambiguous" = the category cannot determine the
# facet (excluded from strict agreement, reported separately).
INTENDED = {
    "portrait_photo": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "human", "representation": "photograph",
    },
    "human_painting": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "human", "representation": "illustration",
    },
    "human_sculpture": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "human", "representation": "statue_or_render",
    },
    "graphic_design": {
        "contains_human": "ambiguous", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "ambiguous", "representation": "ambiguous",
    },
}

FACETS = ["contains_human", "contains_robot", "contains_android",
          "primary_subject", "representation"]


def results_path(run):
    if not run.isdecimal() or int(run) < 1:
        raise ValueError("Run must be a positive integer")
    return os.environ.get("RESULTS_OUT") or os.path.join(
        SCRIPT_DIR, "replication_results_run%s.json" % run)


def require_frozen(tax):
    if fingerprint(tax) != "b645f980bb7d331b357cfcf13ceb6afeac96a7ec343d7f5b009a98098cb4002d":
        raise ValueError("Replication requires the frozen v9 taxonomy")
    if classify_images.VISION_MODEL != "pixtral-12b-2409":
        raise ValueError("Replication requires the frozen Pixtral model")
    if fingerprint(classify_images.VISION_PROMPT) != "b300585e3035a3c4bdc92175514b4e6826f782af3c1165348c520628107b5858":
        raise ValueError("Replication vision prompt has changed")
    if source_digest(routing.__file__) != "2eab8c958fc32ad361ea2b906dfcbd2eaac636df8468e7f64c515ce473284872":
        raise ValueError("Replication routing implementation has changed")


def load_results(path):
    return load_json(path, missing_ok=True)


def save_results(path, results):
    save_json(path, results)


def main():
    if not classify_images.MISTRAL_KEY or not pilot_humanoid.API_KEY:
        raise SystemExit("Missing MISTRAL_API_KEY or TYPESAFE_API_KEY")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    run = (sys.argv[1] if len(sys.argv) > 1 else "1").strip()
    RESULTS = results_path(run)

    with open(TAXONOMY, "r", encoding="utf-8") as f:
        tax = json.load(f)
    require_frozen(tax)
    facets = tax["facets"]

    with open(MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    manifest_id = require_sealed(manifest)
    items = [(k, v) for k, v in manifest.items()
             if isinstance(v, dict) and v.get("status") == "ok" and "category" in v]
    print("Corpus images: %d (run %s -> %s)" % (len(items), run, os.path.basename(RESULTS)))

    results = load_results(RESULTS)
    stamps = prepare_run(
        results, {"manifest": manifest_id, "taxonomy": tax,
                  "vision_model": classify_images.VISION_MODEL, "decision_model": "jev-latest"},
        {name: {"image": file_digest(os.path.join(IMAGES_DIR, name + rec.get("file_ext", ".jpg"))),
                "category": rec["category"]} for name, rec in items},
        __file__, classify_images.__file__, pilot_humanoid.__file__, routing.__file__)
    done = {k for k, r in results.items() if r.get("status") == "ok"}
    todo = [(k, v) for k, v in items if k not in done]
    print("Already done: %d, to process: %d" % (len(done), len(todo)))

    for i, (fname, rec) in enumerate(todo, 1):
        path = os.path.join(IMAGES_DIR, fname + rec.get("file_ext", ".jpg"))
        out = {"category": rec["category"], "title": rec.get("title", ""), "status": "error",
               "_provenance": stamps[fname]}
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
        save_results(RESULTS, results)
        if out["status"] == "ok":
            confs = [out[q]["confidence"] for q in FACETS]
            print("[%d/%d] %s: %s / %s (min conf %.3f)" % (
                i, len(todo), fname, out["primary_subject"]["choice"],
                out["representation"]["choice"], min(confs)))
        else:
            print("[%d/%d] %s: ERROR %s" % (i, len(todo), fname, out.get("error", "")[:80]))
        time.sleep(DELAY)

    ok = {k: r for k, r in results.items() if r.get("status") == "ok"}
    require_complete(results)
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

    print("\n=== Corpus vs. category-implied labels (n=%d) ===" % len(ok))
    for q in FACETS:
        n = scored[q]
        print("  %s: %d/%d (%.0f%%)" % (q, match[q], n, match[q] / n * 100) if n
              else "  %s: 0/0" % q)

    print("\n=== Per category ===")
    for cat in sorted(per_cat):
        c = per_cat[cat]
        pct = "%.0f%%" % (c["match"] / c["scored"] * 100) if c["scored"] else "n/a"
        print("  %s: %d/%d (%s) of %d images" % (cat, c["match"], c["scored"], pct, c["n"]))

    print("\n=== Routing (route_reason) ===")
    burden = {}
    for fname, rec in sorted(ok.items()):
        reason = route_reason(rec) or "auto-accept"
        burden.setdefault(rec["category"], {}).setdefault(reason, 0)
        burden[rec["category"]][reason] += 1
    total_routed = sum(n for d in burden.values()
                       for r, n in d.items() if r != "auto-accept")
    for cat in sorted(burden):
        print("  %s: %s" % (cat, burden[cat]))
    print("  TOTAL routed: %d/%d (%.0f%%)" % (total_routed, len(ok),
                                              total_routed / len(ok) * 100))


if __name__ == "__main__":
    main()
