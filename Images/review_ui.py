"""Local review interface for the humanoid pilot results.

Serves a single-page app on localhost (bind 127.0.0.1 only): the
reviewer walks the review queue, sees each image next to Jev's
classification and confidences, and confirms or corrects the category.
Choices come from the taxonomy JSON, so the UI is data-driven too.

Corrections are written back to the pilot results file as
manual_correction blocks -- raw Jev answers are never modified
(see AGENTS.md). Confirmed-as-correct records also get a block, so
the review pass doubles as the Phase 0 ground-truth seed.

Usage:
    python review_ui.py [port]        # default 8765, then open
                                      # http://localhost:8765

Environment:
    PICTURES_DIR          image folder (required)
    TAXONOMY              taxonomy filename in this dir (v2 default)
    REVIEW_RESULTS        results JSON path (default: pilot results;
                          set to a copy for testing)
"""
import datetime
import json
import os
import random
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY = os.path.join(SCRIPT_DIR, os.environ.get("TAXONOMY", "humanoid_taxonomy_v2.json"))
RESULTS = os.environ.get(
    "REVIEW_RESULTS",
    os.path.join(SCRIPT_DIR, "humanoid_pilot_results.json"),
)
PICTURES = os.environ.get("PICTURES_DIR", "")

FACETS = ["contains_human", "contains_robot", "contains_android", "primary_subject", "representation"]
REVIEW_THRESHOLD = 0.7

MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
    ".avif": "image/avif", ".tiff": "image/tiff", ".tif": "image/tiff",
    ".jfif": "image/jpeg",
}


def tiff_as_png(path, name):
    """Browsers cannot render TIFF; convert to PNG (cached) with Pillow.

    Returns (bytes, mime). Raises ImportError if Pillow is missing.
    """
    cache = os.path.join(tempfile.gettempdir(), "review_ui_png_cache")
    os.makedirs(cache, exist_ok=True)
    out = os.path.join(cache, name + ".png")
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(path):
        from PIL import Image
        with Image.open(path) as im:
            im.load()
            if im.mode in ("P", "LA", "PA", "RGBA") or "A" in im.mode:
                im = im.convert("RGBA")
                background = Image.new("RGB", im.size, (255, 255, 255))
                background.paste(im, mask=im.split()[-1])
                im = background
            elif im.mode != "RGB":
                im = im.convert("RGB")
            im.save(out, "PNG")
    with open(out, "rb") as f:
        return f.read(), "image/png"

_lock = threading.Lock()
_results = None


def load_results():
    global _results
    if _results is None:
        if not os.path.exists(RESULTS):
            sys.exit(f"Results file not found: {RESULTS}")
        with open(RESULTS, "r", encoding="utf-8") as f:
            _results = json.load(f)
    return _results


def save_results():
    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(_results, f, indent=2, ensure_ascii=False)


def taxonomy_choices():
    with open(TAXONOMY, "r", encoding="utf-8") as f:
        tax = json.load(f)
    return {
        "primary_subject": list(tax["facets"]["primary_subject"]["criteria"].keys()),
        "representation": list(tax["facets"]["representation"]["criteria"].keys()),
        "definitions": {
            f: tax["facets"][f]["criteria"]
            for f in ["primary_subject", "representation"]
        },
    }


def record_view(name, r):
    return {
        "file": name,
        "description": r.get("description", ""),
        "facets": {f: {"choice": r[f]["choice"], "confidence": r[f]["confidence"]}
                   for f in FACETS if f in r},
        "queued": any(r[f]["confidence"] < REVIEW_THRESHOLD for f in FACETS if f in r),
        "reviewed": "manual_correction" in r,
        "correction": r.get("manual_correction"),
    }


SAMPLE_PATH = os.environ.get(
    "REVIEW_SAMPLE",
    os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "Ontology_private_backup",
                                  "confident_sample_v1.json")),
)
SAMPLE_SIZE = 30
SAMPLE_SEED = 20260923


