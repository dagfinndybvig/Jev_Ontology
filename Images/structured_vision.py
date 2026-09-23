"""Phase 3: structured vision state (LIBRARY.md).

Replaces the free 25-word description with typed fields per image:
medium, subjects, text_in_image, setting, people. The state passed to
Jev is composed from those fields, with transcribed text explicitly
labeled as quoted content -- attacking the known failure mode where a
scan of text is described as if it were the scene.

Two resumable stages, saved incrementally to
structured_vision_results.json (private, gitignored):
  1. vision  -- Pixtral extracts the typed fields (MISTRAL_API_KEY)
  2. jev     -- Jev classifies the composed state on the five facets of
                humanoid_taxonomy_v4.json (TYPESAFE_API_KEY)

Comparison against the cascade and the baselines is in
baseline_compare.py (the structured system appears when its results
are present).
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
RESULTS = os.path.join(HERE, "structured_vision_results.json")
CASCADE_RESULTS = os.path.join(HERE, "humanoid_pilot_results.json")
TAXONOMY = os.path.join(HERE, "humanoid_taxonomy_v4.json")
EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".avif", ".tiff", ".tif", ".jfif"}

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")
TYPESAFE_KEY = os.environ.get("TYPESAFE_API_KEY", "")
VISION_MODEL = os.environ.get("VISION_MODEL", "pixtral-12b-2409")
JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DELAY = 0.4

VISION_PROMPT = (
    "Examine this image and return JSON only (no other text) with these typed fields:\n"
    '{"medium": "...", "subjects": "...", "text_in_image": "...", "setting": "...", "people": "..."}\n'
    "\n"
    "medium: what the image IS -- exactly one of photograph, illustration, "
    "statue_or_render, text_screenshot, other. This classifies the artifact, "
    "not its content. A photograph of a book cover, poster, or screen is a "
    "photograph. A poster or printed illustration is an illustration. A game "
    "or application screen is text_screenshot only if it consists of text; "
    "otherwise other.\n"
    "subjects: what is depicted, as a short list (empty string if nothing is "
    "depicted). If the image is text or a screenshot of text, subjects is empty -- "
    "never describe a scene the text merely mentions.\n"
    "text_in_image: any legible text, transcribed briefly (or the string none).\n"
    "setting: indoor, outdoor, studio, archival page, screen, or other.\n"
    "people: none, individuals, or group (no identities)."
)

FIELD_KEYS = ["medium", "subjects", "text_in_image", "setting", "people"]
TEXT_TRUNCATE = 120


def compose_state(fields):
    text = fields.get("text_in_image", "none")
    if text and text.lower() != "none":
        text = text[:TEXT_TRUNCATE] + ('..."' if len(text) > TEXT_TRUNCATE else '"')
        text = f'"{text} (quoted content, not the scene)'
    subjects = fields.get("subjects", "") or "none depicted"
    return (
        "Structured vision state (typed fields extracted from the image by a "
        "vision model):\n"
        f"Medium: {fields.get('medium', 'other')}\n"
        f"Subjects depicted: {subjects}\n"
        f"Text in image: {text}\n"
        f"Setting: {fields.get('setting', 'other')}\n"
        f"People: {fields.get('people', 'none')}\n"
        "\n"
        "Classify the depicted content according to the questions."
    )


def repair_fields(text):
    """Fallback parser for malformed JSON (e.g. unescaped quotes inside
    transcribed text): extract each field up to the next key."""
    fields = {}
    for i, key in enumerate(FIELD_KEYS):
        m = re.search(rf'"{key}"\s*:\s*', text)
        if not m:
            continue
        rest = text[m.end():]
        if rest.startswith("["):
            end = rest.find("]")
            if end != -1:
                inner = rest[1:end]
                fields[key] = "; ".join(x.strip(" '\"") for x in inner.split(",") if x.strip(" '\""))
                continue
        nxt = FIELD_KEYS[i + 1] if i + 1 < len(FIELD_KEYS) else None
        pat = rf'"\s*,?\s*(?="{nxt}")' if nxt else r'"\s*,?\s*\}'
        m2 = re.search(pat, rest, re.DOTALL)
        val = rest[:m2.start()] if m2 else rest
        fields[key] = val.strip().strip('"').strip()
    return fields


def extract_fields(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    mime = f"image/{ext}"
    body = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"},
                ],
            }
        ],
        "max_tokens": 700,
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
    # strict=False: Pixtral emits raw newlines inside string values.
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            raise ValueError("no JSON object in answer")
        obj = json.loads(m.group(0), strict=False)

        def norm(v):
            if isinstance(v, list):
                return "; ".join(str(x).strip() for x in v)
            return str(v).strip()

        fields = {k: norm(obj.get(k, "")) for k in FIELD_KEYS}
    except (ValueError, json.JSONDecodeError):
        fields = repair_fields(raw)
        missing = [k for k in FIELD_KEYS if not fields.get(k)]
        if len(missing) > 2:
            raise ValueError(f"unparseable answer: {raw[:120]}")
    return fields, raw, data.get("usage", {})


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
        tax = json.load(f)
    facets = tax["facets"]
    with open(CASCADE_RESULTS, "r", encoding="utf-8") as f:
        cascade = json.load(f)
    labeled = {n: r for n, r in cascade.items() if r.get("manual_correction")}
    print(f"Labeled records: {len(labeled)}")

    results = load_results()

    # Stage 1: vision fields
    todo = [n for n in sorted(labeled) if results.get(n, {}).get("fields_status") != "ok"]
    print(f"Stage 1 (vision fields): to process {len(todo)}")
    for i, name in enumerate(todo, 1):
        path = os.path.join(PICTURES, name)
        rec = results.setdefault(name, {"file": name})
        if not os.path.isfile(path) or os.path.splitext(name)[1].lower() not in EXTS:
            rec["fields_status"] = "error"
            rec["error"] = "image not found or unsupported extension"
        else:
            try:
                fields, raw, usage = extract_fields(path)
                rec["fields"] = fields
                rec["raw_fields_answer"] = raw
                rec["fields_usage"] = usage
                rec["fields_status"] = "ok"
            except Exception as e:
                rec["fields_status"] = "error"
                rec["error"] = str(e)
        save_results(results)
        if rec["fields_status"] == "ok":
            print(f"[{i}/{len(todo)}] {name}: {rec['fields']['medium']} | "
                  f"{rec['fields']['subjects'][:60]}")
        else:
            print(f"[{i}/{len(todo)}] {name}: ERROR {rec['error'][:80]}")
        time.sleep(DELAY)

    # Stage 2: Jev on the composed state
    todo = [n for n in sorted(labeled)
            if results.get(n, {}).get("fields_status") == "ok"
            and results[n].get("status") != "ok"]
    print(f"\nStage 2 (Jev on structured state): to process {len(todo)}")
    for i, name in enumerate(todo, 1):
        rec = results[name]
        state = compose_state(rec["fields"])
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
            confs = [rec["answers"][q]["confidence"] for q in facets]
            print(f"[{i}/{len(todo)}] {name}: {rec['answers']['primary_subject']['choice']}"
                  f" / {rec['answers']['representation']['choice']} (min conf {min(confs):.3f})")
        else:
            print(f"[{i}/{len(todo)}] {name}: ERROR {rec['error'][:80]}")
        time.sleep(DELAY)

    ok = [r for r in results.values() if r.get("status") == "ok"]
    print(f"\nDone. OK={len(ok)} of {len(labeled)} labeled records")


if __name__ == "__main__":
    main()
