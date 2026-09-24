# Library Image Classification: Project Plan

**Date:** 2026-09-22
**Status:** plan, not results
**Goal (from README):** a pipeline that auto-classifies digitized
image collections against a revisable taxonomy, routing uncertain
items to human review.

This document turns the library use-case into a concrete project. It
is grounded in what the `Images/` sub-project has already
demonstrated -- and in what it has already shown does **not** work.

---

## The setting

A university library holds digitized image collections: photographs,
posters, illustrations, scanned book pages, archival material.
Cataloging them by subject is manual, slow, and backlogged. The
proposal: describe each image with a vision model, then classify the
description against a taxonomic scheme with Jev, whose calibrated
probabilities decide what a human must review.

The library context changes the requirements relative to the
"contains a human" demo:

- The taxonomy is **larger and multi-faceted** (subject, genre,
  medium, depicted entities), not a single yes/no question.
- **Ground truth exists**: catalogers can label a sample, so
  accuracy and calibration can actually be measured.
- The output feeds a **catalog workflow**, so review routing matters
  more than raw accuracy.
- Collections contain **personal and sensitive material**, so the
  privacy practices of this repo are the starting point, not an
  afterthought.

---

## What the demo already established

From the 215-image run (`RESULTS.md`):

1. **The cascade works end to end.** Pixtral describes, Jev decides,
   0 errors across 215 images at negligible cost.
2. **Calibration is the value.** The 13 sub-0.7-confidence cases
   were all depictions (statues, cartoons, posters) -- exactly the
   items a cataloger would want to see. Jev did not force them.
3. **Criteria are data.** The decision rule was passed as state;
   tightening "human" to "a real, living human in a photograph"
   requires no retraining, just a new ontology JSON.

## What it also established (the negative results)

Do not build the library project on assumptions this repo has
already falsified:

1. **The feedback loop does not generalize (yet).** On held-out
   items, ontology revision improved mean confidence by +0.004 --
   inside Jev's run-to-run noise floor (spread 0.0045). Revision
   driven by classification signals fits the training batch; treat
   "Jev improves the taxonomy" as unproven until a held-out test
   says otherwise.
2. **The vision model is the bottleneck.** Jev only sees a 25-word
   description. It inherited a real failure: a screenshot of *text
   describing* a photo was classified as containing a human. In a
   library collection full of scanned text pages, this failure mode
   is common, not exceptional.
3. **Calibration is asserted, not measured.** No ground truth was
   collected in the demo. A library project must measure it before
   trusting confidence thresholds for routing.

---

## Phase 0 -- Scope and ground truth (before any modeling)

**What:** Pick one collection (200-500 images) with a cataloger who
can label a stratified sample: ~50 random images, plus deliberately
hard ones (depictions, text-heavy scans, compound images). Label the
top-level facets only. Record inter-annotator agreement if two
catalogers are available -- it sets the ceiling for what "accuracy"
can mean. Until library material exists, two stand-ins are in place:
the generated edge-case suite (`generate_edge_cases.py`, 8 images
covering the measured failure families; measured 2026-09-23, pooled
agreement 33/36) and a 240-image Wikimedia Commons corpus
(`fetch_library_standin.py`, all 6 categories with a committed
manifest as ground truth; topped up 2026-09-23 after the first fetch
was rate-limited, and completed at 40 per category on 2026-09-24;
measured 2026-09-23 by
`measure_library_standin.py` under v4, 231/231, 0 errors, pooled
agreement 794/929 (85%) against the category-implied labels, then
fully re-run with v7 on 2026-09-24 (240/240, 0 errors, pooled
857/960 = 89%, routing burden 44%); routed records reviewed
2026-09-23 and 2026-09-24 (60/60 then
55/55: 75 confirmed, 61 corrected, pooled 55% on the hard cases) --
the corpus now has all 240 records labeled (four review passes: 60/60
and 55/55 under v4, 12/12 under v7, then the 72 remaining auto-accepted records confirmed under v7; corrections merged into the
v7 results), and its edge cases
(non-humanoid statues, android boundaries, covers with depicted
content, finer representation splits) are the input for a future
taxonomy revision; depicts annotation is a dead end -- 0/231 files
carry P180 statements). The Commons corpus is the closer analog
to real library material: digitized covers, statues, and
illustrations with structured depicts annotations.

