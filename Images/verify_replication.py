"""Hand-verification UI for the replication corpus (REPLICATION_PROTOCOL.md step 4).

A localhost review app (127.0.0.1:8766) for verifying that each image's
category-implied label is right before the pipeline run. The Commons corpus
taught us category labels are noisy, so images whose label is wrong are
excluded before the run, with counts recorded -- never after seeing
pipeline results.

Writes verification decisions into replication_manifest.json per record:
    "verified": true/false, "verified_category": <label or "exclude">,
    "verified_date": <iso date>
The queue view shows only unverified records by default and flags
completion explicitly; a category filter narrows the walk.

For testing, point REPLICATION_MANIFEST at a copy and REPLICATION_DIR at
the same image folder.

Usage:
    python verify_replication.py     # then open http://127.0.0.1:8766
"""
import json
import os
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.environ.get("REPLICATION_MANIFEST") or os.path.join(HERE, "replication_manifest.json")
IMAGES_DIR = os.environ.get("REPLICATION_DIR") or os.path.join(HERE, "replication_corpus")
PORT = int(os.environ.get("REPLICATION_PORT", "8766"))

CATEGORIES = ["portrait_photo", "human_painting", "human_sculpture", "graphic_design"]
EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Replication verification</title>
<style>
body {{ font-family: sans-serif; margin: 20px; max-width: 900px; }}
.rec {{ border: 1px solid #ccc; padding: 12px; margin: 14px 0; }}
.rec img {{ max-width: 420px; max-height: 420px; display: block; }}
.meta {{ color: #555; font-size: 0.9em; }}
button, select {{ margin: 4px 4px 0 0; padding: 6px 10px; }}
.done {{ color: #060; font-weight: bold; }}
.filter {{ margin-bottom: 10px; }}
.filter a {{ margin-right: 8px; }}
</style></head>
<body>
<h1>Replication corpus verification</h1>
<div class="filter">{filters}</div>
<p>{status}</p>
{records}
</body></html>"""

RECORD = """<div class="rec">
<b>{fname}</b> &mdash; category: <b>{category}</b><br>
<img src="/image?name={fname}" alt="{fname}">
<div class="meta">{title}<br>{description}<br>object_type: {otypes} &middot; topic: {topics}</div>
<form method="post" action="/verify">
<input type="hidden" name="fname" value="{fname}">
<button name="verdict" value="correct">Category correct</button>
<select name="corrected">
  <option value="">-- wrong: pick what it is --</option>
  {options}
  <option value="exclude">exclude (not classifiable)</option>
</select>
<button name="verdict" value="wrong">Submit wrong-category</button>
</form>
</div>"""


def load_manifest():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def save_manifest(m):
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1, ensure_ascii=False)


def records_only(m):
    return {k: v for k, v in m.items() if isinstance(v, dict) and "category" in v}


def image_path(fname):
    for ext in EXTS:
        p = os.path.join(IMAGES_DIR, fname + ext)
        if os.path.exists(p):
            return p
    return None


def render(filter_cat):
    m = load_manifest()
    recs = records_only(m)
    unverified = {k: v for k, v in recs.items() if v.get("verified") is None
                  and v.get("status") == "ok"}
    counts = {}
    for v in recs.values():
        c = v.get("category")
        counts[c] = counts.get(c, 0)
        if v.get("verified") is None and v.get("status") == "ok":
            counts[c] += 1
    filters = '<a href="/?cat=">All</a>' + "".join(
        '<a href="/?cat=%s">%s (%d)</a>' % (c, c, counts.get(c, 0))
        for c in CATEGORIES)
    total_un = len(unverified)
    if total_un == 0:
        status = '<span class="done">Verification complete: no unverified records left.</span>'
    else:
        status = "%d unverified records left." % total_un
    shown = unverified
    if filter_cat:
        shown = {k: v for k, v in unverified.items() if v["category"] == filter_cat}
    parts = []
    for fname, v in sorted(shown.items()):
        opts = "".join('<option value="%s">%s</option>' % (c, c)
                       for c in CATEGORIES if c != v["category"])
        parts.append(RECORD.format(
            fname=fname, category=v["category"],
            ext=v.get("file_ext", ".jpg"), title=v.get("title", ""),
            description=(v.get("description") or "")[:300],
            otypes=", ".join(v.get("object_type", [])),
            topics=", ".join(v.get("topic", [])), options=opts))
    return PAGE.format(filters=filters, status=status, records="".join(parts))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            qs = parse_qs(parsed.query)
            cat = (qs.get("cat") or [""])[0]
            self._send(200, render(cat).encode("utf-8"))
        elif parsed.path == "/image":
            qs = parse_qs(parsed.query)
            fname = (qs.get("name") or [""])[0]
            if "/" in fname or "\\" in fname or ".." in fname:
                self._send(400, b"bad name")
                return
            p = image_path(fname)
            if p is None:
                self._send(404, b"no image")
                return
            ext = os.path.splitext(p)[1].lower()
            mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                    ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "application/octet-stream")
            with open(p, "rb") as f:
                self._send(200, f.read(), mime)
        else:
            self._send(404, b"not found")

    def do_POST(self):
        if urlparse(self.path).path != "/verify":
            self._send(404, b"not found")
            return
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        fname = (form.get("fname") or [""])[0]
        verdict = (form.get("verdict") or [""])[0]
        corrected = (form.get("corrected") or [""])[0]
        m = load_manifest()
        recs = records_only(m)
        if fname not in recs:
            self._send(400, b"unknown record")
            return
        rec = recs[fname]
        if verdict == "correct":
            rec["verified"] = True
            rec["verified_category"] = rec["category"]
        elif verdict == "wrong":
            if not corrected:
                self._send(400, b"pick what it is".encode("utf-8"))
                return
            rec["verified"] = False
            rec["verified_category"] = corrected
        else:
            self._send(400, b"bad verdict")
            return
        rec["verified_date"] = date.today().isoformat()
        save_manifest(m)
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print("verify UI on http://127.0.0.1:%d (manifest: %s)" % (PORT, MANIFEST))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
