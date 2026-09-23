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

## First accuracy numbers: the complete review queue (2026-09-23)

A full review pass via `review_ui.py` labeled all 50 queued records
(28 confirmed, 22 corrected) -- the first ground truth this project
has. The queue is every record hedging below 0.7 on any facet, so
these numbers describe the dubious band; the 168 confident records
remain unverified and the threshold's miss rate is unknown.

Per-facet accuracy (raw Jev choice vs. the reviewed label):

| Facet | Accuracy |
|---|---|
| contains_human | 40/50 (80%) |
| contains_robot | 46/50 (92%) |
| contains_android | 49/50 (98%) |
| primary_subject | 43/50 (86%) |
| representation | 40/50 (80%) |

All five facets right on 28/50 records. Pooled facet-answers by
confidence bin -- accuracy rises monotonically with confidence, and
the top band lands on its stated probability:

| Confidence | Accuracy |
|---|---|
| 0.0-0.5 | 18/25 (72%) |
| 0.5-0.7 | 27/41 (66%) |
| 0.7-0.9 | 15/17 (88%) |
| 0.9-1.0 | 158/167 (95%) |

The routing claim holds across the whole queue: every wrong record
(22/22) was in the queue; zero errors were found above the 0.7
threshold. At 0.7, hedging and error coincide -- the threshold
routes exactly the records that need eyes.

The 22 corrections sharpen the taxonomy agenda: game screens
corrected to `text_screenshot` (the missing interface class),
illustrations of text-labeled characters corrected back to `human`
(the v2 depicted-vs-described clause overcorrected there --
depicted-in-illustration must still count), and robot overcalls
corrected to `none`.

---

## Taxonomy revision series: v3, v4, v5 (2026-09-23)

After the 50-record review, three revisions were drafted from the 22
corrections, each run separately and measured on the reviewed records
(one revision per re-run):

| Run | Revision | Wrong /50 | Queue | Errors caught | Confident errors |
|---|---|---|---|---|---|
| v2 (baseline) | -- | 22 | 50 (22%) | 22/22 | 0 |
| v3 | broaden text_screenshot to game/app screens | 21 | 32 (14%) | 16/21 | 5 |
| v4 | depiction counts in any medium; robots need a being-like form | **19** | 44 (20%) | 17/19 | 2 |
| v5 | screenshots classify by their content | 19 | 31 (14%) | 13/19 | 6 |

Findings:

1. **v4 is adopted.** Entity accuracy clearly improved
   (contains_human 80% -> 88%, contains_robot 92% -> 94% on the
   labeled 50) at a small routing cost: two confident errors, both
   on records whose descriptions mislead.
2. **v3 and v5 are rejected negative results.** Both cut the
   review burden while leaving accuracy flat -- the revisions
   converted hedged errors into confident ones. In a routing
   workflow, confidence must be earned by correctness: de-hedging
   without improving accuracy manufactures silent errors. LIBRARY.md
   Phase 6's revision caution is now demonstrated twice, in-sample,
   on labeled data.
3. **The residual representation errors are largely vision-limited.**
   Descriptions that open "This image consists of text" for what
   are photographs of covers leave Jev no correct basis to answer.
   The durable fix is Phase 3's structured vision state, not more
   criteria words.

The live results are the v4 run with all 50 review corrections
merged back; `pilot_humanoid.py` defaults to v4. All runs are
preserved privately outside the repo.

---

## Confident-band verification (2026-09-23)

A stratified 30-record sample of the confident band (every facet
>= 0.7, previously unreviewed) was labeled through the review UI's
Sample filter -- 15 records from 0.7-0.9, 15 from 0.9-1.0, spread
across representation classes.

**Record-level miss rate: 7/30 (23%), Wilson 95% CI 12-41%.** On its
face that is high -- but the errors are almost entirely
`representation` (6 of 7 records; the seventh, an entity error, sat
exactly at the 0.70 boundary):

| Facet | Confident-band accuracy |
|---|---|
| contains_human | 29/30 (97%) |
| contains_robot | 30/30 (100%) |
| contains_android | 30/30 (100%) |
| primary_subject | 29/30 (97%) |
| representation | 24/30 (80%) |

