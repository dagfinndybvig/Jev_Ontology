# TODO: Image classification with Jev -- next steps

**Updated: 2026-10-01.** This remains a research pilot, not a
production-ready cataloging service. Audit repairs are complete; the
open priorities below concern stronger evidence and a controlled deployment
trial, not more in-sample taxonomy tuning.

## Current next actions, in order

- [ ] Scope a real-library pilot: agree collection permissions, external-API
  privacy/licensing requirements, cataloger responsibilities, and acceptance
  criteria before processing new material.
- [ ] Independently re-review a sample of historical labels after the review
  UI fixes. Preserve raw model answers and record disagreements explicitly;
  the repairs did not retroactively validate existing human corrections.
- [ ] Build a representative, independently labeled pilot cohort, including
  text-heavy/screenshots and small or background people. Separate authoring
  from held-out measurement and verify labels before the new evaluation.
- [ ] Measure cataloger time, review burden, auto-accepted errors, and
  whole-image as well as per-facet accuracy. Retain repeated-run outputs and
  report uncertainty; confidence alone is not an acceptance criterion.
- [ ] If a vision change is justified, test it as a separate candidate
  against frozen v9 on held-out material. Do not modify the sealed
  replication corpus or silently replace historical runs.

Optional later experiments: multi-band routing, a pixel-level baseline,
a hierarchical alternative to facets, and Score/Noul primitives. These are
not prerequisites established by the current evidence.

## Audit repairs (2026-10-01, priority order)

- [x] Repository-wide follow-up: reject invalid direct/structured vision
  responses and include Images in safe root-level offline test discovery.
- [x] Check both API keys before corpus runs spend on vision.
- [x] Support reuse of the storage/resume helpers by the root experiments
  without changing image data, taxonomy, or routing.
- [x] Remove reliance on the unverified historical ticket-variance range
  from library planning; retain the actual image evidence and pilot caveats.
- [x] Protect results and human corrections with atomic revision-checked
  writes; fix review defaults, independent flags, and keyboard editing.
- [x] Correct auto-accept analysis, calibration/error-capture metrics,
  and historical baseline comparisons; recompute affected documentation.
- [x] Validate resume identity, enforce sealed manifests, fix fetch quotas,
  and reconcile stale sorted copies.

Each milestone includes offline regression coverage and documentation.
Milestone 2 recomputed retained-run metrics without API calls. The old
structured-v3 run lacks raw results, so its corrected ECE/capture metrics
are marked unavailable rather than reconstructed.
Milestone 3 preserves legacy results, refuses unverifiable resumes, and
provides `--report-only` for historical taxonomy measurements. The
published sealed corpus and all existing human labels remain unchanged.

## Historical planning and measurement record

The dated notes below preserve earlier proposals and results. They are not
the current action queue; use the priorities above and the status table at
the end of this document.

