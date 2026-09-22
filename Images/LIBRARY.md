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
can mean.

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
The `deepseek_image.png` incident is the exact motivating case.

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
The library setting -- with real ground truth and many batches --
is actually the best place yet to test whether it can become one.

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
