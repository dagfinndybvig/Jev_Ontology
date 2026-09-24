"""Author humanoid_taxonomy_v10.json: two changes from the v9
production residuals, under the split-half held-out protocol.

The v9 production re-run against the complete ground truth (240/240,
1141/1200 = 95.1%) left three residual families. Two are authorable
from the authoring half's descriptions; one is not:

1. text_screenshot over-calls (5 authoring-half signals): the v9
   interface broadening made Jev call photographed printed matter
   (book covers, a poster, a match program -- the vision preamble
   affirms "The image consists of text") and image-content
   screenshots (a design canvas, an annotation overlay, a grid of
   album covers) text_screenshot. v10 excludes both: printed matter
   is photograph/illustration by its depicted content; a screenshot
   that primarily shows image content rather than text or interface
   controls is other.
2. statue_or_render misses (3 authoring-half signals): robot
   costumes ("two large, detailed robot costumes", "a dog inside a
   cardboard robot costume") and exhibit display models ("on display
   at an exhibit") answered photograph. v10 adds costumes and
   display/exhibit models to statue_or_render.
3. Deliberately NOT revised: the background-people family (6
   contains_human no -> yes corrections). The descriptions do not
   mention the humans (a fossil model, covers whose people are not
   described) -- the signal is not in the text, so no criterion edit
   can fire; it is a vision-layer limit (the description is the
   bottleneck). Documented as an open gap.

The split is the same deterministic md5(filename) first-hex-char
parity as v9's: even = authoring half, odd = measurement half. Every
residual family has members in both halves (statue-miss 5/4,
statue-reverse 2/1, text_screenshot over-call 5/3, background-people
3/3). No API calls.
"""
import hashlib
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
V9 = os.path.join(SCRIPT_DIR, "humanoid_taxonomy_v9.json")
SOURCE = os.path.join(SCRIPT_DIR, "library_standin_results.json")
DST = os.path.join(SCRIPT_DIR, "humanoid_taxonomy_v10.json")


def side(name):
    """Must match measure_taxonomy_v9.py / measure_taxonomy_v10.py."""
    return "A" if int(hashlib.md5(name.encode()).hexdigest()[0], 16) % 2 == 0 else "M"


with open(V9, encoding="utf-8") as f:
    tax = json.load(f)
with open(SOURCE, encoding="utf-8") as f:
    source = json.load(f)

# Authoring-half residual counts -- the signals this revision sees.
fam = {"statue_miss": 0, "statue_rev": 0, "ts_overcall": 0, "bg_people": 0}
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
        fam["statue_miss"] += 1
    if c.get("representation") == "photograph" and stored("representation") == "statue_or_render":
        fam["statue_rev"] += 1
    if stored("representation") == "text_screenshot" and c.get("representation") in ("other", "photograph", "illustration"):
        fam["ts_overcall"] += 1
    if c.get("contains_human") == "yes" and stored("contains_human") == "no":
        fam["bg_people"] += 1
print("authoring-half residual signals:", fam)

tax["_meta"] = {
    "version": "humanoid_taxonomy_v10",
    "date": "2026-09-24",
    "author": "Mistral Vibe (mistral-vibe)",
    "derived_from": "humanoid_taxonomy_v9",
    "purpose": (
        "Two changes from the v9 production residuals, under the split-half "
        "held-out protocol (md5(filename) first hex char: even = authoring "
        "half, odd = measurement half): (1) text_screenshot narrowed against "
        "the v9 broadening's over-calls -- printed matter photographed or "
        "illustrated (book covers, posters, programs, packages) is "
        "photograph/illustration by its depicted content even when dominated "
        "by text, and a screenshot that primarily shows image content (a "
        "design canvas, annotation overlay, or image grid) is other; (2) "
        "statue_or_render extended to robot costumes and display/exhibit "
        "models. The background-people family (6 contains_human corrections) "
        "is deliberately not revised: the descriptions do not mention the "
        "humans, so no criterion edit can fire -- a vision-layer limit."
    ),
    "design_notes": [
        "Split-half held-out protocol: same deterministic md5 split as v9; "
        "every residual family has members in both halves (statue-miss 5/4, "
        "statue-reverse 2/1, text_screenshot over-call 5/3, "
        "background-people 3/3). Authored from the authoring half's "
        "residuals only; measured on the measurement half "
        "(measure_taxonomy_v10.py) against v9's stored answers.",
        "The text_screenshot narrowing is direction-tested: v6's "
        "covers-out narrowing was a measured negative under v4's wording "
        "(it broke ui_screenshots); v10 keeps the v9 interface inclusion "
        "and excludes only printed matter and image-content screenshots -- "
        "the measurement half decides.",
        "Open gap, deliberately not revised: the statue clause's scene "
        "boundary (a sculpture mounted on a building and a statue on an "
        "altar were corrected to photograph, while a distant statue in a "
        "landscape was corrected to statue_or_render) -- the reviewer "
        "labels are inconsistent here; no authorable criterion. The "
        "background-people family is a vision-layer limit (the "
        "descriptions do not mention the humans).",
    ],
}

tax["facets"]["representation"]["criteria"]["statue_or_render"] = (
    "A statue, figurine, sculpture, scale model, display model, or 3D "
    "render of a subject -- including a robot costume (a wearable "
    "being-like figure) and a robot or figure shown as a display or "
    "exhibit model"
)
tax["facets"]["representation"]["criteria"]["text_screenshot"] = (
    "A screenshot or scan of text or a software interface: the image shows "
    "words, code, or an application interface (window, website, terminal), "
    "not a photographed scene. Printed matter photographed or illustrated -- "
    "a book cover, poster, program, or package -- is photograph or "
    "illustration by its depicted content, not text_screenshot, even when "
    "dominated by text; and a screenshot that primarily shows image content "
    "rather than text or interface controls (a design canvas, an annotation "
    "overlay, a grid of images) is other"
)
tax["facets"]["representation"]["criteria"]["other"] = (
    "None of the above: a diagram, chart, map, or abstract image; also an "
    "interface screenshot that primarily shows image content rather than "
    "text or interface controls (a design canvas, an annotation overlay, a "
    "grid of images)"
)

with open(DST, "w", encoding="utf-8") as f:
    json.dump(tax, f, indent=2, ensure_ascii=False)
print("wrote", DST)
