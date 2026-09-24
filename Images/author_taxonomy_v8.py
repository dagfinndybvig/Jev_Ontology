"""Author humanoid_taxonomy_v8.json: the subject-decides clause for
photograph/illustration, from batch 1's statue-family signals.

The v7 production run against human ground truth (148 labeled records,
663/740 = 90%) left one coherent representation family unaddressed:
a photograph or illustration whose subject is a statue or sculpture
was classified by the image medium, not the subject's representation
(6 batch-1 corrections: photograph->statue_or_render x5,
illustration->statue_or_render x1; e.g. "Photograph: ... dark wooden
statue of a human figure" answered photograph). v8 adds the
subject-decides clause to photograph and illustration; statue_or_render
and the text_screenshot/other pair are unchanged.

Deliberately NOT revised: the 13 batch-2 `other` -> text_screenshot
corrections (interface screenshots Jev hedges to `other`). v3 tried
exactly this broadening ("an application interface" inside
text_screenshot) and it was a measured negative on the personal
collection; the 13 records are real, but the fix direction needs a
designed experiment, not a criterion edit. Documented as an open gap.
"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
V7 = os.path.join(SCRIPT_DIR, "humanoid_taxonomy_v7.json")
DST = os.path.join(SCRIPT_DIR, "humanoid_taxonomy_v8.json")

with open(V7, encoding="utf-8") as f:
    tax = json.load(f)

tax["_meta"] = {
    "version": "humanoid_taxonomy_v8",
    "date": "2026-09-24",
    "author": "Mistral Vibe (mistral-vibe)",
    "derived_from": "humanoid_taxonomy_v7",
    "purpose": (
        "Subject-decides clause for the representation facet: a photograph "
        "or illustration whose subject is a statue, sculpture, or model is "
        "statue_or_render, and one whose subject is a drawing, painting, or "
        "poster is illustration -- the image medium does not decide the "
        "facet, the subject's representation does. Authored from batch 1's "
        "statue-family corrections (2026-09-23: photograph->statue_or_render "
        "x5, illustration->statue_or_render x1, photograph->illustration x3), "
        "a family v6/v7 never addressed."
    ),
    "design_notes": [
        "Held-out protocol (LIBRARY.md Phase 6): authored from batch 1 "
        "signals (2026-09-23, 31 corrections); measured on the 67 records "
        "dated 2026-09-24 (batches 2+3), which no version of the revision "
        "saw during authoring. Baseline: v7's stored answers on the same "
        "descriptions.",
        "Open gap, deliberately not revised: 13 batch-2 corrections where "
        "Jev answers `other` for interface screenshots whose truth is "
        "text_screenshot. v3 tried the interface broadening inside "
        "text_screenshot and it was a measured negative on the personal "
        "collection; the fix direction needs a designed experiment. All 39 "
        "labeled ui_screenshot records are dated 2026-09-24, so no held-out "
        "batch can test the fix either.",
        "text_screenshot and `other` are unchanged from v7 (v4's wording, "
        "the measured optimum from both directions).",
    ],
}

tax["facets"]["representation"]["criteria"]["photograph"] = (
    "A photograph of a real scene: actual people, objects, or places "
    "captured by a camera -- but the image being a photograph does not "
    "decide this facet: if the subject is a statue, sculpture, or model, "
    "it is statue_or_render; if the subject is a drawing, painting, or "
    "poster, it is illustration"
)
tax["facets"]["representation"]["criteria"]["illustration"] = (
    "A drawing, cartoon, comic, painting, or digital illustration -- "
    "including one photographed or scanned; but if the subject is a "
    "statue, sculpture, or model, it is statue_or_render"
)

with open(DST, "w", encoding="utf-8") as f:
    json.dump(tax, f, indent=2, ensure_ascii=False)
print("wrote", DST)