**Why first:** every later decision (thresholds, taxonomy size,
baseline comparison) needs a labeled sample. Without it the project
repeats the demo's biggest caveat.

**Success:** a `library_ground_truth.json` (private, gitignored) with
image id, facet labels, and annotator notes.

---

## Phase 1 -- Taxonomy as ontology

**What:** Encode the target scheme as `taxonomy_v1.json` in the
same shape as `ontology.json` (id, label, definition, children,
`_meta` with version). Prefer an existing controlled vocabulary over
a novel one:

- **Thesaurus for Graphic Materials (TGM)** -- free, from the
  Library of Congress, built for exactly this material.
- **Iconclass** -- for art and cultural imagery; check licensing
  terms before use.
- A **local scheme** if the collection has one -- the pipeline does
  not care, and definitions can be LLM-drafted and cataloger-approved.

Start small: 2 levels, 20-50 nodes, one facet (e.g., genre, or
"depicted subject"). Jev's Choice supports up to 255 options per
question, but wide nodes invite hedging; the ticket work showed
sharp sibling definitions are what make Jev commit.

**Why:** this is the exact pattern already proven: LLM authors the
ontology, Jev classifies against it, the taxonomy is swappable data.

**Success:** definitions specific enough that a cataloger reading
two siblings can say which items belong where. The demo's
"WrongfulCharge" fix is the model: one definition change eliminated
hedging on three tickets.

---

## Phase 2 -- Baseline and honest measurement

**What:** Run the sample through three systems and compare against
ground truth:

| System | Purpose |
|---|---|
| Pixtral asked directly ("classify into X/Y/Z") | Is Jev adding anything over the vision model alone? |
| Pixtral + Jev (the cascade) | The candidate production path |
| Keyword/CLIP-style zero-shot classifier | Is either worth it over a trivial baseline? |

Metrics: accuracy, calibration error (ECE binned by confidence),
flag rate at candidate thresholds, and **review burden** -- the
percentage of the collection routed to a human. In a library, "95%
accuracy at 40% review burden" and "85% at 10% burden" are different
proposals; the cataloger decides which trade is acceptable.

**Why:** the demo has no baseline and no ground truth. This phase
removes both objections, and it answers the "Jev is an extra hop"
question with data instead of argument.

**Success:** a written comparison the library can act on, with the
review-burden/accuracy trade-off explicit.

---

## Phase 3 -- Fix the vision state

**What:** Replace the free 25-word description with a structured
one, per image:

```
medium: photograph | illustration | scan of text | poster ...
subjects: (what is depicted, as a short list)
text_in_image: any legible text, transcribed
setting: indoor | outdoor | studio | archival page ...
people: none | individuals | group (no identities)
```

Prompting Pixtral for typed fields directly attacks the known
failure mode: a scan of text gets `medium: scan of text`, and the
classifier never mistakes a description of a photo for the photo.
The DeepSeek-screenshot incident is the exact motivating case.

**Also:** strip OCR-able text from the *state* passed to Jev, or
label it explicitly as quoted content -- Jev treats state as data,
and the demo showed adversarial text can still shift distributions
by a few points.

**Success:** the screenshot-of-text failure mode reproduced on the
labeled sample, then eliminated.

---

## Phase 4 -- Multi-question Jev pass

**What:** One Jev call per image asking several typed questions at
once: genre (Choice), "is this a photograph" (Noul), "confidence
this is a depiction rather than a real scene" (Score or Noul). Jev
answers all questions in a single parallel pass, so this adds
latency-free facets to the record.

