"""Author humanoid_taxonomy_v6.json from humanoid_taxonomy_v4.json.

Authored from the stand-in corpus batch 1 corrections (2026-09-23,
31 corrections in four families) per the LIBRARY.md Phase 6 held-out
protocol; measured on batch 2 (2026-09-24, 55 labeled records), which
the revision never saw.

Changes from v4:
1. contains_human / primary_subject: the depiction-medium enumeration
   omitted sculpted works -- 9 statue corrections answered no/none on
   statues of humans. "Sculpted (a statue or figurine)" is added.
2. contains_android / primary_subject.android: "the image or its
   context identifies them as artificial" over-fired on plain
   mechanical robots (8 corrections). Android now requires a
   human-passing appearance (human face, skin, proportions); a
   visibly mechanical robot is explicitly not an android.
3. representation.text_screenshot: "shows words or code, not a scene"
   fired on book covers, which show both (4 corrections). Narrowed to
   flat captures of words/code with no depicted scene or designed
   surface; a cover, poster, or packaging with a designed surface is
   illustration or photograph.

The two v4 GAPs (incidental humans; interface screenshot with a
depicted subject) stay documented, not revised: n=1 synthetic
evidence each, and the v3/v5 lesson applies.
"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(SCRIPT_DIR, "humanoid_taxonomy_v4.json")
DST = os.path.join(SCRIPT_DIR, "humanoid_taxonomy_v6.json")

with open(SRC, encoding="utf-8") as f:
    tax = json.load(f)

tax["_meta"] = {
    "version": "humanoid_taxonomy_v6",
    "date": "2026-09-24",
    "author": "Mistral Vibe (mistral-vibe)",
    "derived_from": "humanoid_taxonomy_v4",
    "purpose": (
        "Held-out taxonomy revision (LIBRARY.md Phase 6): authored from the "
        "stand-in corpus batch 1 corrections (2026-09-23, 31 corrections in "
        "four families) and measured on batch 2 (2026-09-24, 55 labeled "
        "records), which the revision never saw. Three changes: sculpted "
        "works added to the depiction media (9 statue corrections answered "
        "no/none on statues of humans); the android boundary sharpened to "
        "require a human-passing appearance (8 corrections over-fired on "
        "mechanical robots); text_screenshot narrowed to flat text captures "
        "so covers with designed surfaces classify by their surface "
        "(4 corrections). Representation otherwise reverts to v2/v4 wording."
    ),
    "design_notes": [
        "One revision per re-run (Phase 6 discipline): authored from batch 1 "
        "signals only; batch 2 is the held-out test set.",
        "The v4 medium enumeration (photographed, drawn, illustrated, "
        "rendered, sketched) omitted sculpted works, so Jev read a statue of "
        "a person as containing no human. 'Sculpted (a statue or figurine)' "
        "is added to contains_human.yes, primary_subject.human, and "
        "primary_subject.none.",
        "The v4 android criteria ('the image or its context identifies them "
        "as artificial') let any robot in a robot context count as an "
        "android. v6 requires a human-passing appearance -- a human face, "
        "skin, and human proportions -- and states that a visibly mechanical "
        "robot, even a humanoid one, is not an android.",
        "v4's text_screenshot ('shows words or code, not a scene') fired on "
        "book covers, which show words AND a designed surface. v6 narrows it "
        "to flat captures of words/code with no depicted scene or designed "
        "surface; a cover, poster, or packaging with a designed surface is "
        "illustration or photograph. This narrows (not broadens) the class, "
        "so it cannot de-hedge errors the way v3 did.",
        "The two v4 GAPs (incidental humans; interface screenshot with a "
        "depicted subject) remain documented, not revised: n=1 synthetic "
        "evidence each, and the v3/v5 lesson applies.",
    ],
}

f = tax["facets"]

f["contains_human"]["criteria"]["yes"] = (
    "The image itself shows one or more humans (people, faces, bodies) in "
    "any medium: photographed, drawn, illustrated, rendered, sculpted (a "
    "statue or figurine), or sketched in a diagram. A character depicted in "
    "a cartoon, card, or illustration is visible and counts. A person merely "
    "mentioned, named, or described in text within the image does not count"
)
f["contains_human"]["criteria"]["no"] = (
    "The image itself shows no humans: no person, face, or body is visible "
    "in any medium (people only mentioned or described in text do not "
    "count). A robot or android, however human-like, is not a human for "
    "this question"
)
f["contains_android"]["criteria"]["yes"] = (
    "The image itself shows one or more androids: artificial beings "
    "manufactured to pass as human -- a human face, skin, and human "
    "proportions, presented as a person. Only what is visible in any medium "
    "counts; beings merely described in text do not count"
)
f["contains_android"]["criteria"]["no"] = (
    "The image itself shows no androids: no artificial being presented as "
    "human-passing. A visibly mechanical robot -- exposed machinery, metal "
    "or plastic skin, glowing or camera eyes -- is not an android, even if "
    "humanoid in shape (beings only mentioned in text do not count)"
)
f["primary_subject"]["criteria"]["human"] = (
    "The main subject the image itself shows, in any medium (photo, "
    "illustration, render, sculpture, diagram), is one or more humans; "
    "humans only mentioned or described in text do not count"
)
f["primary_subject"]["criteria"]["android"] = (
    "The main subject the image itself shows is one or more androids: "
    "artificial beings with a human-passing appearance (human face, skin, "
    "and proportions), not visibly mechanical robots"
)
f["primary_subject"]["criteria"]["none"] = (
    "The image shows no humanoid subject of any kind, in any medium: no "
    "human, robot, or android is visible, whether photographed, drawn, "
    "rendered, or sculpted. Images that are only text, objects, or scenes "
    "without humanoids are 'none' -- a humanoid described in text is not "
    "depicted"
)
f["representation"]["criteria"]["text_screenshot"] = (
    "A flat capture of words or code: the image shows only text -- a "
    "terminal, document, or screen of words -- with no depicted scene and "
    "no designed surface. A book cover, poster, sign, or packaging with a "
    "designed surface is illustration or photograph, not text_screenshot, "
    "even though it carries words"
)

with open(DST, "w", encoding="utf-8") as f_out:
    json.dump(tax, f_out, indent=2, ensure_ascii=False)
print("wrote", DST)