> **Planning update (2026-09-24, supplemented 09-25): New labeled data or a vision-layer
> lever -- the taxonomy loop is at diminishing returns on this
> corpus.** Ground truth is complete: all 240 stand-in records
> labeled (172 confirmed, 68 corrected). The taxonomy loop ran four
> held-out revisions: v7 adopted (89% vs v4's 85%), v8 rejected
> (inside noise), v9 adopted under the split-half protocol (96% vs
> 94%, representation 89% vs 80%; production re-run 240/240, 0
> errors, pooled 898/960 = 94% vs v7's 89%; v9 agrees with all
> human corrections on 1141/1200 facets = 95.1%), and v10 measured
> and rejected (pooled identical to v9 at 96%, fixes 2 / breaks 3,
> criterion-attributable 4 toward / 2 away -- inside noise; the
> residual families are small and the boundary labels noisy). v9 is
> the default taxonomy. The remaining residuals are not authorable
> from the descriptions: the background-people family (6
> contains_human corrections) is a vision-layer limit -- the
> descriptions do not mention the humans, so no criterion edit can
> fire; the statue clause's scene boundary has inconsistent reviewer
> labels. Next: (1) a real library collection (new labeled data for
> the loop), or (2) a vision-layer lever -- e.g. the description
> prompt asking explicitly about small/background people, measured
> against the same ground truth. The pre-registered fresh-corpus
> replication is complete (2026-09-25): the frozen v9 pipeline pools
> at 97.0-97.5% on 140 hand-verified Smithsonian images that played
> no role in any revision -- evidence of transfer to this corpus (see
> "Fresh-corpus replication" below).
> Depicts annotation is a dead end
> for this corpus: 0/231 files carry P180 statements. See STATUS.md
> "Next steps" item 2.

## Fresh-corpus replication (complete 2026-09-25)

**Why:** Every taxonomy revision (v6-v9) was authored from corrections
on the two existing corpora. Before approaching the National Library
of Norway, the methodology needs a replication on material that played
no role in any revision or authoring decision -- a fresh corpus
through the frozen pipeline, measurement-only. This tests whether the
loop's result generalizes; it is the de-risked version of lever (1)
above.

**What:** `REPLICATION_PROTOCOL.md` (committed before the run) holds
the full pre-registration: fresh corpus from Smithsonian Open Access
(primary; Met API fallback), 4-5 categories drawn from the
institution's own terms (not ours), 40 images per category, >= 20
hand-verified per category before the run, sealed manifest (no
top-ups), frozen v9 pipeline (taxonomy, 0.7 threshold, text-bearing
routing, Pixtral prompt), and 3 identical runs for run-to-run
variance. No taxonomy changes, no threshold changes, no exclusions
after seeing results.

**Status (2026-09-25): complete.** Corpus fetched (160 images, 40 per
category from Smithsonian Open Access: portrait_photo, human_painting,
human_sculpture, graphic_design; 4 dead IDS links documented), the
pipeline run 3x (160/160 each, 0 errors), and all 160 records
hand-verified through `verify_replication.py` (134 correct, 6
corrected, 20 excluded -- 16 animal sculptures in human_sculpture, the
predicted noise family; 4 dead links). Manifest sealed. Verified
numbers: pooled 97.5% / 97.0% / 97.0% across the three runs -- well
above the pre-registered 90% bar; auto-accept band mismatch 3.48-4.20%
(Wilson 95% CI 1.36-9.46%), at or below half the Commons reference (15%);
routing burden 15-18%. human_sculpture 93% on the verified subset (was
80% against the noisy category labels). Run-to-run variance: 92% of
records identical across all 3 runs. Protocol deviation documented in
REPLICATION_RESULTS.md: the runs executed before hand-verification at
the user's direction; the verified-subset analysis used the same
frozen pipeline and the same pre-registered criteria. **Verdict: evidence
of transfer to this institutional corpus**, without re-tuning; not proof
of reliable unattended cataloging across arbitrary collections. See
REPLICATION_RESULTS.md.

The original `classify_images.py` scaffold asked one yes/no question.
The adopted humanoid pilot now uses five facets through
`pilot_humanoid.py`; the original motivations below describe the earlier
state. Stable item numbers are retained for links from other documents.

---

## High priority -- make Jev do real classification work

### 1. Multi-class taxonomy

**Current status: implemented through the adopted facet taxonomy.**

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

**Current status: deferred alternative.** The adopted design uses facets,
not recursive image-tree traversal.

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

**Current status: implemented.** Multi-facet classification is adopted;
the structured-vision variants below were experiments, not replacements
for the adopted cascade.

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
measured negative vs the cascade (91%, 79%, 18/27 caught vs 8/25).
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

**Current status: initial routing policy implemented; multi-band escalation
remains optional.** Validate any new policy on held-out pilot data.

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

**Current status: manual revision and held-out measurement implemented.**
v9 remains adopted; automated authoring is not implemented.

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

**Current status: retained replication repeats exist.** Broader
repeatability and uncertainty on real-library material remain to be measured;
the original single-run motivation below is historical.

**Why:** Every result here is from a single Jev call per image. We do
not know whether Jev is deterministic on image descriptions. If the same
description yields 1.000 on one call and 0.70 on the next, the
confidence thresholds are less meaningful than they appear.

**What:** Pick ~10 images (mix of high-confidence and flagged).
Classify each 10 times against the same criteria. Measure mean and
standard deviation of confidence, and whether the choice ever flips.

**Update (2026-09-23):** a cross-prompt comparison now exists (old
vs. fixed vision prompt: 204/215 contains_human agreement, queue
79 -> 52), but that changes two variables at once.

**Update (2026-09-24):** same-prompt, same-description variance is now
measured once, as a byproduct of the held-out revision: the v6
criteria were run twice on the same 55 descriptions -- identical
choices on all five facets, but 14 vs 16 threshold-routed records
(25% vs 29% burden). Choices are stable; confidences drift by a few
points run to run, which moves records across the 0.7 boundary.

**Effort:** Small. A loop over the existing `jev_classify` function.

### 7. Ground truth and accuracy

**Current status: labeled personal/stand-in and verified replication
evaluations exist.** Independent re-review and real-library labels remain
open; the UI fixes did not revalidate old labels.

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

**Current status: keyword and direct-vision comparisons complete.**
A pixel-level baseline remains optional and unmeasured.

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
confident): 78% pooled accuracy, ECE 0.216, 0/49 errors caught.
Pixtral-direct: 80%, ECE 0.193, 0/45 caught -- it reports >= 0.9
confidence on everything despite being wrong a fifth of the time.
Cascade (Pixtral+Jev): 91%, ECE 0.051, 18/27 caught. The cascade
wins on every measure; Jev supplies the calibrated probability that
makes routing possible. A CLIP-style pixel-level baseline remains
unmeasured.

