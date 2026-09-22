# Status: Where We Are, Where to Pick Up

**Last updated:** 2026-09-22 (README sessions: image, alt text, caption, file list)
**Repo state:** clean, in sync with `origin/main`.

---

## What happened on 2026-09-22 (this session)

1. **Full audit and fixes.** Data provenance restored for the corrected
   record (raw Jev output preserved under `jev`), resume-retry bug in
   `classify_images.py` fixed, dead parameter removed, all doc numbers
   recomputed from the result JSONs and corrected.
2. **Anonymization.** Per-image data untracked and gitignored; the
   personal path replaced by `PICTURES_DIR`; git history rewritten
   (private files and filenames removed from all commits) and
   force-pushed. Private backups live outside the repo:
   `../Ontology_pre_rewrite.bundle` and `../Ontology_private_backup/`.
3. **Library plan.** `LIBRARY.md` written: seven phases, grounded in
   the repo's positive and negative results.
4. **Humanoid pilot (Phases 1 and 4).** `humanoid_taxonomy_v1.json`
   (five facets as data) + `pilot_humanoid.py` (one Jev call per image,
   all five questions). 215 images re-classified: 0 errors, $0.0082.
   `contains_human` agreed with the original run 215/215. Aggregate
   findings in `LIBRARY.md` ("Pilot run"). Review queue: 79/215 at
   threshold 0.7, driven mostly by the `representation` facet.

## Where things live

| Thing | Path |
|---|---|
| Pilot plan and results write-up | `Images/LIBRARY.md` |
| Pilot taxonomy (public, data) | `Images/humanoid_taxonomy_v1.json` |
| Pilot script (public) | `Images/pilot_humanoid.py` |
| Pilot per-image results (private, gitignored) | `Images/humanoid_pilot_results.json` |
| Original run results (private, gitignored) | `Images/image_human_results.json` |
| Review queue printout | rerun `python pilot_humanoid.py` (instant; resumable) |

## Next steps, in order

1. **Walk the review queue** (local, private): open
   `humanoid_pilot_results.json` and look at the 79 low-confidence
   records, starting with the `representation` hedges. This is the
   cataloger-eye pass that turns anecdotes into taxonomy revisions.
2. **Sharpen the `representation` definitions** (it produced 64 of 79
   queue entries): the screenshot / interface / illustration boundary
   is where the hedging lives. Revise criteria, re-run the pilot
   (`pilot_humanoid.py` resumes; delete
   `humanoid_pilot_results.json` first to force a full re-run), and
   see if the queue shrinks.
3. **Decide the android question**: 0/215 with two hard hedges.
   Either loosen the criteria or drop the facet until ground truth
   exists.
4. **Phase 0 ground truth (the real dependency).** Label a stratified
   sample of the 215: ~50 random plus the deliberate hard cases
   (depictions, text scans, compound images). Until this exists,
   everything is consistency, not accuracy.
5. **Phase 2 baseline** once labels exist: Pixtral-direct vs.
   Pixtral+Jev vs. a trivial classifier, measured on accuracy,
   calibration, and review burden.

## Open decisions

- Threshold 0.7 gives a 37% review burden; nothing has been decided
  about what burden the library workflow can absorb. Phase 2's
  burden-vs-accuracy curve answers this; for now 0.7 is provisional.
- The 215-image collection is personal photos, not library material.
  Phase 0 work on it is practice; the real ground truth comes from an
  actual library collection.
