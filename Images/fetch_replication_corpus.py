"""Fetch a fresh replication corpus from Smithsonian Open Access
(REPLICATION_PROTOCOL.md).

One category per planned class, drawn from the institution's own
object_type/topic terms (REPLICATION_PROTOCOL.md, "Final category
definitions"). Scans unit metadata files (newline-delimited JSON), collects
edanmdm records with CC0 Images media matching the category filter, samples
40 per category at random with a fixed seed, downloads the images, and
writes replication_manifest.json -- the ground truth: filename, category,
title, description, object_type, topic, license, source URL. The manifest
is committed (public CC0 data); images go to replication_corpus/
(gitignored).

Resumable: records already in the manifest with status ok are skipped, and
numbering continues after the category's existing count (the Commons
top-up collision lesson). Metadata scanning is deterministic (file order),
so the fixed-seed sample is stable across re-runs.

Usage:
    python fetch_replication_corpus.py                    # all categories
    python fetch_replication_corpus.py portrait_photo ... # named only
"""
import json
import os
import random
import sys
import time
import urllib.request

BASE = "https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/"
HERE = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.environ.get("REPLICATION_DIR") or os.path.join(HERE, "replication_corpus")
MANIFEST = os.path.join(HERE, "replication_manifest.json")
UA = {"User-Agent": "JevOntology-corpus-fetcher/1.0 (academic image-classification research)"}

# Category definitions are data (REPLICATION_PROTOCOL.md, "Final category
# definitions"): filters on the source's own indexedStructured fields.
# object_type/topic are any-of lists; topic None means no topic filter.
CATEGORIES = {
    "portrait_photo": {"unit": "npg", "object_type": ["Photographs"], "topic": ["Portraits"]},
    "human_painting": {"unit": "saam", "object_type": ["Paintings", "Graphic arts"],
                       "topic": ["Portraits", "Figure group"]},
    "human_sculpture": {"unit": "saam", "object_type": ["Sculpture"], "topic": None},
    "graphic_design": {"unit": "chndm", "object_type": ["Prints", "Bound print", "Wall coverings"],
                       "topic": None},
}
PER_CATEGORY = int(os.environ.get("REPLICATION_PER_CATEGORY", "40"))
POOL = 80        # candidates collected per category before the random sample
MAX_FILES = 60   # metadata files scanned per unit, to bound runtime
SEED = 20260925  # fixed seed, recorded in the manifest (protocol step 2)
DELAY = 1.0      # seconds between downloads; S3/ids.si.edu, not Wikimedia
RETRIES = 3
MAX_BYTES = 12_000_000  # skip pathological originals

MAGIC = {b"\xff\xd8": ".jpg", b"\x89PNG": ".png", b"GIF8": ".gif", b"RIFF": ".webp"}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def unit_files(unit):
    """Metadata file URLs for a unit, in index order."""
    idx = get(BASE + unit + "/index.txt").decode("utf-8", errors="replace")
    return [l.strip() for l in idx.splitlines() if l.strip()]


def iter_records(unit, max_files):
    """Yield edanmdm records from a unit's metadata files (NDJSON)."""
    for fu in unit_files(unit)[:max_files]:
        try:
            data = get(fu).decode("utf-8", errors="replace")
        except Exception as e:
            print("  metadata error %s: %s" % (fu, e))
            continue
        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line, strict=False)
            except Exception:
                continue
            if isinstance(rec, dict) and rec.get("type") == "edanmdm":
                yield rec


def as_list(v):
    return v if isinstance(v, list) else []


def matches(rec, spec):
    """Category filter on the source's own indexedStructured fields."""
    c = rec.get("content")
    if not isinstance(c, dict):
        return False
    ins = c.get("indexedStructured")
    if not isinstance(ins, dict):
        return False
    otypes = [t for t in as_list(ins.get("object_type")) if isinstance(t, str)]
    topics = [t for t in as_list(ins.get("topic")) if isinstance(t, str)]
    if not any(t in otypes for t in spec["object_type"]):
        return False
    want = spec.get("topic")
    if want and not any(t in topics for t in want):
        return False
    return True


def cc0_image(rec):
    """First Images media item with CC0 access, as a dict; None if absent."""
    c = rec.get("content")
    if not isinstance(c, dict):
        return None
    dnr = c.get("descriptiveNonRepeating")
    if not isinstance(dnr, dict):
        return None
    om = dnr.get("online_media")
    media = om.get("media") if isinstance(om, dict) else None
    if not isinstance(media, list):
        return None
    for m in media:
        if not isinstance(m, dict) or m.get("type") != "Images":
            continue
        if not isinstance(m.get("usage"), dict) or m["usage"].get("access") != "CC0":
            continue
        url = m.get("content")
        if isinstance(url, str) and url.startswith("http"):
            return m
    return None


