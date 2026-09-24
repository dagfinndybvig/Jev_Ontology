"""Author humanoid_taxonomy_v9.json: three changes from the complete
ground truth's correction families, under a split-half held-out protocol.

Ground truth is now complete (240/240 labeled, 68 corrected records,
87 facet changes). With no unseen batch left, the held-out protocol
becomes a deterministic split: md5(filename) first hex char, even =
authoring half (132 records), odd = measurement half (108 records).
Every correction family has members in both halves (statue 13/9,
interface 8/8, background-people 4/3), so each change is authored
from one half and measured on the other.

Changes (authored from the authoring half only):
1. representation: v8's subject-decides clause, refined. v8 measured
   inside noise; its "model" wording over-applied to photographed
   robots. v9 says "statue, sculpture, figurine, or display model"
   and adds that a real, functioning robot or machine is photograph.
2. text_screenshot: extended to software interfaces (the largest
   untested family: 16 `other` -> text_screenshot corrections).
   v3's broadening was a measured negative on the personal
   collection; this is the first held-out test on the corpus.
   `other` loses the interface clause accordingly.
3. contains_human yes: a person visible anywhere counts -- small,
   partial, in the background, or in a reflection (6 no -> yes
   corrections).

Requires nothing but the results file; no API calls.
"""
import hashlib
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
V7 = os.path.join(SCRIPT_DIR, "humanoid_taxonomy_v7.json")
SOURCE = os.path.join(SCRIPT_DIR, "library_standin_results.json")
DST = os.path.join(SCRIPT_DIR, "humanoid_taxonomy_v9.json")


def side(name):
    """Deterministic split: md5 first hex char, even = authoring (A),
    odd = measurement (M)."""
    return "A" if int(hashlib.md5(name.encode()).hexdigest()[0], 16) % 2 == 0 else "M"


with open(V7, encoding="utf-8") as f:
    tax = json.load(f)
with open(SOURCE, encoding="utf-8") as f:
    source = json.load(f)

# Family counts on the authoring half -- the signals this revision
# is allowed to see.
fam = {"statue_family": 0, "interface_family": 0, "bg_people": 0}
for name, rec in source.items():
    if side(name) != "A":
        continue
    mc = rec.get("manual_correction") or {}
    c = mc.get("correct")
    if not isinstance(c, dict):
        continue

    def stored(facet):
        v = rec.get(facet)
        return v.get("choice") if isinstance(v, dict) else v

    if c.get("representation") == "statue_or_render" and stored("representation") == "photograph":
        fam["statue_family"] += 1
    if c.get("representation") == "text_screenshot" and stored("representation") == "other":
        fam["interface_family"] += 1
    if c.get("contains_human") == "yes" and stored("contains_human") == "no":
        fam["bg_people"] += 1
print("authoring-half family signals:", fam)

tax["_meta"] = {
    "version": "humanoid_taxonomy_v9",
    "date": "2026-09-24",
    "author": "Mistral Vibe (mistral-vibe)",
    "derived_from": "humanoid_taxonomy_v7",
    "purpose": (
        "Three changes from the complete ground truth's correction families, "
        "under a split-half held-out protocol (md5(filename) first hex char: "
        "even = authoring half, 132 records; odd = measurement half, 108): "
        "(1) v8's subject-decides clause for representation, refined -- "
        "'statue, sculpture, figurine, or display model' instead of 'model', "
        "plus 'a real, functioning robot or machine is photograph' (v8's "
        "'model' over-applied to photographed robots); (2) text_screenshot "
        "extended to software interfaces, the first held-out test of the "
        "interface family (16 `other` -> text_screenshot corrections; v3's "
        "broadening was a measured negative on the personal collection); "
        "(3) contains_human yes counts a person visible anywhere -- small, "
        "partial, background, or reflection (6 no -> yes corrections)."
    ),
    "design_notes": [
        "Split-half held-out protocol: with ground truth complete (240/240), "
        "no unseen batch remains; the split is deterministic "
        "(md5(filename)[0] hex parity) and every correction family has "
        "members in both halves (statue 13/9, interface 8/8, "
        "background-people 4/3). Authored from the authoring half's "
        "corrections only; measured on the measurement half "
        "(measure_taxonomy_v9.py) against v7's stored answers.",
        "The subject-decides clause is v8's, refined: v8 measured inside "
        "noise (fixes 5 / breaks 3, 3 of 8 run-to-run variance; the "
        "clause's 'model' over-applied to photographed robots). v9 "
        "sharpens the wording and adds the functioning-robot exception.",
        "The interface broadening is v3's change re-tested held-out on the "
        "corpus: v3 regressed on the personal collection (representation "
        "76% -> 69%, photographed covers called text_screenshot). The "
        "corpus's 16 interface corrections are the new evidence; the "
        "measurement half's 8 are the test.",
    ],
}

tax["facets"]["contains_human"]["criteria"]["yes"] = (
    "The image itself shows one or more humans (people, faces, bodies) in "
    "any medium: photographed, drawn, illustrated, rendered, sculpted (a "
    "statue or figurine), or sketched in a diagram. A character depicted in "
    "a cartoon, card, or illustration is visible and counts. A person "
    "visible anywhere in the image counts -- even small, partial, in the "
    "background, or in a reflection. A person merely mentioned, named, or "
    "described in text within the image does not count"
)
tax["facets"]["representation"]["criteria"]["photograph"] = (
    "A photograph of a real scene: actual people, objects, or places "
    "captured by a camera -- but the image being a photograph does not "
    "decide this facet: if the subject is a statue, sculpture, figurine, "
    "or display model, it is statue_or_render; if the subject is a "
    "drawing, painting, or poster, it is illustration. A photograph of a "
    "real, functioning robot, machine, or vehicle is photograph"
)
tax["facets"]["representation"]["criteria"]["illustration"] = (
    "A drawing, cartoon, comic, painting, or digital illustration -- "
    "including one photographed or scanned; but if the subject is a "
    "statue, sculpture, figurine, or display model, it is statue_or_render"
)
tax["facets"]["representation"]["criteria"]["statue_or_render"] = (
    "A statue, figurine, sculpture, scale model, display model, or 3D "
    "render of a subject"
)
tax["facets"]["representation"]["criteria"]["text_screenshot"] = (
    "A screenshot or scan of text or a software interface: the image shows "
    "words, code, or an application interface (window, website, terminal), "
    "not a photographed scene"
)
tax["facets"]["representation"]["criteria"]["other"] = (
    "None of the above: a diagram, chart, map, or abstract image"
)

with open(DST, "w", encoding="utf-8") as f:
    json.dump(tax, f, indent=2, ensure_ascii=False)
print("wrote", DST)