**Effort:** Moderate. Needs a baseline model and ground-truth labels.

### 9. Adversarial and edge cases

**Current status: initial generated suite measured.** Broader real-world
coverage, especially screenshots and background people, remains open.

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

**Current status: deferred experiment, not an adopted pipeline change.**

**Why:** The pipeline uses only Jev's Choice primitive. Jev also has
Score (rate on a 2-10 scale) and Noul (yes/no probability). These could
help: Noul as a pre-filter ("is this image relevant to the 'human'
branch?"), Score as a continuous fit measure.

**What:** Build a variant that uses Noul as a pre-filter and Score as a
confidence supplement. Compare to the Choice-only pipeline.

**Effort:** Small. The API supports all three in a single call.

### 11. Larger dataset and different domains

**Current status: Commons stand-in and Smithsonian replication complete.**
A controlled real-library pilot remains the next application step.

**Why:** The pipeline ran on 215 images from one folder. Scaling to a
larger, more varied collection (and different domains, e.g. medical or
satellite imagery) would test whether the approach generalizes.

**What:** Run the pipeline on a larger or different image set. Compare
confidence distributions and flag rates.

**Effort:** Small if a dataset is available; the pipeline works as-is.

---

## Current status by original item

| # | Item | Completed | Remaining |
|---|---|---|---|
| 1 | Multi-class taxonomy | Adopted facet taxonomy | Validate on pilot material |
| 2 | Hierarchical image ontology | Facets adopted instead | Optional tree comparison |
| 3 | Multiple questions | Multi-facet calls | No implementation gap |
| 4 | Review routing | Threshold plus text signal | Pilot validation; optional multi-band policy |
| 5 | Criteria revision | Manual loop and held-out measurement | New evidence before more tuning |
| 6 | Repeatability | Retained replication runs | Repeatability on pilot cohort |
| 7 | Labels and accuracy | Existing corpus evaluations | Independent re-review and pilot labels |
| 8 | Baselines | Keyword/direct-vision comparisons | Optional pixel-level baseline |
| 9 | Edge cases | Initial generated suite | Representative real-world coverage |
| 10 | Score/Noul primitives | Not adopted | Deferred experiment |
| 11 | Broader corpus | Commons and Smithsonian studies | Real-library pilot |
