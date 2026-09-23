"""Option 1 experiment: a dedicated binary capture-type question.

The structured vision state's remaining representation errors have a
wrong `medium` field, and prompt wording cannot fix it (v2's clause
failed to fire, v3's physical-context clause backfired). This script
tests a different mechanism: a separate, isolated vision call that
answers only "flat digital capture, or photograph of a physical
object?", then deterministically overrides the structured state:

  - capture == photo_of_physical and medium == text_screenshot
      -> medium becomes photograph (the photographed-cover family)
  - capture == digital_capture and medium == photograph
      -> medium becomes text_screenshot, and subjects is cleared
         (nothing is physically depicted; the described-scene trap)

Jev then classifies the composed state. Two resumable stages, saved to
capture_type_results.json (private, gitignored). The structured fields
come from structured_vision_results.json (the v2 run).
"""
import base64
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PICTURES = os.environ.get("PICTURES_DIR", "")
RESULTS = os.path.join(HERE, "capture_type_results.json")
STRUCTURED_RESULTS = os.path.join(HERE, "structured_vision_results.json")
CASCADE_RESULTS = os.path.join(HERE, "humanoid_pilot_results.json")
TAXONOMY = os.path.join(HERE, "humanoid_taxonomy_v4.json")
EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".avif", ".tiff", ".tif", ".jfif"}

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")
TYPESAFE_KEY = os.environ.get("TYPESAFE_API_KEY", "")
VISION_MODEL = os.environ.get("VISION_MODEL", "pixtral-12b-2409")
JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DELAY = 0.4

CAPTURE_PROMPT = (
    "Look only at how this image was captured, not at what it shows. Is this:\n"
    "- digital_capture: a flat, head-on digital capture -- a screenshot or scan "
    "where the content fills the frame with no physical context, depth, or "
    "background; or\n"
    "- photo_of_physical: a photograph of a physical object -- a page, book "
    "cover, poster, or screen seen as a physical thing (at an angle, with "
    "depth, lighting, shadows, reflections, or visible surroundings)?\n"
    'Answer with JSON only: {"capture": "digital_capture"} or '
    '{"capture": "photo_of_physical"}'
)

FACET_NAMES = ["contains_human", "contains_robot", "contains_android",
               "primary_subject", "representation"]
TEXT_TRUNCATE = 120


