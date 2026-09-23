# TODO: Image classification with Jev -- next steps

> **NEXT STEP (2026-09-23): A real library collection.** Everything
> else on this list is either done, measured, or blocked on it. The
> pipeline, taxonomy, and review UX are ready. A stand-in now exists
> with a first pipeline pass and a completed review: 149 Wikimedia
> Commons images across 5 categories (`library_standin/`, manifest
> committed as the ground truth), measured 2026-09-23 -- 149/149, 0
> errors, pooled agreement 541/615 (88%) against the category-implied
> labels -- and reviewed 2026-09-23 (60/60 routed records: 32
> confirmed, 28 corrected, pooled 83% on the hard cases). Short of
> the 40/category target because Wikimedia rate-limited the fetch;
> re-run `fetch_library_standin.py` once the block lifts to top up,
> then review the new records. The review's edge cases (non-humanoid
> statues, android boundaries, covers with depicted content)
> highlight the need for a richer ontology -- a future revision,
> measured against the 60 labeled records. See STATUS.md "Next
> steps" item 2.

The current pipeline (`classify_images.py`) is scaffolding: a vision
model describes each image, Jev answers one yes/no question. The goal of
this project is to **increase Jev's contribution** -- to make Jev do
more of the meaningful decision work, not just a thin yes/no on a vision
description.

Items are grouped by priority. Each references the finding that
motivates it.

---

## High priority -- make Jev do real classification work

### 1. Multi-class taxonomy

**Why:** The single yes/no "contains human" question underuses Jev. It
asks Jev to make a trivial binary decision on a description that already
contains the answer. A multi-class taxonomy makes Jev's Choice question
do real work.

**What:** Replace the yes/no criteria with a multi-class set, e.g.
`human / animal / object / text / landscape / other`. Ask Jev to pick
one per image. This is a drop-in change to the `criteria` in
`classify_images.py`; the pipeline logic is unchanged.

**Effort:** Small. The criteria dict changes; the rest of the pipeline
is reusable.

### 2. Hierarchical image ontology

**Why:** The ticket project's core insight is that Jev classifies well
against a *hierarchy* via recursive descent, and its calibrated
probabilities surface where the ontology is incomplete. Images have the
same structure (e.g. `scene -> contains_human -> photo/depiction`), but
the current pipeline is flat.

**What:** Author a small image ontology (2-3 levels, ~8-12 leaves) and
classify each image by recursive descent, exactly like
`mvp_jev_ontology.py`. Track cumulative confidence down the tree. This
is the direct analog of the ticket work and the strongest way to
increase Jev's contribution.

**Effort:** Moderate. Reuse the recursive-descent logic from the ticket
MVP; the ontology authoring and prompt design are the main work.

### 3. Multiple questions in one pass

**Why:** Jev supports several questions in a single call (Choice, Score,
Noul). The current pipeline asks one. Asking several per image -- e.g.
"contains human?", "is it a photo or a depiction?", "is it text?" --
lets Jev return a richer, structured decision in one round trip.

**What:** Extend the Jev call to include multiple questions. Use the
answers together (e.g. `contains_human=yes` AND `is_photo=yes` -> a real
photo of a person; `contains_human=yes` AND `is_depiction=yes` -> an
illustration). This directly addresses the "real human vs. depiction"
boundary that the current single question only flags with low
confidence.

**Update (2026-09-23):** the structured-decision variant ran three
times on the 85 labeled records (`structured_vision.py`, LIBRARY.md
Phase 3): typed vision fields (medium, subjects, text_in_image,
setting, people) composed into the state Jev classifies. v1 (rich
medium vocabulary) regressed on representation (67%) -- vocabulary
mismatch with the taxonomy. v2 (medium aligned to the representation
classes): pooled 90%, representation 76%, burden 22% -- still a
measured negative vs the cascade (91%, 79%, 16/27 caught vs 5/25).
v3 (physical-context clause) was rejected: it fixed 1 record and
broke 7 (representation 69%). Option 1 (an isolated binary
capture-type question with a deterministic medium override,
`capture_type.py`) was also falsified: the question itself answers
`digital_capture` for 37 of 85 records whose truth is a photo,
illustration, or render. The decisive finding: 19 of 20
remaining representation errors have a wrong vision `medium` field,
and no question architecture tried (embedded clause, sharper clause,
isolated binary) can fix that family -- the limitation is
perceptual. The structured state is the diagnostic instrument; the
cascade stays the production path, and review-always routing is the
remaining fix for the ambiguous family.

