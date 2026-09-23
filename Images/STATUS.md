# Status: Where We Are, Where to Pick Up

**Last updated:** 2026-09-23 (sessions: original run 09-22; humanoid
pilot 09-22; folder verification, prompt fix, and full re-run 09-23)
**Repo state:** clean, in sync with `origin/main`.

---

## What happened on 2026-09-23 (this session)

1. **Folder verification.** `sort_humanoids.py` copies each image
   into `PICTURES_DIR\Humanoids\<primary_subject>\<representation>\`
   plus `_review\` (low-confidence and corrected records), so the
   pilot can be verified by eye. First look: correct throughout,
   except the known failure image.
2. **Second screenshot-of-text false positive.** A screenshot of a
   text-only terminal showing DeepSeek text describing an image was
   classified as a promotional photograph at 1.0 confidence. Manual
   correction recorded (raw Jev answers preserved). Both instances
   involve text describing "a man and a robot."
3. **Vision prompt fix.** `classify_images.py` now makes Pixtral check
   for text first and state the medium. Verified live: the failure
   image and a second text screenshot are described as text; normal
   photographs unaffected. A weaker medium-first draft failed on the
   failure image -- the scene description overwhelmed it. RESULTS.md
   documents both corrections.
4. **Full re-run.** 218 images (3 new), 0 errors, negligible cost.
   Review queue 79 -> 52 (37% -> 24% burden); `representation` hedges
   64 -> 28; 11 `contains_human` flips, almost all correct catches of
   text-describing-people images. The failure image is now
   `text_screenshot` at the raw level, but Jev still answers the
   *described* scene for `primary_subject` -- a criteria gap
   ("depicted vs. described"). Android: now 2 raw yes (one is the
   corrected failure record; one is the new Buck Rogers photo).
5. **Sorter bug fixed.** `sort_humanoids.py` initially read
   `manual_correction` labels from the wrong JSON level, so corrected
   records sorted by raw labels. Fixed; placement verified with find.

The old-prompt baseline (both result JSONs) is preserved at
`../Ontology_private_backup/rerun_v1_2026-09-23/` (outside the repo,
private).

## Where things live

| Thing | Path |
|---|---|
| Pilot plan and results write-up | `Images/LIBRARY.md` |
| Run write-up incl. both corrections and the re-run | `Images/RESULTS.md` |
| Pilot taxonomy (public, data) | `Images/humanoid_taxonomy_v1.json` |
| Pilot script (public) | `Images/pilot_humanoid.py` |
| Sorter (public) | `Images/sort_humanoids.py` |
| Sorted folder tree (private) | `PICTURES_DIR\Humanoids\` (+ `_review\`) |
| Pilot per-image results (private, gitignored) | `Images/humanoid_pilot_results.json` |
| Original-run results (private, gitignored) | `Images/image_human_results.json` |
| Old-prompt baseline (private) | `../Ontology_private_backup/rerun_v1_2026-09-23/` |
| Review queue printout | rerun `python pilot_humanoid.py` (instant; resumable) |

## Next steps, in order

1. **Walk the new review queue** (52 records, was 79): same
   cataloger-eye pass, now against `Humanoids\_review\`. The
   `representation` hedges halved; the remaining ones still cluster on
   covers/posters, game and UI screens, and 3D renders -- the missing
   classes identified on 2026-09-22.
2. **Add a "depicted vs. described" clause** to Jev's criteria
   (`contains_human`, `primary_subject`): text describing a person is
   not an image containing one. The re-run shows the vision layer
   fixed but Jev still answering the described scene.
3. **Sharpen the `representation` definitions** (28 queue entries):
   add cover_or_poster, interface_or_game_screen, and 3d_render
   classes; re-run the pilot and see if the queue shrinks further.
4. **Decide the android question**: 2 raw yes now (one corrected);
   `buck.jpg` at 0.55 is the only genuine hedge. Loosen the criteria
   or drop the facet until ground truth exists.
5. **Phase 0 ground truth (the real dependency).** Label a
   stratified sample (~50 random plus the deliberate hard cases:
   depictions, text scans, compound images). Until this exists,
   everything is consistency, not accuracy.
6. **Phase 2 baseline** once labels exist: Pixtral-direct vs.
   Pixtral+Jev vs. a trivial classifier, measured on accuracy,
   calibration, and review burden.

## Open decisions

- Threshold 0.7 now yields a 24% review burden (52/218), down from
  37%. Still provisional; Phase 2's burden-vs-accuracy curve decides.
- The 218-image collection is personal photos, not library material.
  Phase 0 work on it is practice; the real ground truth comes from an
  actual library collection.