def confident_sample(res):
    """Deterministic stratified sample of unreviewed, fully confident records.

    Half from the 0.7-0.9 band, half from 0.9-1.0, spread round-robin
    across representation classes. Computed once, then persisted, so
    the sample is stable across sessions.
    """
    if os.path.exists(SAMPLE_PATH):
        with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)["files"]

    cands = []
    for name, r in res.items():
        if r.get("status") != "ok" or "manual_correction" in r:
            continue
        if any(r[f]["confidence"] < REVIEW_THRESHOLD for f in FACETS):
            continue
        cands.append((name, min(r[f]["confidence"] for f in FACETS),
                      r["representation"]["choice"]))

    rng = random.Random(SAMPLE_SEED)
    picked = []
    per_band = SAMPLE_SIZE // 2
    for band in (lambda c: c < 0.9, lambda c: c >= 0.9):
        by_rep = {}
        for name, conf, rep in cands:
            if band(conf):
                by_rep.setdefault(rep, []).append(name)
        reps = sorted(by_rep)
        rng.shuffle(reps)
        for rep in reps:
            rng.shuffle(by_rep[rep])
        count, i = 0, 0
        while count < per_band and any(by_rep[r] for r in reps):
            rep = reps[i % len(reps)]
            if by_rep[rep]:
                picked.append(by_rep[rep].pop())
                count += 1
            i += 1

    files = sorted(picked)
    os.makedirs(os.path.dirname(SAMPLE_PATH), exist_ok=True)
    with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
        json.dump({"date": datetime.date.today().isoformat(),
                   "files": files}, f, indent=1, ensure_ascii=False)
    return files


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Humanoid pilot review</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; font-family: Segoe UI, Arial, sans-serif; background: #16181d; color: #e6e6e6; }
  header { padding: 10px 18px; background: #1e2128; border-bottom: 1px solid #333; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
  header h1 { font-size: 15px; margin: 0; font-weight: 600; }
  .filters button, .meta span { font-size: 13px; }
  .filters button { background: #2a2e37; color: #ccc; border: 1px solid #3a3f4a; padding: 4px 10px; cursor: pointer; border-radius: 4px; }
  .filters button.active { background: #3b6ea5; color: #fff; border-color: #3b6ea5; }
  .meta { margin-left: auto; color: #9aa0ab; }
  main { display: flex; height: calc(100vh - 47px); }
  .left { flex: 1.4; display: flex; align-items: center; justify-content: center; padding: 14px; min-width: 0; background: #101216; }
  .left img { max-width: 100%; max-height: calc(100vh - 75px); object-fit: contain; }
  .right { flex: 1; min-width: 380px; max-width: 560px; overflow-y: auto; padding: 16px 20px; border-left: 1px solid #2a2e37; }
  .fname { font-family: Consolas, monospace; font-size: 14px; color: #9fd0ff; word-break: break-all; }
  .desc { font-size: 13px; color: #b9bfc9; margin: 10px 0; padding: 8px 10px; background: #1c2027; border-radius: 6px; white-space: pre-wrap; }
  .facet { margin: 8px 0; font-size: 13px; }
  .facet .row { display: flex; justify-content: space-between; }
  .bar { height: 5px; background: #2a2e37; border-radius: 3px; margin-top: 3px; }
  .bar i { display: block; height: 100%; border-radius: 3px; background: #4caf7d; }
  .bar i.low { background: #c7903b; }
  h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; color: #8b93a0; margin: 20px 0 6px; }
  .choices { display: flex; flex-wrap: wrap; gap: 6px; }
  .choices button { padding: 7px 12px; font-size: 13px; background: #262a33; color: #d6dae2; border: 1px solid #3a3f4a; border-radius: 5px; cursor: pointer; }
  .choices button.sel { background: #3b6ea5; border-color: #6fa3d8; color: #fff; }
  .choices button small { display: block; font-size: 10px; color: #9096a1; }
  .choices button.sel small { color: #cfe4fb; }
  .flags { display: flex; gap: 14px; font-size: 13px; margin-top: 6px; }
  .flags label { cursor: pointer; }
  #note { width: 100%; box-sizing: border-box; margin-top: 10px; background: #1c2027; color: #e6e6e6; border: 1px solid #3a3f4a; border-radius: 5px; padding: 7px 9px; font-size: 13px; }
  .actions { display: flex; gap: 8px; margin-top: 14px; }
  .actions button { padding: 9px 14px; font-size: 14px; border-radius: 5px; cursor: pointer; border: 1px solid #3a3f4a; background: #2a2e37; color: #ddd; }
  #save { background: #2e7d4f; border-color: #2e7d4f; color: #fff; font-weight: 600; }
  #save:hover { background: #35915d; }
  #uncorrect { color: #d98a8a; }
  .status { font-size: 12px; color: #8b93a0; margin-top: 10px; min-height: 16px; }
  .corrbox { font-size: 13px; background: #243026; border: 1px solid #3f5a44; padding: 8px 10px; border-radius: 6px; margin-top: 6px; }
  .hint { font-size: 11px; color: #6d7480; margin-top: 16px; line-height: 1.6; }
  .empty { padding: 40px; text-align: center; color: #8b93a0; }
</style>
</head>
<body>
<header>
  <h1>Humanoid pilot review</h1>
  <div class="filters" id="filters"></div>
  <div class="meta" id="meta"></div>
</header>
<main>
  <div class="left" id="imgpane"></div>
  <div class="right" id="pane"><div class="empty">Loading...</div></div>
</main>
<script>
let records = [], defs = {}, order = [], idx = 0;
let filter = 'queue', pendingOnly = true, sampleFiles = [];
let pick = {subject: null, rep: null, flags: {contains_human: false, contains_robot: false, contains_android: false}};
const SUBKEYS = ['contains_human','contains_robot','contains_android'];

function subjectDefaults(s) {
  return { contains_human: s === 'human' || s === 'multiple',
           contains_robot: s === 'robot' || s === 'multiple',
           contains_android: s === 'android' };
}

async function init() {
  try {
    const tax = await (await fetch('/api/taxonomy')).json();
    defs = tax.definitions;
    const data = await (await fetch('/api/records')).json();
    records = data.records;
    const smp = await (await fetch('/api/sample')).json();
    sampleFiles = smp.files || [];
    rebuild();
  } catch (e) {
    document.getElementById('pane').innerHTML =
      '<div class="empty">Error: ' + esc(String(e)) + '</div>';
  }
}

function buildOrder() {
  const inFilter = r => filter === 'all' ? true : (filter === 'queue' ? (r.queued && (!pendingOnly || !r.reviewed)) : filter === 'sample' ? (sampleFiles.includes(r.file) && (!pendingOnly || !r.reviewed)) : r.reviewed);
  const list = records.filter(inFilter);
  list.sort((a, b) => (a.reviewed - b.reviewed) || (minConf(a) - minConf(b)));
  return list.map(r => r.file);
}
function minConf(r) { return Math.min(...Object.values(r.facets).map(f => f.confidence)); }

function rebuild() {
  order = buildOrder();
  const f = document.getElementById('filters');
  f.innerHTML = '';
  const counts = { queue: records.filter(r => r.queued).length, all: records.length, reviewed: records.filter(r => r.reviewed).length };
  [['queue','Queue'], ['sample','Sample'], ['all','All'], ['reviewed','Reviewed']].forEach(([k, label]) => {
    const b = document.createElement('button');
    if (k === 'queue' && pendingOnly)
      b.textContent = 'Queue (' + records.filter(r => r.queued && !r.reviewed).length + ' pending of ' + counts.queue + ')';
    else if (k === 'sample')
      b.textContent = 'Sample (' + records.filter(r => sampleFiles.includes(r.file) && !r.reviewed).length + ' pending of ' + sampleFiles.length + ')';
    else
      b.textContent = label + ' (' + counts[k] + ')';
    b.className = filter === k ? 'active' : '';
    b.onclick = () => { filter = k; rebuild(); };
    f.appendChild(b);
  });
  const lab = document.createElement('label');
  lab.style.cssText = 'font-size:12px;color:#9aa0ab;display:flex;align-items:center;gap:4px;margin-left:6px;cursor:pointer';
  const cb = document.createElement('input');
  cb.type = 'checkbox';
  cb.checked = pendingOnly;
  cb.disabled = filter !== 'queue' && filter !== 'sample';
  cb.onchange = () => { pendingOnly = cb.checked; rebuild(); };
  lab.appendChild(cb);
  lab.appendChild(document.createTextNode('pending only'));
  f.appendChild(lab);
  idx = Math.min(idx, Math.max(order.length - 1, 0));
  render();
}

function render() {
  const pending = records.filter(r => r.queued && !r.reviewed).length;
  document.getElementById('meta').innerHTML =
    (order.length ? (idx + 1) + ' / ' + order.length : '0') +
    '  |  pending: ' + pending +
    (pending === 0 && records.some(r => r.queued) ? '  <span style="color:#4caf7d">queue complete</span>' : '');
  if (!order.length) {
    document.getElementById('imgpane').innerHTML = '';
    const hasAny = filter === 'queue' ? records.some(r => r.queued) : sampleFiles.length > 0;
    const done = (filter === 'queue' || filter === 'sample') && pendingOnly && hasAny;
    const samplePending = sampleFiles.filter(f => {
      const rr = records.find(x => x.file === f);
      return rr && !rr.reviewed;
    }).length;
    document.getElementById('pane').innerHTML = '<div class="empty">' + (done ?
      '<strong style="color:#4caf7d">Review complete.</strong><br><br>' +
      'Every record in this filter has a label.' +
      (filter === 'queue' && samplePending > 0
        ? '<br><br>The <strong>Sample</strong> filter still has ' + samplePending +
          ' confident records pending.'
        : '') +
      '<br><br>Use the Reviewed filter to browse ' +
      'your labels, or All to see the whole collection.' :
      'No records in this filter.') + '</div>';
    return;
  }
  const r = records.find(x => x.file === order[idx]);
  const imgpane = document.getElementById('imgpane');
  imgpane.innerHTML = '<img src="/image/' + encodeURIComponent(r.file) + '" alt="image">';
  const im = imgpane.querySelector ? imgpane.querySelector('img') : null;
  if (im) {
    im.onerror = () => {
      imgpane.innerHTML = '<div style="color:#d98a8a;font-size:14px;padding:24px">' +
        'Failed to load image: ' + esc(r.file) + '</div>';
    };
  }
  const pane = document.getElementById('pane');
  let h = '<div class="fname">' + r.file + (r.queued ? ' <span style="color:#c7903b">[queued]</span>' : '') + '</div>';
  h += '<div class="desc">' + esc(r.description) + '</div>';
  for (const [name, f] of Object.entries(r.facets)) {
    h += '<div class="facet"><div class="row"><span>' + name + '</span>' +
         '<span>' + f.choice + ' (' + f.confidence.toFixed(2) + ')</span></div>' +
         '<div class="bar"><i class="' + (f.confidence < 0.7 ? 'low' : '') + '" style="width:' + (f.confidence * 100) + '%"></i></div></div>';
  }
  if (r.reviewed && r.correction) {
    h += '<div class="corrbox">Reviewed ' + (r.correction.date || '') + ': ' +
         (r.correction.correct ? (r.correction.correct.primary_subject + ' / ' + r.correction.correct.representation) : '') +
         (r.correction.reason ? ' &mdash; ' + esc(r.correction.reason) : '') + '</div>';
  }
  h += '<h2>Primary subject</h2><div class="choices" id="subj"></div>';
  h += '<h2>Representation</h2><div class="choices" id="rep"></div>';
  h += '<h2>Contains</h2><div class="flags" id="flags"></div>';
  h += '<input id="note" placeholder="Optional note (becomes the correction reason)">';
  h += '<div class="actions">' +
       '<button id="save">Save &amp; next (Enter)</button>' +
       '<button id="skip">Skip &rarr;</button>' +
       '<button id="back">&larr; Back</button>' +
       (r.reviewed ? '<button id="uncorrect">Remove correction</button>' : '') +
       '</div><div class="status" id="status"></div>' +
       '<div class="hint">Keys: 1-5 subject, Q W E R T representation, Enter save &amp; next, arrows navigate.</div>';
  pane.innerHTML = h;

  pick.subject = r.facets.primary_subject ? r.facets.primary_subject.choice : null;
  pick.rep = r.facets.representation ? r.facets.representation.choice : null;
  const corr = r.correction && r.correction.correct;
  if (corr) { pick.subject = corr.primary_subject; pick.rep = corr.representation;
              pick.flags = {contains_human: corr.contains_human === 'yes', contains_robot: corr.contains_robot === 'yes', contains_android: corr.contains_android === 'yes'}; }
  else pick.flags = subjectDefaults(pick.subject);

  drawChoices('subj', 'subject', defs.primary_subject);
  drawChoices('rep', 'rep', defs.representation);
  drawFlags();

  document.getElementById('save').onclick = save;
  document.getElementById('skip').onclick = () => { idx = Math.min(idx + 1, order.length - 1); render(); };
  document.getElementById('back').onclick = () => { idx = Math.max(idx - 1, 0); render(); };
  const un = document.getElementById('uncorrect');
  if (un) un.onclick = uncorrect;
  document.getElementById('note').focus();
}

function drawChoices(elId, kind, d) {
  const el = document.getElementById(elId);
  el.innerHTML = '';
  Object.keys(d).forEach((c, i) => {
    const b = document.createElement('button');
    b.innerHTML = c + '<small>' + (kind === 'subject' ? (i + 1) : 'QWERT'[i]) + ' &middot; ' + esc(d[c]).slice(0, 60) + '</small>';
    b.className = (kind === 'subject' ? pick.subject : pick.rep) === c ? 'sel' : '';
    b.onclick = () => {
      if (kind === 'subject') { pick.subject = c; pick.flags = subjectDefaults(c); }
      else pick.rep = c;
      drawChoices('subj', 'subject', defs.primary_subject);
      drawChoices('rep', 'rep', defs.representation);
      drawFlags();
    };
    el.appendChild(b);
  });
}

function drawFlags() {
  const el = document.getElementById('flags');
  el.innerHTML = '';
  SUBKEYS.forEach(k => {
    const l = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = pick.flags[k];
    cb.onchange = () => { pick.flags[k] = cb.checked; };
    l.appendChild(cb);
    l.appendChild(document.createTextNode(' ' + k));
    el.appendChild(l);
  });
}

async function save() {
  const r = records.find(x => x.file === order[idx]);
  if (!pick.subject || !pick.rep) { document.getElementById('status').textContent = 'Pick both a subject and a representation first.'; return; }
  const body = {
    correct: {
      primary_subject: pick.subject,
      representation: pick.rep,
      contains_human: pick.flags.contains_human ? 'yes' : 'no',
      contains_robot: pick.flags.contains_robot ? 'yes' : 'no',
      contains_android: pick.flags.contains_android ? 'yes' : 'no',
    },
    note: document.getElementById('note').value.trim(),
  };
  const resp = await fetch('/api/correct/' + encodeURIComponent(r.file), {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const out = await resp.json();
  document.getElementById('status').textContent = out.ok ? 'Saved.' : ('Error: ' + out.error);
  if (out.ok) { r.reviewed = true; r.correction = out.correction;
    setTimeout(() => {
      if ((filter === 'queue' || filter === 'sample') && pendingOnly) rebuild();
      else { idx = Math.min(idx + 1, order.length - 1); render(); }
    }, 250); }
}

async function uncorrect() {
  const r = records.find(x => x.file === order[idx]);
  const resp = await fetch('/api/uncorrect/' + encodeURIComponent(r.file), {method: 'POST'});
  const out = await resp.json();
  if (out.ok) { r.reviewed = false; r.correction = null; rebuild(); }
}

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' && e.key !== 'Enter') return;
  const r = records.find(x => x.file === order[idx]);
  if (!r) return;
  const subs = Object.keys(defs.primary_subject), reps = Object.keys(defs.representation);
  if (e.key >= '1' && e.key <= '5' && subs[+e.key - 1]) { pick.subject = subs[+e.key - 1]; pick.flags = subjectDefaults(pick.subject); render(); }
  else if ('QWERT'.includes(e.key) && e.key.length === 1) { const i = 'QWERT'.indexOf(e.key.toUpperCase()); if (reps[i]) { pick.rep = reps[i]; render(); } }
  else if (e.key === 'Enter') { e.preventDefault(); save(); }
  else if (e.key === 'ArrowRight') { idx = Math.min(idx + 1, order.length - 1); render(); }
  else if (e.key === 'ArrowLeft') { idx = Math.max(idx - 1, 0); render(); }
});

function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

init();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_request(self, code="-", size="-"):
        print(f"REQ {self.command} {self.path} -> {code}", flush=True)

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/taxonomy":
            self._json(taxonomy_choices())
        elif path == "/api/records":
            with _lock:
                res = load_results()
                views = [record_view(n, r) for n, r in res.items() if r.get("status") == "ok"]
            self._json({"records": views})
        elif path == "/api/sample":
            with _lock:
                res = load_results()
                files = confident_sample(res)
            self._json({"files": files})
        elif path.startswith("/image/"):
            name = unquote(path[len("/image/"):])
            if os.path.basename(name) != name or "/" in name or "\\" in name:
                self._send(403, b"forbidden", "text/plain")
                return
            fp = os.path.join(PICTURES, name)
            if not os.path.isfile(fp):
                self._send(404, b"not found", "text/plain")
                return
            ext = os.path.splitext(name)[1].lower()
            if ext in (".tiff", ".tif"):
                try:
                    body, mime = tiff_as_png(fp, name)
                except ImportError:
                    self._send(500, b"TIFF display needs Pillow (pip install pillow)",
                               "text/plain")
                    return
                self._send(200, body, mime)
                return
            with open(fp, "rb") as f:
                self._send(200, f.read(), MIME.get(ext, "application/octet-stream"))
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        path = urlparse(self.path).path
        name = unquote(path[path.rfind("/") + 1:])
        with _lock:
            res = load_results()
            if name not in res or res[name].get("status") != "ok":
                self._json({"ok": False, "error": "unknown record"}, 404)
                return
            if path.startswith("/api/correct/"):
                length = int(self.headers.get("Content-Length", 0))
                try:
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                    correct = {f: body["correct"][f] for f in FACETS}
                except Exception as e:
                    self._json({"ok": False, "error": f"bad body: {e}"}, 400)
                    return
                r = res[name]
                raw_same = all(r[f]["choice"] == correct[f] for f in FACETS if f in r)
                kind = "Confirmed in review" if raw_same else "Corrected in review"
                r["manual_correction"] = {
                    "date": datetime.date.today().isoformat(),
                    "correct": correct,
                    "reason": body.get("note") or kind + " (review_ui)",
                    "raw_jev_preserved": True,
                }
                save_results()
                self._json({"ok": True, "correction": r["manual_correction"]})
            elif path.startswith("/api/uncorrect/"):
                if "manual_correction" in res[name]:
                    del res[name]["manual_correction"]
                    save_results()
                self._json({"ok": True})
            else:
                self._json({"ok": False, "error": "unknown endpoint"}, 404)


def main():
    if not PICTURES or not os.path.isdir(PICTURES):
        sys.exit("Set PICTURES_DIR to the folder of images")
    if not os.path.exists(RESULTS):
        sys.exit(f"Results file not found: {RESULTS}")
    if not os.path.exists(TAXONOMY):
        sys.exit(f"Taxonomy not found: {TAXONOMY}")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Review UI: http://localhost:{port}  ({len(load_results())} records)")
    print(f"Images: {PICTURES}")
    print(f"Results: {RESULTS}")
    server.serve_forever()


if __name__ == "__main__":
    main()