def ask_capture(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    body = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": CAPTURE_PROMPT},
                    {"type": "image_url", "image_url": f"data:image/{ext};base64,{b64}"},
                ],
            }
        ],
        "max_tokens": 100,
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {MISTRAL_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    raw = data["choices"][0]["message"]["content"].strip()
    m = re.search(r'"capture"\s*:\s*"(digital_capture|photo_of_physical)"', raw)
    if not m:
        raise ValueError(f"no capture answer: {raw[:120]}")
    return m.group(1), raw, data.get("usage", {})


def apply_override(fields, capture):
    """Deterministic capture-informed override of the structured fields."""
    f = dict(fields)
    medium = f.get("medium", "other")
    if capture == "photo_of_physical" and medium == "text_screenshot":
        f["medium"] = "photograph"
    elif capture == "digital_capture" and medium == "photograph":
        f["medium"] = "text_screenshot"
        f["subjects"] = ""  # nothing is physically depicted
    f["capture"] = capture
    return f


def compose_state(f):
    text = f.get("text_in_image", "none")
    if text and text.lower() != "none":
        text = text[:TEXT_TRUNCATE] + ('..."' if len(text) > TEXT_TRUNCATE else '"')
        text = f'"{text} (quoted content, not the scene)'
    subjects = f.get("subjects", "") or "none depicted"
    return (
        "Structured vision state (typed fields extracted from the image by a "
        "vision model):\n"
        f"Medium: {f.get('medium', 'other')}\n"
        f"Capture type: {f.get('capture')} (flat digital capture vs photograph "
        "of a physical object)\n"
        f"Subjects depicted: {subjects}\n"
        f"Text in image: {text}\n"
        f"Setting: {f.get('setting', 'other')}\n"
        f"People: {f.get('people', 'none')}\n"
        "\n"
        "Classify the depicted content according to the questions."
    )


def jev_classify_facets(state, facets):
    body = {"model": "jev-latest", "state": state, "questions": facets}
    req = urllib.request.Request(
        JEV_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {TYPESAFE_KEY}", "Content-Type": "application/json"},
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
    return out, data.get("usage", {})


def load_results():
    if os.path.exists(RESULTS):
        with open(RESULTS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_results(results):
    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def main():
    if not MISTRAL_KEY or not TYPESAFE_KEY:
        print("Missing MISTRAL_API_KEY or TYPESAFE_API_KEY")
        sys.exit(1)
    if not PICTURES or not os.path.isdir(PICTURES):
        print("Set PICTURES_DIR to the folder of images to classify")
        sys.exit(1)

    with open(TAXONOMY, "r", encoding="utf-8") as f:
        facets = json.load(f)["facets"]
    with open(CASCADE_RESULTS, "r", encoding="utf-8") as f:
        cascade = json.load(f)
    labeled = {n for n, r in cascade.items() if r.get("manual_correction")}
    with open(STRUCTURED_RESULTS, "r", encoding="utf-8") as f:
        structured = json.load(f)
    print(f"Labeled records: {len(labeled)}")

    results = load_results()

    # Stage 1: the isolated capture question
    todo = [n for n in sorted(labeled)
            if results.get(n, {}).get("capture_status") != "ok"]
    print(f"Stage 1 (capture question): to process {len(todo)}")
    for i, name in enumerate(todo, 1):
        path = os.path.join(PICTURES, name)
        rec = results.setdefault(name, {"file": name})
        if not os.path.isfile(path) or os.path.splitext(name)[1].lower() not in EXTS:
            rec["capture_status"] = "error"
            rec["error"] = "image not found or unsupported extension"
        else:
            try:
                capture, raw, usage = ask_capture(path)
                rec["capture"] = capture
                rec["raw_capture_answer"] = raw
                rec["capture_usage"] = usage
                rec["capture_status"] = "ok"
            except Exception as e:
                rec["capture_status"] = "error"
                rec["error"] = str(e)
        save_results(results)
        if rec["capture_status"] == "ok":
            print(f"[{i}/{len(todo)}] {name}: {rec['capture']}")
        else:
            print(f"[{i}/{len(todo)}] {name}: ERROR {rec['error'][:80]}")
        time.sleep(DELAY)

    # Stage 2: Jev on the capture-informed state
    todo = [n for n in sorted(labeled)
            if results.get(n, {}).get("capture_status") == "ok"
            and structured.get(n, {}).get("status") == "ok"
            and results[n].get("status") != "ok"]
    print(f"\nStage 2 (Jev on capture-informed state): to process {len(todo)}")
    for i, name in enumerate(todo, 1):
        rec = results[name]
        fields = apply_override(structured[name]["fields"], rec["capture"])
        rec["overridden_fields"] = fields
        state = compose_state(fields)
        rec["state"] = state
        try:
            answers, usage = jev_classify_facets(state, facets)
            rec["answers"] = answers
            rec["jev_usage"] = usage
            rec["status"] = "ok"
        except Exception as e:
            rec["status"] = "error"
            rec["error"] = str(e)
        save_results(results)
        if rec["status"] == "ok":
            confs = [rec["answers"][q]["confidence"] for q in FACET_NAMES]
            print(f"[{i}/{len(todo)}] {name}: {rec['answers']['primary_subject']['choice']}"
                  f" / {rec['answers']['representation']['choice']} (min conf {min(confs):.3f})")
        else:
            print(f"[{i}/{len(todo)}] {name}: ERROR {rec['error'][:80]}")
        time.sleep(DELAY)

    ok = [r for r in results.values() if r.get("status") == "ok"]
    print(f"\nDone. OK={len(ok)} of {len(labeled)} labeled records")


if __name__ == "__main__":
    main()
