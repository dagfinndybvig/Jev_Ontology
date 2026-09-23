"""Generate the adversarial edge-case suite (TODO item 9) with Mistral image generation.

Creates an image-generation agent once (POST /v1/agents with the
image_generation tool; the agent ID is cached in edge_case_agent.json and
reused across runs), renders each prompt through the conversations API, and
downloads the PNG into EDGE_CASES_DIR. Results are saved incrementally to
edge_case_results.json so the run can be resumed; prompts with status ok are
skipped. Stdlib only. Needs MISTRAL_API_KEY credits (per-image generation
rate plus a small token overhead for the agent turns).

Usage:
    python generate_edge_cases.py            # all pending prompts
    python generate_edge_cases.py meme ...   # only the named prompt ids
"""
import json
import os
import sys
import time
import urllib.request

API = "https://api.mistral.ai/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "edge_case_results.json")
AGENT_CACHE = os.path.join(HERE, "edge_case_agent.json")
IMAGES_DIR = os.environ.get("EDGE_CASES_DIR") or os.path.join(HERE, "edge_cases")
PROMPTS_FILE = os.environ.get("EDGE_CASE_PROMPTS")  # optional JSON override

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")
AGENT_MODEL = os.environ.get("IMAGE_AGENT_MODEL", "mistral-medium-latest")

DELAY = 1.0  # seconds between images, to be polite to the API

# The measured failure families (TODO item 9): text describing a scene, memes,
# AI-generated people, collages, background people, app screens, and the
# representation boundaries (statue vs. person, robot vs. android).
DEFAULT_PROMPTS = [
    {
        "id": "text_describes_scene",
        "prompt": (
            "A screenshot of a chat window on a dark background. The only "
            "content is the message text: 'A man and a robot stand together "
            "in a rainy city street at night.' No picture, just the text."
        ),
    },
    {
        "id": "meme_caption",
        "prompt": (
            "A classic meme: a photograph of a disapproving cat, with large "
            "white impact-font caption text at the top and bottom."
        ),
    },
    {
        "id": "ai_generated_portrait",
        "prompt": (
            "A photorealistic AI-generated portrait of a smiling woman in her "
            "thirties, studio lighting, plain background."
        ),
    },
    {
        "id": "collage",
        "prompt": (
            "A collage of six different family photos arranged in a 2x3 grid "
            "with white borders between them."
        ),
    },
    {
        "id": "people_in_background",
        "prompt": (
            "A photograph of a historic stone building; a few tourists are "
            "visible small in the background, out of focus."
        ),
    },
    {
        "id": "game_screen",
        "prompt": (
            "A screenshot of a fantasy role-playing game's inventory screen, "
            "with text menus, item icons, and a character portrait."
        ),
    },
    {
        "id": "statue",
        "prompt": (
            "A photograph of a bronze statue of a standing man in a city "
            "park, trees behind it."
        ),
    },
    {
        "id": "robot_illustration",
        "prompt": (
            "A colorful 1960s cartoon-style illustration of a boxy retro "
            "robot waving one claw hand."
        ),
    },
]


def load_prompts():
    if PROMPTS_FILE:
        with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_PROMPTS