**Update (2026-09-23, Option 2 adopted):** `routing.py` routes to
review on the 0.7 threshold OR a text-bearing signal in the
description. Measured on the labeled 85: catches 25/27 errors vs
18/27 for the threshold alone. Full-collection burden 135/218 (62%)
after the 2026-09-23 preamble-stripper fix (was 156/218, 72%).
The two remaining silent errors are vision-limited with no text
signal. The trade is explicit and tunable (the pattern is one
constant).

**Effort:** Small. The API supports multiple questions in one body; the
interpretation logic is the new work.

---

## Medium priority -- calibrate, route, and close the loop

### 4. Calibration-driven routing

**Why:** We currently use a fixed 0.7 threshold to flag ambiguous cases.
Jev's confidence is a richer signal than a threshold -- it can drive
routing (auto-classify vs. human review) and prioritization.

**What:** Replace the fixed threshold with a routing policy driven by
Jev's confidence: high confidence -> auto-classify; mid -> queue for
review; low -> escalate. Measure the precision/recall of each band
against a labeled sample.

**Effort:** Small. The routing logic is new; the confidence data already
exists in `image_human_results.json`.

**Update (2026-09-23):** a first routing policy is implemented:
`routing.py` routes to review on the 0.7 threshold OR a text-bearing
description signal (measured: 25/27 errors caught), and the rule is
wired into `sort_humanoids.py` and `review_ui.py`. The preamble
stripper was fixed 2026-09-23 (negation-only stripping, found by the
edge-case suite): same 25/27 catches, burden 156 -> 135 of 218
(72% -> 62%). A multi-band policy (mid -> queue, low -> escalate)
remains open.

### 5. Criteria as the ontology -- close the feedback loop

**Why:** The ticket project's most interesting result is the feedback
loop: Jev's low-confidence signals reveal where the ontology is
incomplete, the LLM revises it, and re-running improves confidence. The
image pipeline has no such loop -- the criteria are fixed.

**What:** Treat the decision criteria as an ontology to be revised.
Collect Jev's low-confidence images and the descriptions that produced
them, feed them to an LLM with instructions to sharpen the criteria
(e.g. split "human" into "photo of a real person" vs. "depiction"),
then re-run. This is the same abduction loop as the ticket work.

