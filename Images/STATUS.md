# Status: Where We Are, Where to Pick Up

**Last updated:** 2026-09-23 (original run and humanoid pilot 09-22;
folder verification, prompt fix, re-run, and taxonomy v2 on 09-23)
**Repo state:** see git; keep in sync with `origin/main` before new work.

---

## What happened on 2026-09-23 (this session)

1. **Folder verification.** `sort_humanoids.py` copies each image
   into `PICTURES_DIR\Humanoids\<primary_subject>\<representation>\`
   plus `_review\` (low-confidence and corrected records), so the
   pilot can be verified by eye. First look: correct throughout,
   except the known failure image.
2. **Second screenshot-of-text false positive.** A screenshot of a
   text-only terminal showing DeepSeek text describing an image was
   classified as a promotional photograph at 1.0 confidence. Both
   instances involve text describing "a man and a robot."
3. **Vision prompt fix.** `classify_images.py` now makes Pixtral
   check for text first and state the medium. Verified live; a weaker
   medium-first draft failed on the known image. RESULTS.md documents
   both corrections.
4. **Full re-run (fixed prompt, taxonomy v1).** 218 images (3 new),
   0 errors. Queue 79 -> 52; `representation` hedges 64 -> 28. The
   failure image became `text_screenshot` raw, but Jev still answered
   the *described* scene for `primary_subject` -- a criteria gap.
5. **Sorter bug fixed.** `manual_correction` labels are nested under
   `correct`; the sorter first read them at the wrong level. Fixed;
   placement verified with find.
6. **Taxonomy v2 (depicted vs. described).** New
   `humanoid_taxonomy_v2.json` adds one clause to every entity facet:
   only what the image itself shows counts; entities merely mentioned
   or described in text do not. Pilot re-run on the same 218
   descriptions (v1-criteria results preserved privately):
   - The failure image is now correct raw on all five facets
     (`primary_subject: none` at 0.88, was `multiple` at 0.91). No
     manual correction needed anymore.
   - Choice agreement with v1 criteria: 217/218 on four facets,
     213/218 on primary_subject; the five subject flips are the
     intended fixes or noise on already-hedged records.
   - Queue 50/218 (23%), down from 52. `contains_human` 66/152.
   - This is the first criteria revision driven by review-queue
     signals -- in-sample only; LIBRARY.md Phase 6's held-out
     protocol applies to future revisions.
7. **Review UI.** `review_ui.py`: a localhost single-page app for
   walking the queue -- image, description, facet confidences, and
   confirm/correct buttons whose choices come from the taxonomy JSON.
   Corrections save as `manual_correction` blocks and double as the
   Phase 0 ground-truth seed. Tested against a copy of the results
   (via `REVIEW_RESULTS`) before pointing at the live file. First
   browser run hung at "Loading...": `init()` called a nonexistent
   `buildFilters()`; fixed by removing the call and wrapping `init()`
   in try/catch so errors surface in the pane. Reproduced and
   verified with a Node DOM-stub harness against the live API
   payloads before restarting the server.
8. **First review pass (25 records).** The dubious cases were
   reviewed via the UI: 13 confirmed, 12 corrected. On this
   ground-truth-seeded subset, per-facet accuracy was 76-96%
   (contains_human lowest at 76%, contains_android highest at
   96%), and pooled accuracy rose monotonically with confidence:
   62-67% below the 0.7 threshold, 83% at 0.7-0.9, 94% at 0.9-1.0.
   Every wrong record was in the review queue -- zero errors found
   above threshold in the reviewed set. Analysis is now restricted
   to reviewed records; the other 25 queued and 168 unqueued
   records remain unverified.
9. **Review UX hardened.** The queue view now shows only unreviewed
   queued records by default (a pending-only toggle, on by default),
   the header carries a live pending count that turns green with
   "queue complete" at zero, and finishing the last pending record
   shows an explicit "Review complete" pane. Saving advances to the
   next pending record without re-showing reviewed ones. Verified
   with five scenario tests in the Node DOM-stub harness (the
   harness needed a document.createTextNode stub).
10. **Review queue completed.** All 50 queued records reviewed:
   28 confirmed, 22 corrected. Per-facet accuracy 80-98%
   (representation and contains_human lowest at 80%), pooled
   accuracy 72%/66% below the threshold, 88% at 0.7-0.9, 95% at
   0.9-1.0. Every wrong record was in the queue; zero errors above
   threshold. The 168 confident records remain unverified, so the
   threshold's miss rate is unknown. See RESULTS.md for the tables.
11. **Taxonomy revision series (v3, v4, v5).** Three revisions from
   the 22 corrections, each run separately and measured on the 50
   reviewed records. v3 (broadened text_screenshot to game/app
   screens): rejected -- accuracy flat, five hedged errors became
   confident. v4 (depiction counts in any medium; robots need a
   being-like form): adopted -- contains_human 88%, 19 wrong
   records, two confident errors. v5 (content-based screenshot
   rule): rejected -- representation +1 but six confident errors.
   Lesson: de-hedging without accuracy gains manufactures silent
   errors; measure errors-caught per burden, not queue size.
   `pilot_humanoid.py` defaults to v4; the live results are the v4
   run with the 50 review corrections merged.
12. **Confident-band sampling instrumented.** The review UI gained a
   Sample filter: a deterministic, stratified sample of 30 fully
   confident unreviewed records (15 from the 0.7-0.9 band, 15 from
   0.9-1.0, round-robin across representation classes), computed
   once and persisted privately
   (`../Ontology_private_backup/confident_sample_v1.json`). Reviewing
   it bounds the 0.7 threshold's miss rate and extends the labeled
   set into the confident band.
13. **Confident-band sample reviewed (30/30).** Miss rate 7/30
   (23%, Wilson CI 12-41%) -- but 6 of 7 errors are `representation`;
   entity facets are 97-100% in the band (entity-only miss 3%).
   `representation` accuracy is 80% in the band, the same as in the
   queue: its confidence carries no information. See RESULTS.md
   ("Confident-band verification"). 85 of 218 records are now
   labeled.
14. **Phase 2 baseline started (two of three systems).**
    `baseline_compare.py` measures accuracy, ECE, flag rate at 0.7,
    and errors caught against the 85 reviewed records. Keyword
    baseline (trivial, always confident): 78% pooled accuracy, ECE
    0.166, 0/49 errors caught. Cascade (Pixtral+Jev): 91%, ECE 0.038,
    16/27 caught. Jev adds calibration, not just accuracy -- the
    baseline matches on easy facets and collapses on ambiguous ones,
    silently. Pixtral-direct (`baseline_pixtral_direct.py`,
    resumable) is blocked: Mistral returned HTTP 402 Payment Required
    on every call -- the account needs credits. See RESULTS.md
    ("Phase 2 baseline").

## Where things live

| Thing | Path |
|---|---|
| Pilot plan and results write-up | `Images/LIBRARY.md` |
| Run write-up (both corrections, re-run, taxonomy v2) | `Images/RESULTS.md` |
| Pilot taxonomy v4 (current, adopted) | `Images/humanoid_taxonomy_v4.json` |
| Pilot taxonomies v1-v3, v5 (history; v3 and v5 measured rejections) | `Images/humanoid_taxonomy_v*.json` |
| Pilot script (public; `TAXONOMY` env var selects version, v4 default) | `Images/pilot_humanoid.py` |
| Sorter (public) | `Images/sort_humanoids.py` |
| Review UI (public; localhost web app) | `Images/review_ui.py` -> http://localhost:8765 |
| Phase 2: Pixtral-direct baseline (public) | `Images/baseline_pixtral_direct.py` |
| Phase 2: three-system comparison (public) | `Images/baseline_compare.py` |
| Pixtral-direct results (private, gitignored) | `Images/baseline_pixtral_direct_results.json` |
| Sorted folder tree (private) | `PICTURES_DIR\Humanoids\` (+ `_review\`) |
| Pilot per-image results (private, gitignored) | `Images/humanoid_pilot_results.json` |
| Original-run results (private, gitignored) | `Images/image_human_results.json` |
| Confident-band sample (private) | `../Ontology_private_backup/confident_sample_v1.json` |
| Baselines (private) | `../Ontology_private_backup/` (`rerun_v1_2026-09-23/` = old prompt; `2026-09-23_criteria_v1_run/`; `2026-09-23_criteria_v2_reviewed/` = reviewed ground truth; `2026-09-23_taxonomy_v3_run/`, `..._v4_run/`, `..._v5_run/`) |
| Review queue printout | rerun `python pilot_humanoid.py` (instant; resumable) |

## Next steps, in order

1. **Finish Phase 2: Pixtral-direct.** Add Mistral credits (the run
   failed with HTTP 402 Payment Required), then rerun
   `python baseline_pixtral_direct.py` (resumable; 85 vision calls)
   and `python baseline_compare.py` -- the three-way comparison
   answers whether the Jev hop earns its keep.
2. **Representation residuals are vision-limited.** The remaining
   representation errors trace to descriptions that mislead (a
   photographed cover described as "consists of text"). The
   durable fix is LIBRARY.md Phase 3's structured vision state
   (typed fields: medium, subjects, text_in_image), not further
   criteria wording -- v3 and v5 proved criteria wording is
   exhausted.

The android question is settled by the review: the collection
contains no androids (buck.jpg's Twiki is a robot, not an android).
Keep the facet for library material, where the question will
actually arise.

## Open decisions

- Threshold 0.7 is validated two-sided for entity facets: the queue
  caught 17/19 errors in the v4 run at a ~20% burden, and the
  confident band's entity miss rate is ~3%. `representation` is the
  exception -- ~80% accurate at every confidence level, so it needs
  a review-always policy or Phase 3's structured vision state.
- Taxonomy v2's improvement is measured in-sample (same 218
  descriptions). The held-out protocol (LIBRARY.md Phase 6) is the
  standard for calling a revision real.
- The 218-image collection is personal photos, not library material.
  Phase 0 work on it is practice; the real ground truth comes from an
  actual library collection.
