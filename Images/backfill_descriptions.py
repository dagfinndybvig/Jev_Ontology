"""Backfill manifest descriptions from the Smithsonian bulk metadata.

The first fetch took only the first freetext note (capped at 500 chars) --
for most records that is a short label ("Research in Progress") or nothing,
so the verification UI showed heavily truncated descriptions. This script
re-scans the same deterministic metadata files (same index order, same
MAX_FILES bound) and rewrites each manifest record's description as the
join of ALL freetext notes ("label: content", capped at 2000), matched by
idsId == si_id. Metadata only: no image downloads, no category or label
changes -- the manifest is unsealed (verification still open), so this is
pre-sealing enrichment.

Usage:
    python backfill_descriptions.py
"""
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "replication_manifest.json")
BASE = "https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/"
UA = {"User-Agent": "JevOntology-corpus-fetcher/1.0 (academic image-classification research)"}
MAX_FILES = 60  # same bound as fetch_replication_corpus.py


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def as_list(v):
    return v if isinstance(v, list) else []


def description_of(rec):
    ft = rec.get("content", {}).get("freetext")
    if not isinstance(ft, dict):
        return None
    notes = []
    for n in as_list(ft.get("notes")):
        if isinstance(n, dict) and n.get("content"):
            notes.append("%s: %s" % (n.get("label", "Note"), str(n["content"])))
    if not notes:
        return None
    return "\n".join(notes)[:2000]


def main():
    with open(MANIFEST, encoding="utf-8") as f:
        m = json.load(f)
    recs = {k: v for k, v in m.items() if isinstance(v, dict) and "category" in v}
    by_si = {}
    for k, v in recs.items():
        if v.get("si_id"):
            by_si[v["si_id"]] = k
    units = sorted({(v.get("unit") or "").lower() for v in recs.values() if v.get("unit")})
    found = {}
    for unit in units:
        idx = get(BASE + unit + "/index.txt").decode("utf-8", errors="replace")
        files = [l.strip() for l in idx.splitlines() if l.strip()][:MAX_FILES]
        for fu in files:
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
                if not (isinstance(rec, dict) and rec.get("type") == "edanmdm"):
                    continue
                img_ids = set()
                om = rec.get("content", {}).get("descriptiveNonRepeating", {}).get("online_media", {})
                media = om.get("media") if isinstance(om, dict) else None
                if isinstance(media, list):
                    for mi in media:
                        if isinstance(mi, dict) and mi.get("idsId"):
                            img_ids.add(mi["idsId"])
                hit = img_ids & by_si.keys()
                for si in hit:
                    d = description_of(rec)
                    if d is not None:
                        found[by_si[si]] = d
        print("%s: %d/%d descriptions found so far" % (unit, len(found), len(by_si)))
    changed = 0
    for k, d in found.items():
        if recs[k].get("description") != d:
            recs[k]["description"] = d
            changed += 1
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1, ensure_ascii=False)
    lens = sorted(len(v.get("description") or "") for v in recs.values())
    print("updated %d descriptions; new lengths min %d / median %d / max %d"
          % (changed, lens[0], lens[len(lens) // 2], lens[-1]))


if __name__ == "__main__":
    main()
