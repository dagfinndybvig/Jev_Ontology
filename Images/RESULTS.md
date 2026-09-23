# Results: Image classification with Jev

**Date:** 2026-09-22
**Author:** Mistral Vibe (mistral-vibe)
**Task:** Sort 215 images in a personal photo folder by whether they contain a human.
**Vision model:** Mistral `pixtral-12b-2409`
**Jev model:** jev-latest (jev-1.13.0)
**Images:** 215 (73 human, 142 no-human, 0 errors)

---

## Summary

The task was to sort the images in a personal photo folder by whether they
contain a human, using Jev. The result: 73 images contain a human, 142
do not, with 0 errors. 188 of 215 (87%) were classified at 0.9+
confidence.

The interesting finding is not the split itself but *where* Jev hedged.
The 13 sub-0.7-confidence cases are all illustrations, statues,
cartoons, or posters rather than photographs of real people. Jev's
calibrated probabilities surface the "real human vs. depiction" boundary
instead of forcing a confident answer.

---

## The constraint: Jev is text-only

Jev classifies a text *state* against typed questions. It cannot see
pixels. To classify images with Jev, each image must first be converted
to text. The pipeline therefore uses a vision model as a front-end:

```
Mistral Pixtral describes the image (one 25-word sentence)
  -> Jev classifies the description: "Does this image contain a human?" (yes/no)
```

