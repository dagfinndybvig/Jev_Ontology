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

## Where things live

| Thing | Path |
|---|---|
| Pilot plan and results write-up | `Images/LIBRARY.md` |
| Run write-up (both corrections, re-run, taxonomy v2) | `Images/RESULTS.md` |
| Pilot taxonomy v2 (current) | `Images/humanoid_taxonomy_v2.json` |
| Pilot taxonomy v1 (superseded, kept for comparison) | `Images/humanoid_taxonomy_v1.json` |
| Pilot script (public; `TAXONOMY` env var selects version) | `Images/pilot_humanoid.py` |
| Sorter (public) | `Images/sort_humanoids.py` |
| Review UI (public; localhost web app) | `Images/review_ui.py` -> http://localhost:8765 |
| Sorted folder tree (private) | `PICTURES_DIR\Humanoids\` (+ `_review\`) |
| Pilot per-image results (private, gitignored) | `Images/humanoid_pilot_results.json` |
| Original-run results (private, gitignored) | `Images/image_human_results.json` |
| Baselines (private) | `../Ontology_private_backup/` (`rerun_v1_2026-09-23/` = old prompt; `2026-09-23_criteria_v1_run/` = fixed prompt, v1 criteria) |
| Review queue printout | rerun `python pilot_humanoid.py` (instant; resumable) |

## Next steps, in order

1. **Walk the review queue** (50 records, was 79 at peak): run
   `python review_ui.py` and open http://localhost:8765 -- confirm or
   correct each queued image's subject and representation; corrections
   are saved as `manual_correction` blocks and double as the Phase 0
   ground-truth seed. The `representation`
   hedges (26) still cluster on covers/posters, game and UI screens,
   and 3D renders -- the missing classes identified on 2026-09-22.
2. **Sharpen the `representation` definitions**: add cover_or_poster,
   interface_or_game_screen, and 3d_render classes as
   `humanoid_taxonomy_v3.json`; re-run and see if the queue shrinks.
   Measure against the v2 baseline, one change at a time.
3. **Decide the android question**: 1 raw yes (`buck.jpg`, 0.55).
   Loosen the criteria or drop the facet until ground truth exists.
4. **Phase 0 ground truth (the real dependency).** Label a stratified
   sample (~50 random plus the deliberate hard cases: depictions,
   text scans, compound images). Until this exists, everything is
   consistency, not accuracy.
5. **Phase 2 baseline** once labels exist: Pixtral-direct vs.
   Pixtral+Jev vs. a trivial classifier, measured on accuracy,
   calibration, and review burden.

## Open decisions

- Threshold 0.7 now yields a 23% review burden (50/218), down from
  37% at the first pilot. Still provisional; Phase 2's
  burden-vs-accuracy curve decides.
- Taxonomy v2's improvement is measured in-sample (same 218
  descriptions). The held-out protocol (LIBRARY.md Phase 6) is the
  standard for calling a revision real.
- The 218-image collection is personal photos, not library material.
  Phase 0 work on it is practice; the real ground truth comes from an
  actual library collection.