**Why:** the single-question demo under-uses Jev. Facets are how a
library record is actually structured, and routing can use any
question's confidence, not just the leaf choice.

**Success:** a per-image record with multiple facets and per-facet
confidence, at the same cost as one question.

---

## Phase 5 -- Review workflow

**What:** A review queue sorted by ascending confidence, with a
simple correction interface. Corrections follow the proven record
pattern: Jev's raw answer is preserved under a `jev` key, the human
override goes in the top-level fields, and nothing is overwritten.
Corrections accumulate as a labeled set -- which feeds Phase 2's
ground truth over time.

**Update (2026-09-23):** `review_ui.py` implements this phase's first
pass on the pilot data: a localhost app with the queue sorted by
ascending confidence, a confirm/correct interface driven by the
taxonomy JSON, and `manual_correction` blocks that accumulate as the
ground-truth seed.

Route on the **review-burden curve** chosen in Phase 2, not on an
arbitrary threshold. Re-check the curve against the noise floor
(~0.005 on 16-item means) before treating small confidence changes
as signal.

**Success:** a cataloger clears the queue faster than manual
cataloging of the same images, and trusts the flag list.

---

## Phase 6 -- Taxonomy revision (carefully)

**What:** Feed review-queue corrections and low-confidence patterns
back into taxonomy revisions -- but evaluate every revision
**held-out**: revise using signals from one batch, measure on a
labeled batch the revision never saw. This is the protocol the
ticket experiments learned the hard way (in-sample +0.013, held-out
+0.004, inside noise).

**Why:** the loop is the project's interesting bet, but it is
currently a classifier-tuning mechanism, not a learning mechanism.
The library setting -- with real ground truth and many batches -- is
actually the best place yet to test whether it can become one.

**Update (2026-09-23):** demonstrated twice in one session, on
labeled data: revisions v3 and v5 (both representation definitions)
cut the review burden while leaving accuracy flat, converting hedged
errors into confident ones -- revisions that fit the batch and broke
the routing property. The adopted revision (v4, entity clause)
raised accuracy. Lesson for the protocol: evaluate revisions on
errors-caught per review burden against labels, never on confidence
or queue size alone. See RESULTS.md ("Taxonomy revision series").