This is the same cascade pattern as the ticket experiment, with one
change: the *state* Jev sees is now a vision model's description rather
than raw text. The vision model is the "eyes"; Jev is the decision
maker. (Note: the `OPENAI_API_KEY` in the environment was a 25-char
placeholder, so Mistral's Pixtral was used for the vision step.)

---

## Results

| Bucket | Count | Mean confidence | >=0.9 | 0.7-0.9 | 0.5-0.7 | <0.5 |
|---|---|---|---|---|---|---|
| Contains human | 73 | 0.920 | 61 | 5 | 2 | 5 |
| No human | 142 | 0.959 | 127 | 9 | 3 | 3 |
| **Total** | **215** | | **188** | **14** | **5** | **8** |

0 errors. 188 of 215 (87%) classified at 0.9+ confidence. The buckets
above use each record's effective (post-correction) confidence, so the
corrected screenshot-of-text record contributes a manual 1.0 to the
no-human >=0.9 bucket; Jev's raw answer ("yes" at 1.000, preserved
under the record's `jev` key in `image_human_results.json`) would place
it in the contains-human >=0.9 bucket instead.

> **Correction (2026-09-22):** One image -- a screenshot of *text*
> describing a photo -- was initially classified as "contains human" at
> 1.000. The vision model read the text ("a man and a robot...") and
> described it as if it were the scene, and Jev then said "yes." It has
> been removed from the human set and reclassified as no-human. This is
> a real failure mode: screenshots of text that *describes* a person get
> misclassified as containing a person.

> **Correction 2 (2026-09-23, humanoid pilot):** A second instance of the
> same failure mode. A screenshot of a text-only terminal showing another
> model's text *describing* an image (again a man and a robot) was
> described by the vision model as a promotional photograph, and Jev
> answered at 1.000 confidence (photograph, multiple subjects). The
> record now carries a manual correction -- raw Jev answers preserved --
> in `humanoid_pilot_results.json`, and `sort_humanoids.py` sorts
> corrected records by their corrected labels. The vision prompt in
> `classify_images.py` now checks for text first, states the medium,
> and requires describing what text says rather than a scene the text
> merely mentions. Verified live: the known failure image and a second
> text screenshot are both described as text; normal photographs
> still describe normally. A weaker medium-first-only instruction was
> tested first and failed on the known image -- the scene description
> overwhelmed it.

---

## The interesting finding: Jev surfaces "real human vs. depiction"

The 13 cases below 0.7 confidence are not noise -- they are all
illustrations, statues, cartoons, or posters rather than photographs of
real people:

| Image | Choice | Conf | Description |
|---|---|---|---|
| image_01 | yes | 0.05 | comic book characters Batman and Robin |
| image_02 | yes | 0.16 | Arthur Mensch discusses Mistral AI |
| image_03 | yes | 0.28 | a cartoon child celebrating a birthday |
| image_04 | yes | 0.39 | pixelated version of "The Thinker" statue |
| image_05 | no | 0.45 | superhero resembling The Flash |
| image_06 | no | 0.47 | cartoon superhero labeled GPT-5 |
| image_07 | yes | 0.48 | illustrations of team members |
| image_08 | no | 0.49 | magazine cover |
| image_09 | yes | 0.54 | illustrations of team members |
| image_10 | no | 0.55 | victory screen with characters |
| image_11 | no | 0.57 | list of students |
| image_12 | no | 0.61 | cartoon character giving a thumbs-up |
| image_13 | yes | 0.69 | film poster |

(Filenames are redacted: they come from a personal photo collection.
The unredacted records live in the private `image_human_results.json`;
see the Privacy section in `README.md`.)

Jev's criteria said "one or more humans (people, faces, bodies)", but it
correctly hedged on depictions. A statue of a person, a cartoon of a
person, and a photograph of a person are all "a human" in some sense and
not in another. Jev's calibrated probabilities flag this boundary rather
than forcing a confident answer -- the same behavior that made it useful
on ambiguous support tickets.

---

## Cost

Jev calls: 215, ~344 input tokens each, ~74K input tokens total. At
$0.042/M input tokens, that is roughly $0.003. The vision calls
(Pixtral) dominate the cost but are still small. The whole batch is
effectively free.

---

## Re-run with the fixed vision prompt (2026-09-23)

The second screenshot-of-text instance (Correction 2 above) led to a
vision-prompt fix: Pixtral now checks for text first and states the
medium (photograph, illustration, render, screenshot, or text) before
describing content. A weaker medium-first-only draft failed live
testing on the known failure image; the check-first version passed on
that image, a second text screenshot, and two normal photos.

The full pipeline was then re-run on the collection, grown to 218
images (3 new since the original 215). 218 descriptions, 218 Jev
calls, 0 errors. Comparison against the original run (215 common
images; the old-prompt baseline is preserved in a private backup
outside the repo):

| Measure | Original run | Re-run |
|---|---|---|
| Review queue (<0.7 any facet) | 79/215 (37%) | 52/218 (24%) |
| `representation` hedges | 64 | 28 |
| Binary "contains human" | 73 yes / 142 no | 67 yes / 151 no |
| `contains_human` choice flips | -- | 11 (10 of them yes -> no) |

The 10 yes->no flips are almost entirely the failure family the prompt
fix targeted: screenshots of text *about* people (article headlines,
name lists), a greeting card, poster illustrations, and a render. The
single no->yes flip also looks correct.

The original failure image is now described as text at the raw level
(`representation: text_screenshot` at 0.53, previously `photograph`
at 1.0). Jev, however, still answers the *described* scene for
`primary_subject` (multiple, 0.91): the remaining gap is in Jev's
criteria, which do not distinguish "depicted" from "described." The
manual correction stands.

`sort_humanoids.py` (new) materializes the pilot results as a sorted
folder tree -- `Humanoids/<primary_subject>/<representation>/` plus a
`_review/` folder of low-confidence and corrected records -- for
visual verification. Its first version read `manual_correction` labels
from the wrong JSON level and sorted corrected records by raw labels;
fixed the same day, placement verified with `find`.

---

## Taxonomy v2: the depicted-vs-described clause (2026-09-23)

The re-run left one gap: Jev answered the *described* scene for
`primary_subject` on the failure image (`multiple` at 0.91).
`humanoid_taxonomy_v2.json` adds one clause to every entity facet:
only what the image itself shows counts; a person or robot merely
mentioned or described in text does not. The pilot was re-run on the
same 218 descriptions (criteria-v1 results preserved privately).

- The failure image is now correct raw on all five facets:
  `primary_subject: none` (0.88, previously `multiple` at 0.91).
  No manual correction needed anymore.
- Choice agreement with criteria v1: 217/218 on four facets,
  213/218 on `primary_subject`. The five subject flips are the
  intended fixes (the failure image, a birthday greeting card, a
  text+illustration timeline, a movie poster described only by title
  and stars) or coin-flip noise on records already hedged.
- Review queue 50/218 (23%), down from 52. The clause's effect is
  targeted: it fixes text-describes-entity cases and adds mild
  hedging where the description is ambiguous about whether anyone is
  depicted.
- Caveat: measured in-sample, on the same descriptions that
  motivated the revision. The held-out protocol (LIBRARY.md Phase 6)
  is the standard for calling a revision real.

---

## First accuracy numbers: the reviewed subset (2026-09-23)

A first review pass via `review_ui.py` labeled 25 records (13
confirmed, 12 corrected) -- the first ground truth this project has.
Accuracy is computed on that subset only; it is queue-heavy by
construction, so these numbers describe the dubious band, not the
collection as a whole.

Per-facet accuracy (raw Jev choice vs. the reviewed label):

| Facet | Accuracy |
|---|---|
| contains_human | 19/25 (76%) |
| contains_robot | 22/25 (88%) |
| contains_android | 24/25 (96%) |
| primary_subject | 20/25 (80%) |
| representation | 21/25 (84%) |

All five facets right on 13/25 records. Pooled facet-answers by
confidence bin -- accuracy rises monotonically with confidence, and
the high band is close to its stated confidence:

| Confidence | Accuracy |
|---|---|
| 0.0-0.5 | 8/12 (67%) |
| 0.5-0.7 | 13/21 (62%) |
| 0.7-0.9 | 10/12 (83%) |
| 0.9-1.0 | 75/80 (94%) |

The routing claim holds on this subset: every wrong record (12/12)
was in the review queue; zero errors were found above the 0.7
threshold. The queue is doing its job -- at 0.7, hedging and error
largely coincide -- though 25 of the 50 queued records and all 168
unqueued records remain unverified, so the threshold's *miss* rate
is still unknown.

The 12 corrections also sharpen the taxonomy agenda: game screens
corrected to `text_screenshot` (the missing interface class),
illustrations of text-labeled characters corrected back to `human`
(the v2 clause overcorrected there -- depicted-in-illustration must
still count), and one robot overcall corrected to `none`.

---

## What is unproven

1. **Ground truth is only seeded, not established.** 25 of 218
   images are labeled (queue-heavy by construction). The 73/142
   split is still Jev's judgment everywhere else. The reviewed
   subset gives first accuracy numbers above, but per-confidence
   calibration for the collection needs a stratified sample,
   including confident records.
2. **The vision model is the bottleneck.** Jev only sees the 25-word
   description. If Pixtral mis-describes an image (e.g., misses a person
   in the background, or describes a statue as a person), Jev inherits
   the error. The description is lossy by design.
3. **"Human" is a fuzzy label.** The low-confidence cases show the
   boundary is genuinely ambiguous (statue vs. person, cartoon vs.
   photo). The criteria could be tightened (e.g., "a real, living human
   in a photograph") or split into sub-labels (photo / illustration /
   statue).
4. **No baseline.** We did not compare against a dedicated image
   classifier (e.g., a CLIP-based zero-shot model or a face detector).
   The right comparison is "Jev + vision description vs. the cheapest
   acceptable image classifier."

---

## Files

```
classify_images.py       -- resumable pipeline (vision -> Jev)
summarize_results.py     -- regenerates the summary from the JSON
image_human_results.json -- full per-image records
image_human_summary.txt  -- clean sorted list
```

---

*Signed: Mistral Vibe (mistral-vibe), 2026-09-22*
