"""Classify all images in a folder (PICTURES_DIR) as containing a human or not.

Pipeline: Mistral vision (Pixtral) describes each image -> Jev classifies the
description as human / no-human. Results are saved incrementally to
image_human_results.json so the run can be resumed. Errored records are
retried on the next run.
"""
import base64
import json
import os
import sys
import time
import urllib.request

PICTURES = os.environ.get("PICTURES_DIR", "")  # folder of images to classify
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_human_results.json")
EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".avif", ".tiff", ".tif", ".jfif"}

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")
TYPESAFE_KEY = os.environ.get("TYPESAFE_API_KEY", "")
VISION_MODEL = os.environ.get("VISION_MODEL", "pixtral-12b-2409")

DELAY = 0.4  # seconds between images, to be polite to the APIs


def describe_image(path, model=VISION_MODEL):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    mime = f"image/{ext}"
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Describe this image in one short sentence (max 25 words). "
                            "Focus on the main subject. If it contains people, say so. "
                            "Do not mention the filename."
                        ),
                    },
                    {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"},
                ],
            }
        ],
        "max_tokens": 80,
    }
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {MISTRAL_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def jev_classify(state):
    body = {
        "model": "jev-latest",
        "state": state,
        "questions": {
            "contains_human": {
                "type": "choice",
                "instructions": "Does this image contain a human?",
                "criteria": {
                    "yes": "The image contains one or more humans (people, faces, bodies)",
                    "no": "The image contains no humans",
                },
            }
        },
    }
    req = urllib.request.Request(
        "https://api.typesafe.ai/v1/systemone",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {TYPESAFE_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    ans = data["answers"]["contains_human"]
    return {
        "choice": ans["choice"],
        "confidence": ans["confidence"],
        "probabilities": ans["probabilities"],
    }


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

    files = []
    for name in os.listdir(PICTURES):
        full = os.path.join(PICTURES, name)
        if os.path.isfile(full) and os.path.splitext(name)[1].lower() in EXTS:
            files.append(name)
    files.sort(key=lambda x: x.lower())
    print(f"Total images: {len(files)}")

    results = load_results()
    done = {name for name, rec in results.items() if rec.get("status") == "ok"}
    todo = [n for n in files if n not in done]
    print(f"Already done: {len(done)}, to process: {len(todo)}")

    for i, name in enumerate(todo, 1):
        path = os.path.join(PICTURES, name)
        rec = {"file": name, "status": "error"}
        try:
            desc = describe_image(path)
            rec["description"] = desc
            rec.update(jev_classify(desc))
            rec["status"] = "ok"
        except Exception as e:
            rec["error"] = str(e)
        results[name] = rec
        save_results(results)
        if rec["status"] == "ok":
            print(f"[{i}/{len(todo)}] {name}: {rec['choice']} ({rec['confidence']:.3f})")
        else:
            print(f"[{i}/{len(todo)}] {name}: ERROR {rec['error'][:80]}")
        time.sleep(DELAY)

    # Summary
    ok = [r for r in results.values() if r.get("status") == "ok"]
    yes = [r for r in ok if r["choice"] == "yes"]
    no = [r for r in ok if r["choice"] == "no"]
    print(f"\nDone. OK={len(ok)}, human={len(yes)}, no-human={len(no)}, errors={len(results)-len(ok)}")


if __name__ == "__main__":
    main()