Entity-only miss rate: 1/30 (3%). Pooled calibration in the band:
0.7-0.9: 88%; 0.9-1.0: 95% -- matching the queue's numbers, so
Jev's confidence is genuinely calibrated for the entity facets.

The `representation` finding is the sharpest of the project: its
confident-band accuracy (80%) equals its queue accuracy (80%).
Whether Jev hedges or asserts, `representation` is wrong a fifth of
the time -- its confidence carries no information, and the errors
are the same class everywhere (interface, app, and game screens
forced into the wrong bucket). This is not a criteria problem; the
facet needs either a review-always policy or LIBRARY.md Phase 3's
structured vision state (a typed `medium` field from the vision
model instead of a five-way choice on a free-text description).

**The two-sided routing verdict:** at threshold 0.7, the queue
catches entity errors (17/19 in the v4 run), the confident band's
entity miss rate is ~3%, and `representation` should never be
auto-accepted at any confidence. Total labeled records: 85 of 218.

---

## Phase 2 baseline: the cascade vs. a trivial classifier (2026-09-23)

LIBRARY.md Phase 2 asks whether Jev adds anything over the vision
model alone, and whether either is worth it over a trivial baseline.
Three systems were run against the 85 reviewed records (ground truth
= the manual_correction labels):

1. **Keyword baseline** (`baseline_compare.py`): deterministic
   keyword rules on the same Pixtral descriptions, always fully
   confident -- a trivial classifier with no calibration by
   construction.
2. **Cascade** (Pixtral description + Jev): the production path;
   raw Jev answers from the v4 run.
3. **Pixtral asked directly** (`baseline_pixtral_direct.py`): the
   vision model classifies the five facets itself, same v4 criteria,
   with a calibrated-confidence instruction. 85/85 records, 0 API
   errors (an earlier attempt failed with HTTP 402 Payment Required
   until the account was topped up).

Head-to-head on the 85 labeled records:

| System | Pooled accuracy | ECE | Wrong records | Caught at 0.7 | Silent errors |
|---|---|---|---|---|---|
| Keyword baseline | 78% | 0.166 | 49 | 0/49 | 49 |
| Cascade (Pixtral+Jev) | **91%** | **0.038** | 27 | 16/27 | 11 |
| Pixtral asked directly | 80% | 0.150 | 45 | 0/45 | 45 |

Per-facet accuracy:

| Facet | Keyword | Cascade | Pixtral-direct |
|---|---|---|---|
| contains_human | 67/85 (79%) | 78/85 (92%) | 72/85 (85%) |
| contains_robot | 78/85 (92%) | 82/85 (96%) | 71/85 (84%) |
| contains_android | 85/85 (100%) | 84/85 (99%) | 79/85 (93%) |
| primary_subject | 61/85 (72%) | 77/85 (91%) | 64/85 (75%) |
| representation | 42/85 (49%) | 67/85 (79%) | 54/85 (64%) |

Cascade accuracy by confidence bin (both other systems have one bin,
0.9-1.0, at 78% and 80% -- their confidence carries no information):

| Confidence | Accuracy |
|---|---|
| 0.0-0.5 | 13/20 (65%) |
| 0.5-0.7 | 24/35 (69%) |
| 0.7-0.9 | 41/47 (87%) |
| 0.9-1.0 | 310/323 (96%) |

Findings:

1. **The cascade wins on every measure that matters.** +11 points
   pooled accuracy over Pixtral-direct, 4x lower calibration error,
   and it is the only system whose 0.7 threshold catches errors
   (16/27). Both alternatives answer everything at 0.9+ confidence,
   so all 45-49 of their wrong records are silent.
2. **Pixtral-direct ignores the calibration instruction.** Asked for
   calibrated probabilities, it reports >= 0.9 on all 425 facet
   answers while being wrong 20% of the time. Jev's confidence is
   the scarce resource in this pipeline: the vision model supplies
   perception, Jev supplies the probability that makes routing
   possible.
3. **The keyword baseline is a real floor, not a straw man.** It
   matches the cascade on easy facets (contains_android 100% vs 99%)
   because the descriptions already contain the answer -- but it
   collapses where descriptions are ambiguous (representation 49%,
   primary_subject 72%). The comparison is also conservative toward
   it: the keyword rules run on Pixtral's descriptions, inheriting
   the vision model's work for free.