**Update (2026-09-23):** the loop ran three times, measured against
50 reviewed records. Adopted: v4 (depiction counts in any medium;
robots need a being-like form) -- contains_human 80% -> 88%.
Rejected: v3 and v5 (representation rewrites) -- both de-hedged
without accuracy gains, converting queue-caught errors into
confident ones. The loop needs the errors-caught-per-burden metric,
not confidence or queue size. Residual representation errors are
vision-limited (see item 3's structured vision state).

**Effort:** Moderate. Needs an LLM call for criteria revision and a
re-run harness.

### 6. Run-to-run variance

**Why:** Every result here is from a single Jev call per image. We do
not know whether Jev is deterministic on image descriptions. If the same
description yields 1.000 on one call and 0.70 on the next, the
confidence thresholds are less meaningful than they appear.

**What:** Pick ~10 images (mix of high-confidence and flagged).
Classify each 10 times against the same criteria. Measure mean and
standard deviation of confidence, and whether the choice ever flips.

**Update (2026-09-23):** a cross-prompt comparison now exists (old
vs. fixed vision prompt: 204/215 contains_human agreement, queue
79 -> 52), but that changes two variables at once. Same-prompt,
same-description variance is still unmeasured.

**Effort:** Small. A loop over the existing `jev_classify` function.

### 7. Ground truth and accuracy

**Why:** We have no ground truth. The 73/142 split is Jev's judgment,
not a verified answer. Accuracy is unmeasured, so we cannot say whether
the pipeline is right, only that it is confident.

**What:** Manually label a sample (e.g. 50 images, oversampling the
low-confidence ones). Compare Jev's choice to the label. Report
accuracy, and per-confidence-bin accuracy (calibration).

**Update (2026-09-23):** `review_ui.py` records every confirm/correct
as a `manual_correction` block, so a review pass of the queue
accumulates labels directly in the results file -- the labeled set
Phase 5 (LIBRARY.md) describes.

**Effort:** Small once labels exist; the labeling is the main work.

---

## Lower priority -- broaden and harden

### 8. Baseline comparison

**Why:** We have no baseline. The right comparison is "Jev + vision
description vs. the cheapest acceptable image classifier" -- e.g. a
CLIP-based zero-shot model, a face detector, or the vision model asked
directly.

**What:** Run the same images through a CLIP zero-shot classifier and/or
a face detector. Compare accuracy (once ground truth exists), cost, and
latency.

**Update (2026-09-23):** Phase 2 complete on the 85 labeled records.
`baseline_compare.py` measures accuracy, ECE, flag rate at 0.7, and
errors caught per system. Keyword baseline (trivial, always
confident): 78% pooled accuracy, ECE 0.166, 0/49 errors caught.
Pixtral-direct: 80%, ECE 0.150, 0/45 caught -- it reports >= 0.9
confidence on everything despite being wrong a fifth of the time.
Cascade (Pixtral+Jev): 91%, ECE 0.038, 16/27 caught. The cascade
wins on every measure; Jev supplies the calibrated probability that
makes routing possible. A CLIP-style pixel-level baseline remains
unmeasured.

**Effort:** Moderate. Needs a baseline model and ground-truth labels.

### 9. Adversarial and edge cases

**Why:** One image showed a real failure mode: a screenshot
of text describing a person was classified as containing a person,
because the vision model transcribed the text as if it were a scene.
Other edge cases: memes, AI-generated images, collages, images with
people in the background, text-heavy screenshots.

**What:** Build a small suite of these edge cases. Measure how often the
pipeline misclassifies them, and whether the multi-question approach
(item 3) catches them (e.g. `is_text=yes` would flag the screenshot).

**Update (2026-09-23):** fixed in two layers. The vision prompt now
checks for text first and states the medium, and
`humanoid_taxonomy_v2.json` adds a depicted-vs-described clause to
the entity facets. The known failure image is now correct raw on all
five facets. The suite now exists and is measured:
`generate_edge_cases.py` generated 8 images (0 errors, 7,217 tokens
+ 8 generations, API credits) and `measure_edge_cases.py` ran the
production path on all 8: pooled agreement 33/36 (92%) on
unambiguous facets. The described-scene failure reappeared but
hedged into the queue (caught at 0.050 confidence); the one silent
error is the AI-generated portrait called `photograph` at 1.000 --
perceptual, and the taxonomy has no AI-generated class. The suite
also exposed a routing preamble-stripper brittleness (AGENTS.md
gotchas) and two taxonomy gaps (incidental humans; UI with a
depicted subject).

**Effort:** Small. Assembling the suite is the main work.

### 10. Jev's Score and Noul primitives

**Why:** The pipeline uses only Jev's Choice primitive. Jev also has
Score (rate on a 2-10 scale) and Noul (yes/no probability). These could
help: Noul as a pre-filter ("is this image relevant to the 'human'
branch?"), Score as a continuous fit measure.

**What:** Build a variant that uses Noul as a pre-filter and Score as a
confidence supplement. Compare to the Choice-only pipeline.

**Effort:** Small. The API supports all three in a single call.

### 11. Larger dataset and different domains

**Why:** The pipeline ran on 215 images from one folder. Scaling to a
larger, more varied collection (and different domains, e.g. medical or
satellite imagery) would test whether the approach generalizes.

**What:** Run the pipeline on a larger or different image set. Compare
confidence distributions and flag rates.

**Effort:** Small if a dataset is available; the pipeline works as-is.

---

## Summary

| # | Item | Priority | Effort | Motivated by |
|---|---|---|---|---|
| 1 | Multi-class taxonomy | High | Small | Single yes/no underuses Jev |
| 2 | Hierarchical image ontology | High | Moderate | Flat pipeline; ticket analog |
| 3 | Multiple questions in one pass | High | Small | Richer decision per image |
| 4 | Calibration-driven routing | Medium | Small | Fixed threshold is crude |
| 5 | Criteria as ontology / feedback loop | Medium | Moderate | No loop; ticket analog |
| 6 | Run-to-run variance | Medium | Small | Unknown determinism |
| 7 | Ground truth and accuracy | Medium | Small | No ground truth |
| 8 | Baseline comparison | Low | Moderate | No baseline |
| 9 | Adversarial and edge cases | Low | Small | Screenshot-of-text failure |
| 10 | Jev's Score and Noul primitives | Low | Small | Only Choice tested |
| 11 | Larger dataset and different domains | Low | Small | Single folder tested |