def record_fields(rec, cat, img):
    c = rec.get("content", {})
    dnr = c.get("descriptiveNonRepeating", {}) if isinstance(c, dict) else {}
    ins = c.get("indexedStructured", {}) if isinstance(c, dict) else {}
    notes = ""
    ft = c.get("freetext") if isinstance(c, dict) else None
    if isinstance(ft, dict):
        for n in as_list(ft.get("notes")):
            if isinstance(n, dict) and n.get("content"):
                notes = str(n["content"])[:500]
                break
    return {
        "category": cat,
        "unit": rec.get("unitCode", ""),
        "si_id": img.get("idsId", ""),
        "title": dnr.get("title", rec.get("title", "")),
        "description": notes,
        "object_type": [t for t in as_list(ins.get("object_type")) if isinstance(t, str)],
        "topic": [t for t in as_list(ins.get("topic")) if isinstance(t, str)],
        "license": "CC0",
        "source_url": dnr.get("record_link", rec.get("url", "")),
        "image_url": img.get("content", ""),
    }


def sniff_ext(data):
    for magic, ext in MAGIC.items():
        if data.startswith(magic):
            return ext
    return None


def download(img_url, path):
    """Download an image, preferring the IDS max=960 size; sniff magic bytes
    (the reported type is not trusted -- AGENTS.md gotcha). Returns ext or None."""
    for url in (img_url + "&max=960", img_url):
        for attempt in range(RETRIES):
            try:
                data = get(url, timeout=120)
                if len(data) > MAX_BYTES:
                    break
                ext = sniff_ext(data)
                if ext is None:
                    break
                with open(path + ext, "wb") as f:
                    f.write(data)
                return ext
            except Exception as e:
                if attempt < RETRIES - 1:
                    time.sleep(2 * (attempt + 1))
                else:
                    print("  download error %s: %s" % (url, e))
        # fall through to the next URL variant
    return None


def main():
    named = [a for a in sys.argv[1:] if a in CATEGORIES]
    cats = named or list(CATEGORIES)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    manifest = {}
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)

    # Group categories by unit so each unit's metadata is scanned once.
    by_unit = {}
    for cat in cats:
        by_unit.setdefault(CATEGORIES[cat]["unit"], []).append(cat)

    rng = random.Random(SEED)
    for unit, unit_cats in by_unit.items():
        print("== unit %s: categories %s" % (unit, unit_cats))
        candidates = {cat: [] for cat in unit_cats}
        counts = {cat: 0 for cat in unit_cats}
        for rec in iter_records(unit, MAX_FILES):
            for cat in unit_cats:
                if len(candidates[cat]) >= POOL:
                    continue
                if matches(rec, CATEGORIES[cat]):
                    img = cc0_image(rec)
                    if img is not None:
                        candidates[cat].append((rec, img))
                        counts[cat] += 1
        for cat in unit_cats:
            print("  %s: %d candidates" % (cat, counts[cat]))
            # Fixed-seed shuffle of the whole candidate pool; download in that
            # order and keep the first PER_CATEGORY successes. Dead IDS links
            # (HTTP 404) are common, so a fixed 40 picks would leave the
            # category short -- sampling the usable images keeps the random
            # sample and fills the quota.
            order = list(candidates[cat])
            rng.shuffle(order)
            existing_ids = {v.get("si_id") for k, v in manifest.items()
                            if isinstance(v, dict) and v.get("category") == cat
                            and v.get("status") in ("ok", "error")}
            existing = [k for k, v in manifest.items()
                        if isinstance(v, dict) and v.get("category") == cat]
            seq = len(existing)
            done = 0
            for rec, img in order:
                if done >= PER_CATEGORY:
                    break
                if img.get("idsId") in existing_ids:
                    done += 1
                    continue
                seq += 1
                fname = "%s_%03d" % (cat, seq)
                fields = record_fields(rec, cat, img)
                ext = download(fields["image_url"], os.path.join(IMAGES_DIR, fname))
                if ext is None:
                    fields["status"] = "error"
                    print("  %s: DOWNLOAD FAILED" % fname)
                else:
                    fields["status"] = "ok"
                    fields["file_ext"] = ext
                    fields["verified"] = None
                    done += 1
                manifest[fname] = fields
                with open(MANIFEST, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=1, ensure_ascii=False)
                time.sleep(DELAY)
            print("  %s: %d/%d downloaded" % (cat, done, PER_CATEGORY))

    manifest["_sampling"] = {"seed": SEED, "pool": POOL,
                             "per_category": PER_CATEGORY, "max_files": MAX_FILES}
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    total = sum(1 for v in manifest.values()
                if isinstance(v, dict) and v.get("status") == "ok")
    print("manifest: %d ok records" % total)


if __name__ == "__main__":
    main()