4. **The burden number needs care.** On the labeled subset the
   cascade flags 52% -- but that subset is queue-heavy by
   construction (50 of 85 are queue records). The collection-wide
   burden remains 50/218 (23%).

---

## Phase 3: structured vision state (2026-09-23)

LIBRARY.md Phase 3 replaces the free 25-word description with typed
fields per image (medium, subjects, text_in_image, setting, people);
Jev classifies the composed state, with transcribed text explicitly
labeled as quoted content. Two iterations, each run on the 85 labeled
records (`structured_vision.py`; runs preserved privately in
`2026-09-23_structured_v1_run/`):

| System | Pooled accuracy | ECE | representation | Burden at 0.7 | Wrong | Caught | Silent |
|---|---|---|---|---|---|---|---|
| Cascade (production) | 91% | 0.038 | 79% | 52% | 27 | 16/27 | 11 |
| Structured v1 (rich medium: poster, diagram, render) | 88% | 0.047 | 67% | 22% | 34 | 11/34 | 23 |
| Structured v2 (medium aligned to the representation classes) | 90% | 0.048 | 76% | 22% | 25 | 5/25 | 20 |

Findings:

1. **v1's regression was vocabulary mismatch.** The medium field
   answered `poster` and `diagram`, which are not representation
   classes -- Jev had to guess (a poster of a photograph became an
   illustration). Aligning `medium` exactly with the representation
   taxonomy recovered most of the loss (representation 67% -> 76%).
2. **The bottleneck moved into the vision field extraction.** Of the
   20 remaining representation errors in v2, 19 have a wrong
   `medium` field -- Jev inherits the error from a state that is
   already wrong. The photographed-cover family (a real photo of a
   cover described as `screenshot_of_text`) and the deepseek
   described-scene trap (subjects filled from text the image merely
   mentions) both live in the vision model, not in Jev.
3. **The screenshot-of-text failure mode is eliminated where the
   medium field is right.** Every image the vision model correctly
   labels `text_screenshot` classifies as `text_screenshot` at 1.0
   confidence -- the incident that motivated Phase 3 cannot recur on
   a correctly-extracted state.
4. **On the errors-caught-per-burden metric, the structured state is
   still a measured negative against the cascade**: it flags less
   (22% vs 52% on this subset) but converts more errors into
   confident ones (20 silent vs 11). The cascade remains the
   production path.
5. **The structured state is the right diagnostic instrument.** It
   separates vision errors from Jev errors cleanly: Jev is now
   nearly perfect on the state it is given. The next representation
   fix is a vision-prompt fix (the photographed-cover family), not a
   Jev-criteria fix.

Engineering notes: Pixtral emits raw newlines and unescaped quotes
inside transcribed text -- the parser needs `strict=False` and a
regex repair fallback; `max_tokens` 300 truncated long transcriptions
(raised to 700).

---

## What is unproven

1. **Ground truth covers 85 of 218 records (39%).** All 50 queued
   records plus a 30-record stratified sample of the confident band
   are labeled -- the first two-sided view of the routing threshold.
   The verdict: entity facets are well-calibrated (queue catches
   their errors; confident-band entity miss ~3%), but
   `representation` is ~80% accurate at every confidence level and
   should never be auto-accepted. The remaining 133 confident
   records are unlabeled; extrapolating the sample, roughly 31
   carry a wrong facet, almost all `representation`.
2. **The vision model is the bottleneck.** Jev only sees the 25-word
   description. If Pixtral mis-describes an image (e.g., misses a person
   in the background, or describes a statue as a person), Jev inherits
   the error. The description is lossy by design.
3. **"Human" is a fuzzy label.** The low-confidence cases show the
   boundary is genuinely ambiguous (statue vs. person, cartoon vs.
   photo). The criteria could be tightened (e.g., "a real, living human
   in a photograph") or split into sub-labels (photo / illustration /
   statue).
4. **The baseline comparison is complete on this collection.** All
   three systems are measured (above): the cascade beats both the
   keyword baseline and Pixtral-direct on accuracy, calibration, and
   errors caught. Still unmeasured: a CLIP-style pixel-level
   baseline, and the comparison on a real library collection.

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
