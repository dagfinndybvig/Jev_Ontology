"""Phase 2 baseline: Pixtral asked directly (no Jev cascade).

For each labeled image (records with a manual_correction in
humanoid_pilot_results.json), Pixtral classifies the five facets itself,
using the same criteria as humanoid_taxonomy_v4.json, and reports a
confidence per facet. Results are saved incrementally to
baseline_pixtral_direct_results.json (private, gitignored) so the run
can be resumed. Comparison against the cascade and a keyword baseline is
in baseline_compare.py.
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
RESULTS = os.path.join(HERE, "baseline_pixtral_direct_results.json")
CASCADE_RESULTS = os.path.join(HERE, "humanoid_pilot_results.json")
TAXONOMY = os.path.join(HERE, "humanoid_taxonomy_v4.json")
EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".avif", ".tiff", ".tif", ".jfif"}

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")
VISION_MODEL = os.environ.get("VISION_MODEL", "pixtral-12b-2409")
DELAY = 0.4


def build_prompt(taxonomy):
    facets = taxonomy["facets"]
    lines = [
        "Classify this image on five facets. Answer with JSON only, no other text:",
        '{"contains_human": {"choice": "...", "confidence": 0.0}, ...}',
        "confidence is your calibrated probability (0.0-1.0) that the choice is correct.",
        "",
    ]
    for name, spec in facets.items():
        lines.append(f"{name}: {spec['instructions']}")
        for choice, crit in spec["criteria"].items():
            lines.append(f"  - {choice}: {crit}")
    lines.append("")
    lines.append('Respond with exactly these keys: ' + ", ".join(facets))
    return "\n".join(lines)


def classify_image(path, prompt):
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
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"},
                ],
            }
        ],
        "max_tokens": 400,
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {MISTRAL_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage", {})
    return text, usage


def parse_answer(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON in answer: {text[:120]}")
    obj = json.loads(m.group(0))
    out = {}
    for facet, ans in obj.items():
        if isinstance(ans, dict) and "choice" in ans:
            out[facet] = {"choice": ans["choice"], "confidence": float(ans.get("confidence", 0.0))}
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
    if not MISTRAL_KEY:
        print("Missing MISTRAL_API_KEY")
        sys.exit(1)
    if not PICTURES or not os.path.isdir(PICTURES):
        print("Set PICTURES_DIR to the folder of images to classify")
        sys.exit(1)

    with open(TAXONOMY, "r", encoding="utf-8") as f:
        taxonomy = json.load(f)
    with open(CASCADE_RESULTS, "r", encoding="utf-8") as f:
        cascade = json.load(f)

    labeled = {name: rec for name, rec in cascade.items() if rec.get("manual_correction")}
    print(f"Labeled records: {len(labeled)}")

    prompt = build_prompt(taxonomy)
    results = load_results()
    todo = [n for n in sorted(labeled) if results.get(n, {}).get("status") != "ok"]
    print(f"Already done: {len(labeled) - len(todo)}, to process: {len(todo)}")

    for i, name in enumerate(todo, 1):
        path = os.path.join(PICTURES, name)
        rec = {"file": name, "status": "error"}
        if not os.path.isfile(path) or os.path.splitext(name)[1].lower() not in EXTS:
            rec["error"] = "image not found or unsupported extension"
        else:
            try:
                text, usage = classify_image(path, prompt)
                rec["answer"] = parse_answer(text)
                rec["raw_answer"] = text
                rec["usage"] = usage
                rec["status"] = "ok"
            except Exception as e:
                rec["error"] = str(e)
        results[name] = rec
        save_results(results)
        if rec["status"] == "ok":
            brief = {k: v["choice"] for k, v in rec["answer"].items()}
            print(f"[{i}/{len(todo)}] {name}: {brief}")
        else:
            print(f"[{i}/{len(todo)}] {name}: ERROR {rec['error'][:80]}")
        time.sleep(DELAY)

    ok = [r for r in results.values() if r.get("status") == "ok"]
    print(f"\nDone. OK={len(ok)}, errors={len(results) - len(ok)}")


if __name__ == "__main__":
    main()