**Update (2026-09-24):** the protocol ran held-out for the first
time: v6 was authored from the stand-in corpus batch 1 corrections
and measured on batch 2 (55 labeled records the revision never saw).
v6's entity changes worked (android 89% -> 100%) but its
text_screenshot narrowing regressed representation 62% -> 49% -- the
v3 lesson in mirror image, and the reason the protocol exists: the
regression was invisible at authoring time. The composed v7 (entity
changes kept, representation reverted to v4) beat v4 held-out: pooled
89% vs 85%, fixes 10 / breaks 2 (sign test ~p=0.04), routing
property intact (21/22 caught). This is the first revision that
beats its held-out batch -- at the edge of the noise floor,
suggestive rather than decisive, but the loop has now produced one
held-out-validated revision. See RESULTS.md ("Held-out taxonomy
revision").

**Success:** at least one revision that beats its held-out batch
beyond the noise floor. Until then, revisions are cataloger-driven
with LLM assistance, not autonomous.

---

## Risks

| Risk | Mitigation |
|---|---|
| Personal/sensitive imagery goes public via logs | Keep all per-image records private (gitignored, as in this repo); descriptions can carry personal data too |
| Taxonomy licensing (some thesauri are not free) | Prefer TGM or a local scheme; check terms before encoding |
| API lock-in (TypeSafe, Mistral) | The taxonomy and records are plain JSON; the cascade is re-implementable against any vision model + classifier |
| Vision model drift between batches | Version the vision model in each record's `_meta`, like the ontology version |
| Silent degradation of the vision layer | Phase 0's labeled sample is re-scored on any model change |

---

## Suggested order of work

1. Phase 0 (ground truth) -- everything else depends on it
2. Phase 1 (taxonomy_v1, one facet, 2 levels)
3. Phase 2 (three-system comparison on the sample)
4. Phase 3 (structured vision state)
5. Phase 5 (review queue; it can start on Phase 2 output)
6. Phase 4 (multi-question facets)
7. Phase 6 (revision loop, held-out evaluated)

Phases 0-3 are a realistic first milestone: a measured answer to
"can this classify our collection," with a review queue a cataloger
can actually use.

---

## Pilot run (2026-09-22): humanoid taxonomy v1

`humanoid_taxonomy_v1.json` and `pilot_humanoid.py` implement
Phases 1 and 4 on the existing 215 image descriptions: one Jev call
per image carrying five questions (contains_human, contains_robot,
contains_android, primary_subject, representation) in a single
parallel pass. 215 calls, 0 errors, 194,193 input tokens, $0.0082.
Per-image results are private (`humanoid_pilot_results.json`,
gitignored).

Aggregate:

| Facet | Distribution |
|---|---|
| primary_subject | none 131, human 74, robot 7, multiple 3 |
| representation | text/screenshot 66, photograph 60, illustration 54, other 26, statue/render 9 |
| contains_robot | 10 yes / 205 no |
| contains_android | 0 yes / 215 no |

Findings:

1. **Consistency: 215/215.** `contains_human` (same criteria as the
   original run) agreed with the original single-question run on
   every image, including the depiction cases. Two runs, two
   question sets, same answers.
2. **The compound class earns its keep.** All three `multiple`
   images are human+robot scenes -- the exact case a single-label
   taxonomy forces a wrong answer on.
3. **Representation is the noisy facet.** 64 of the 79 review-queue
   entries come from `representation` hedging, not from entity
   questions. A five-way choice with subtle boundaries (screenshot
   vs. interface vs. illustration) hedges more than yes/no
   questions. Before deployment: sharpen those definitions, or
   accept that representation drives the review burden.
4. **The android criteria may be too strict.** 0/215, with two
   images hedging hard on the question. Either the collection has
   no androids (plausible) or the "identified as artificial in
   context" requirement reads stricter than intended. Phase 0
   ground truth would settle it.
5. **Review burden at threshold 0.7: 79/215 (37%).** Higher than
   the original single-question run's 13 flagged, as expected --
   five questions means five chances to hedge, and the queue takes
   the minimum. The burden-vs-threshold trade-off is exactly what
   Phase 2 is designed to measure.

The pilot validates the taxonomy-as-data pattern and the
multi-question single-call pattern at library scale. What it does
not do is measure accuracy: the 215 images still have no ground
truth. Phase 0 remains the next dependency.

### Addendum (2026-09-23): re-run with the fixed vision prompt

A second screenshot-of-text false positive (text describing "a man
and a robot," classified as a promotional photograph at 1.0
confidence) led to a vision-prompt fix -- Pixtral now checks for
text first and states the medium -- and a full re-run on the
collection, now 218 images:

- Review queue 52/218 (24%), down from 79/215 (37%);
  `representation` hedges 28, down from 64.
- The failure image is now `text_screenshot` at the raw level, but
  Jev still answers the *described* scene for `primary_subject`
  (multiple, 0.91). The criteria need a "depicted vs. described"
  clause; Phase 3's structured vision state remains the durable
  fix for this class of error.
- Android: 2 raw yes in the re-run (one is the corrected failure
  record); the facet is still awaiting ground truth.

The old-prompt baseline is preserved privately outside the repo.
Phase 0 ground truth is still the dependency.

Later the same day, `humanoid_taxonomy_v2.json` added the
depicted-vs-described clause to every entity facet (only what the
image itself shows counts; entities described in text do not).
Re-run on the same 218 descriptions: the failure image is correct
raw on all five facets, queue 50/218 (23%). This is the first
criteria revision driven by review-queue signals -- in-sample only;
Phase 6's held-out protocol is the standard for future revisions.