def mistral_request(method, path, body=None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Authorization": f"Bearer {MISTRAL_KEY}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(file_id):
    """Fetch a generated file's bytes. The API reports file_type png but the
    download endpoint has returned JPEG (JFIF) bytes; sniff the magic bytes."""
    req = urllib.request.Request(
        API + f"/files/{file_id}/content",
        headers={"Authorization": f"Bearer {MISTRAL_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def sniff_ext(data):
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    raise RuntimeError(f"unrecognized image format: {data[:8].hex()}")


def load_agent():
    if os.path.exists(AGENT_CACHE):
        with open(AGENT_CACHE, "r", encoding="utf-8") as f:
            return json.load(f).get("agent_id", "")
    return ""


def save_agent(agent_id):
    with open(AGENT_CACHE, "w", encoding="utf-8") as f:
        json.dump({"agent_id": agent_id, "model": AGENT_MODEL}, f, indent=2)


def create_agent():
    body = {
        "model": AGENT_MODEL,
        "name": "Edge-case image generator",
        "description": "Generates the adversarial edge-case suite for the image pipeline.",
        "instructions": "Use the image generation tool for every request. Render exactly what is described.",
        "tools": [{"type": "image_generation"}],
        "completion_args": {"temperature": 0.3, "top_p": 0.95},
    }
    data = mistral_request("POST", "/agents", body)
    return data["id"]


def ensure_agent():
    agent_id = load_agent()
    if agent_id:
        return agent_id
    agent_id = create_agent()
    save_agent(agent_id)
    return agent_id


def generate_one(agent_id, prompt):
    """Render one prompt; returns (file_id, file_name, usage).

    The REST conversations response carries the entries under the top-level
    `outputs` key (the SDK docs show `entries`); accept either.
    """
    data = mistral_request("POST", "/conversations", {"agent_id": agent_id, "inputs": prompt})
    for entry in data.get("outputs") or data.get("entries") or []:
        if entry.get("type") != "message.output":
            continue
        for chunk in entry.get("content", []):
            if chunk.get("type") == "tool_file" and chunk.get("file_id"):
                return chunk["file_id"], chunk.get("file_name", ""), data.get("usage", {})
    raise RuntimeError("no tool_file in conversation response")


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

    prompts = load_prompts()
    only = set(sys.argv[1:])
    if only:
        prompts = [p for p in prompts if p["id"] in only]
        missing = only - {p["id"] for p in prompts}
        if missing:
            print(f"Unknown prompt ids: {', '.join(sorted(missing))}")
            sys.exit(1)

    os.makedirs(IMAGES_DIR, exist_ok=True)
    results = load_results()
    done = {k for k, r in results.items() if r.get("status") == "ok"}
    todo = [p for p in prompts if p["id"] not in done]
    print(f"Total prompts: {len(prompts)}, already done: {len(prompts) - len(todo)}, to generate: {len(todo)}")
    if not todo:
        return

    agent_id = ensure_agent()
    print(f"Agent: {agent_id}")

    for i, p in enumerate(todo, 1):
        pid = p["id"]
        rec = {"prompt": p["prompt"], "status": "error"}
        try:
            file_id, file_name, usage = generate_one(agent_id, p["prompt"])
            data = download_file(file_id)
            dest = os.path.join(IMAGES_DIR, pid + sniff_ext(data))
            with open(dest, "wb") as f:
                f.write(data)
            rec.update({"status": "ok", "file": os.path.basename(dest), "file_id": file_id, "file_name": file_name, "usage": usage})
        except Exception as e:
            # A vanished cached agent is recreated once, then the prompt is retried.
            if "404" in str(e) or "not found" in str(e).lower():
                try:
                    os.remove(AGENT_CACHE)
                    agent_id = ensure_agent()
                    file_id, file_name, usage = generate_one(agent_id, p["prompt"])
                    data = download_file(file_id)
                    dest = os.path.join(IMAGES_DIR, pid + sniff_ext(data))
                    with open(dest, "wb") as f:
                        f.write(data)
                    rec.update({"status": "ok", "file": os.path.basename(dest), "file_id": file_id, "file_name": file_name, "usage": usage})
                except Exception as e2:
                    rec["error"] = str(e2)
            else:
                rec["error"] = str(e)
        results[pid] = rec
        save_results(results)
        if rec["status"] == "ok":
            print(f"[{i}/{len(todo)}] {pid}: saved {rec['file']}")
        else:
            print(f"[{i}/{len(todo)}] {pid}: ERROR {rec['error'][:80]}")
        time.sleep(DELAY)

    ok = [r for r in results.values() if r.get("status") == "ok"]
    print(f"\nDone. OK={len(ok)}, errors={len(results) - len(ok)}, images in {IMAGES_DIR}")


if __name__ == "__main__":
    main()
