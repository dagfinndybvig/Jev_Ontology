"""Measure the generated edge-case suite against the pipeline (TODO item 9).

Runs the production path on each image in edge_cases/: Pixtral describes it
(same prompt as classify_images.py), Jev answers the five facets (v4
taxonomy, same call shape as pilot_humanoid.py). Answers are compared to the
intended labels each prompt was written to elicit; facets whose truth is
genuinely ambiguous under the v4 taxonomy are excluded from strict agreement
and reported separately. Also checks whether routing.py's route_reason flags
each record. Results are saved incrementally to edge_case_pipeline_results.json
(private, gitignored); images with status ok are skipped.

Requires MISTRAL_API_KEY (vision) and TYPESAFE_API_KEY (Jev).
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

RESULTS = os.path.join(SCRIPT_DIR, "edge_case_pipeline_results.json")
GENERATED = os.path.join(SCRIPT_DIR, "edge_case_results.json")
IMAGES_DIR = os.environ.get("EDGE_CASES_DIR") or os.path.join(SCRIPT_DIR, "edge_cases")

DELAY = 0.4

# Intended labels: what each prompt was written to elicit under the v4
# taxonomy. "ambiguous" marks facets whose truth the taxonomy cannot express
# (scored separately, not as errors); "note" records why.
INTENDED = {
    "text_describes_scene": {
        "contains_human": "no", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "none", "representation": "text_screenshot",
        "note": "the known failure mode: text describing a man and a robot",
    },
    "meme_caption": {
        "contains_human": "no", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "none", "representation": "photograph",
        "note": "a real photograph (cat) with caption text; the scene, not the words, dominates",
    },
    "ai_generated_portrait": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "ambiguous",
        "primary_subject": "human", "representation": "statue_or_render",
        "note": "AI-generated photorealistic: a depicted human (render); android is ambiguous -- the image does not identify her as artificial, only the generation context does",
    },
    "collage": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "human", "representation": "photograph",
        "note": "six family photos: multiple humans, one kind -- 'multiple' means distinct kinds",
    },
    "people_in_background": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "ambiguous", "representation": "photograph",
        "note": "taxonomy gap: the main subject is the building, but 'none' requires no visible humanoid -- incidental humans have no class",
    },
    "game_screen": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "ambiguous", "representation": "ambiguous",
        "note": "taxonomy gap: an interface screenshot with a depicted character portrait; v4's design notes say screenshots classify by content, but UI-with-subject fits neither text_screenshot nor other cleanly",
    },
    "statue": {
        "contains_human": "yes", "contains_robot": "no", "contains_android": "no",
        "primary_subject": "human", "representation": "statue_or_render",
        "note": "a statue depicts a human form in a physical medium",
    },
    "robot_illustration": {
        "contains_human": "no", "contains_robot": "yes", "contains_android": "no",
        "primary_subject": "robot", "representation": "illustration",
        "note": "boxy retro robot: being-like form, not android",
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
    with open(TAXONOMY, "r", encoding="utf-8") as f:
        tax = json.load(f)
    facets = tax["facets"]

    with open(GENERATED, "r", encoding="utf-8") as f:
        generated = json.load(f)
    items = [(pid, rec) for pid, rec in generated.items() if rec.get("status") == "ok"]
    print(f"Generated images: {len(items)}")

    results = load_results()
    done = {k for k, r in results.items() if r.get("status") == "ok"}
    todo = [(pid, rec) for pid, rec in items if pid not in done]
    print(f"Already done: {len(done)}, to process: {len(todo)}")

    for i, (pid, rec) in enumerate(todo, 1):
        path = os.path.join(IMAGES_DIR, rec["file"])
        out = {"file": rec["file"], "prompt": rec["prompt"], "status": "error"}
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
        results[pid] = out
        save_results(results)
        if out["status"] == "ok":
            confs = [out[q]["confidence"] for q in FACETS]
            print(f"[{i}/{len(todo)}] {pid}: {out['primary_subject']['choice']}"
                  f" / {out['representation']['choice']} (min conf {min(confs):.3f})")
        else:
            print(f"[{i}/{len(todo)}] {pid}: ERROR {out['error'][:80]}")
        time.sleep(DELAY)

    # Comparison against the intended labels
    ok = {k: r for k, r in results.items() if r.get("status") == "ok"}
    if not ok:
        print("\nNothing measured.")
        return

    print(f"\n=== Edge-case suite vs. intended labels (n={len(ok)}) ===")
    match = {q: 0 for q in FACETS}
    scored = {q: 0 for q in FACETS}
    for pid, rec in sorted(ok.items()):
        want = INTENDED[pid]
        print(f"\n{pid}  [{want['note']}]")
        print(f"  description: {rec.get('description', '')}")
        for q in FACETS:
            got = rec[q]["choice"]
            conf = rec[q]["confidence"]
            exp = want[q]
            if exp == "ambiguous":
                verdict = "AMBIGUOUS (not scored)"
            elif got == exp:
                verdict = "match"
                match[q] += 1
                scored[q] += 1
            else:
                verdict = f"MISMATCH (intended {exp})"
                scored[q] += 1
            flag = "" if conf >= 0.7 else "  [low conf]"
            print(f"  {q}: {got} ({conf:.3f}){flag}  -> {verdict}")
        reason = route_reason(rec)
        print(f"  routing: {reason or 'auto-accept'}")

    print("\n=== Per-facet agreement (unambiguous facets only) ===")
    for q in FACETS:
        n = scored[q]
        print(f"  {q}: {match[q]}/{n} ({match[q] / n * 100:.0f}%)" if n else f"  {q}: 0/0")


if __name__ == "__main__":
    main()
