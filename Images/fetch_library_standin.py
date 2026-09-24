"""Fetch a stand-in library corpus from Wikimedia Commons (STATUS.md next steps item 1).

Queries one Commons category per taxonomy class, downloads a fixed number of
images per category (deterministic stride over the category members, not the
alphabetical head), and writes library_manifest.json -- the stand-in ground
truth: filename, category, Commons description, license, and the structured
"depicts" (P180) statements resolved to Wikidata labels. The corpus is public
data, so the manifest is committed; the images are gitignored.

Resumable: files already in the manifest with status ok are skipped.
Category names are data (CATEGORIES below); adjust without touching code.

Usage:
    python fetch_library_standin.py              # all categories
    python fetch_library_standin.py statue ...   # only the named classes
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
HERE = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.environ.get("LIBRARY_STANDIN_DIR") or os.path.join(HERE, "library_standin")
MANIFEST = os.path.join(HERE, "library_manifest.json")
UA = {"User-Agent": "JevOntology-corpus-fetcher/1.0 (academic image-classification research)"}

# One Commons category per taxonomy class. Names are data; adjust freely.
CATEGORIES = {
    "statue": "Category:Statues",
    "humanoid_robot": "Category:Humanoid robots",
    "book_cover": "Category:Book covers",
    "human_photo": "Category:Portrait photographs",
    "human_illustration": "Category:Paintings of people",
    "ui_screenshot": "Category:Screenshots of software",
}
PER_CATEGORY = int(os.environ.get("LIBRARY_PER_CATEGORY", "40"))
POOL = 200          # members fetched per category before the stride sample
THUMB_WIDTH = 960   # a Wikimedia standard thumbnail size (1024 is not; see w.wiki/GHai)
EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff"}
DELAY = 20.0        # seconds between downloads; Commons rate-limits bursts hard
                    # (5s drew 429s on the 2026-09-23 top-up; 20s after cooldown)
RETRIES = 3         # with backoff, on HTTP 429

TAGS = re.compile(r"<[^>]+>")


def api(params):
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def category_members(category, pool):
    """File titles in a category, up to pool size."""
    titles, cont = [], {}
    while True:
        d = api({"action": "query", "list": "categorymembers", "cmtitle": category,
                 "cmtype": "file", "cmlimit": "50", **cont})
        titles += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        if "continue" not in d or len(titles) >= pool:
            break
        cont = d["continue"]
    return titles[:pool]


def stride_sample(titles, n):
    """Deterministic spread over the pool, not the alphabetical head."""
    if len(titles) <= n:
        return titles
    step = len(titles) / n
    return [titles[int(i * step)] for i in range(n)]


def batched(titles, prop, extra=None, batch=50):
    """prop=imageinfo or pageprops for up to 50 titles per call."""
    out = {}
    for i in range(0, len(titles), batch):
        d = api({"action": "query", "titles": "|".join(titles[i:i + batch]),
                 "prop": prop, **(extra or {})})
        for page in d.get("query", {}).get("pages", {}).values():
            out[page["title"]] = page
        time.sleep(1.0)
    return out


def depicts_by_title(titles):
    """P180 (depicts) statements per file title, resolved to English labels.

    Commons structured data lives in MediaInfo entities (M-ids), looked
    up by site+title; pageprops.wikibase_item is the Wikidata Q-id link
    and is empty for most files (found live, 2026-09-23).
    """
    claims = {}
    for i in range(0, len(titles), 50):
        d = api({"action": "wbgetentities", "sites": "commonswiki",
                 "titles": "|".join(titles[i:i + 50]), "props": "claims|info"})
        for ent in d.get("entities", {}).values():
            title = ent.get("title", "")
            claims[title] = [c["mainsnak"]["datavalue"]["value"]["id"]
                             for c in ent.get("claims", {}).get("P180", [])
                             if c.get("mainsnak", {}).get("datavalue", {}).get("value")]
        time.sleep(DELAY)
    qids = sorted({q for qs in claims.values() for q in qs})
    labels = {}
    for i in range(0, len(qids), 50):
        d = api({"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
                 "props": "labels", "languages": "en"})
        for eid, ent in d.get("entities", {}).items():
            label = ent.get("labels", {}).get("en", {}).get("value")
            if label:
                labels[eid] = label
        time.sleep(DELAY)
    return {t: [labels[q] for q in qs if q in labels] for t, qs in claims.items()}


def download(url, dest):
    """Fetch bytes with backoff on HTTP 429 (Commons rate-limits bursts)."""
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            with open(dest, "wb") as f:
                f.write(data)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < RETRIES - 1:
                time.sleep(60 * (attempt + 1))
                continue
            raise
    return False


def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_manifest(manifest):
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    only = set(sys.argv[1:])
    cats = {k: v for k, v in CATEGORIES.items() if not only or k in only}
    unknown = only - set(CATEGORIES)
    if unknown:
        print(f"Unknown classes: {', '.join(sorted(unknown))}")
        sys.exit(1)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    manifest = load_manifest()
    done = {k for k, v in manifest.items() if v.get("status") == "ok"}
    seen_titles = {v.get("title") for v in manifest.values()}

    for cls, category in cats.items():
        print(f"\n=== {cls}: {category} ===")
        try:
            pool = category_members(category, POOL)
        except Exception as e:
            print(f"  category fetch failed: {e}")
            continue
        if not pool:
            print("  EMPTY -- check the category name")
            continue
        # Resume tops up to PER_CATEGORY total for the category.
        have = sum(1 for v in manifest.values()
                   if v.get("status") == "ok" and v.get("category") == cls)
        need = PER_CATEGORY - have
        if need <= 0:
            print(f"  already have {have}, target {PER_CATEGORY}")
            continue
        fresh = [t for t in pool if t not in seen_titles]
        titles = stride_sample(fresh, need)
        infos = batched(titles, "imageinfo",
                        {"iiprop": "url|extmetadata|size", "iiurlwidth": str(THUMB_WIDTH)})
        depicts = depicts_by_title(titles)

        got = 0
        next_num = have  # resume numbering after the existing files
        for title in titles:
            info = (infos.get(title, {}).get("imageinfo") or [{}])[0]
            thumb = info.get("thumburl") or info.get("url")
            if not thumb:
                continue
            ext = os.path.splitext(urllib.parse.urlparse(thumb).path)[1].lower()
            if ext not in EXTS:
                continue
            fname = f"{cls}_{next_num + 1:03d}{ext}"
            while fname in done:
                next_num += 1
                fname = f"{cls}_{next_num + 1:03d}{ext}"
            dest = os.path.join(IMAGES_DIR, fname)
            try:
                if not download(thumb, dest):
                    continue
            except Exception as e:
                print(f"  download failed {title}: {e}")
                continue
            meta = info.get("extmetadata", {})
            manifest[fname] = {
                "status": "ok",
                "category": cls,
                "commons_category": category,
                "title": title,
                "description": TAGS.sub("", meta.get("ImageDescription", {}).get("value", "")).strip()[:500],
                "license": meta.get("LicenseShortName", {}).get("value", ""),
                "depicts": depicts.get(title, []),
                "url": info.get("descriptionurl", ""),
                "file": fname,
            }
            save_manifest(manifest)
            seen_titles.add(title)
            next_num += 1
            got += 1
            time.sleep(DELAY)
        print(f"  fetched {got} of {PER_CATEGORY} (pool {len(pool)})")

    ok = [v for v in manifest.values() if v.get("status") == "ok"]
    by_cat = {}
    for v in ok:
        by_cat[v["category"]] = by_cat.get(v["category"], 0) + 1
    print(f"\nDone. Total {len(ok)} images in {IMAGES_DIR}")
    for cls in sorted(by_cat):
        print(f"  {cls}: {by_cat[cls]}")
    print(f"Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
