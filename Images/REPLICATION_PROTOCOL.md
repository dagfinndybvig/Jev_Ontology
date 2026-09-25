# REPLICATION_PROTOCOL.md — Fresh-corpus replication of the Jev image-classification pipeline

**Status: executed (2026-09-25).** This file was committed before any
fetch or pipeline run, as the pre-registration. The run is complete and
the results are in `REPLICATION_RESULTS.md` (both bases reported:
category-implied and hand-verified). Amendments over the original
proposal are marked **(amendment)**.

## Purpose and scope

Every taxonomy revision (v6–v9) was authored from corrections on the two
existing corpora: the personal photo collection (218 images) and the
Wikimedia Commons stand-in (240 images, complete human ground truth, v9 at
96% held-out / 95.1% vs all human corrections). Before approaching the
National Library of Norway, the methodology needs a replication on material
that played no role in any revision or authoring decision — a completely
fresh corpus through the frozen pipeline.

**This is a measurement-only task.** The repo's discipline — v3, v5, v8,
and v10 were all measured and rejected — is the whole point.

Explicitly out of scope:

- Any taxonomy revision. No v11 from these results; corrections found here
  may seed a future revision with its own held-out protocol.
- Any prompt or threshold changes, before or after seeing results.
- Any National Library material.

## Corpus selection

**Decision rule:** pick whichever source can populate all planned
categories with >= 40 usable, hand-verifiable images each. Document the
choice and reasoning in REPLICATION_RESULTS.md.

Probe results (2026-09-25, live):

- **Smithsonian Open Access** (primary): bulk metadata on AWS S3
  (`smithsonian-open-access` bucket, s3-us-west-2), directory index at
  `https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan/index.txt`.
  No API key. The index lists 38 unit directories; relevant units:
  `npg` (National Portrait Gallery — portrait photographs), `saam`
  (American Art — paintings/illustrations), `sil` (Smithsonian Libraries —
  book covers), `chndm` (Cooper Hewitt — posters/graphic design). Records
  are JSON per unit file; two record types observed: `edanmdm` (object
  records, carry `online_media` with `ids.si.edu` image URLs) and
  `ead_component` (archival finding-aid components, mostly no media) —
  the fetch script filters to `edanmdm` records with image media.
  Caveat: type/medium terms are object-level and non-uniform; category
  construction needs a verification pass.
- **Met API** (fallback): free, no key, ~490k open-access objects with
  actual classification and medium fields plus CC0 image URLs. Categories
  nearly trivial to construct, but the mix is art-heavy (weaker on
  photographs; no screenshots).
- **Harvard LIL mirror on source.coop** (amendment): the `metadata.parquet`
  catalog pre-filters to records with images, but reading parquet requires
  pyarrow/pandas — it breaks this repo's stdlib-only convention. Use only
  as an out-of-repo exploration aid, or skip; the S3 route works with
  stdlib urllib.

## Category scheme (Option A: remap)

Do not reuse the Commons six categories verbatim. Categories come from the
institution's own vocabulary — this is a dry run of exactly what the
National Library pilot would do (classify against a real institution's
cataloging terms).

**Final category definitions** (probed 2026-09-25 from source metadata;
filters are on the source's own `indexedStructured` fields —
`object_type` and `topic` — not on our vocabulary):

1. `portrait_photo` — unit `npg` (National Portrait Gallery);
   `object_type` contains "Photographs" AND `topic` contains
   "Portraits". Measured density: 95 Photographs / 216 Portraits in
   the first 4 metadata files; 214 of 228 `edanmdm` records carry CC0
   images.
2. `human_painting` — unit `saam` (Smithsonian American Art Museum);
   `object_type` contains "Paintings" OR "Graphic arts", AND `topic`
   contains "Portraits" OR "Figure group". Measured density: 65
   Paintings + 63 Graphic arts per 4 files; 189 of 205 records carry
   CC0 images.
3. `human_sculpture` — unit `saam`; `object_type` contains
   "Sculpture". Measured density: 13 per 4 files (~6% of records) —
   the fetch script scans more files to reach 40; feasible.
4. `graphic_design` — unit `chndm` (Cooper Hewitt, the design
   museum); `object_type` contains "Prints" OR "Bound print" OR "Wall
   coverings" (poster-like and graphic material). Measured density:
   212 Prints + 38 Bound print + 76 Wall coverings per 4 files; 830
   of 879 records carry CC0 images.

Dropped during the probe:

- `sil` (Smithsonian Libraries) — **not viable**: 14,626 `edanmdm`
  records in the first 4 files but only 3 carry images (bibliographic
  records, not digitized objects). Book-cover material is served by
  `chndm`'s Bound prints and `saam`'s Graphic arts instead.
- Digitized-text/screen analog — neither candidate source supports it
  (as expected); the scheme has 4 categories. **(amendment)**

The five Jev facets (`contains_human`, `contains_robot`,
`contains_android`, `primary_subject`, `representation`) and their v9
definitions are frozen. Only the category labels (ground truth) are new.

**(amendment)** The comparison against the Commons 240 will not be
like-for-like: no candidate source supports a `ui_screenshot` category.
Compare on shared categories, or state the mix difference explicitly in
REPLICATION_RESULTS.md.

## Protocol (pre-registered — commit before running)

1. Define categories from source metadata; commit the final category
   definitions in this file before fetching.
2. Sample 40 images per category at random (fixed seed, recorded in the
   manifest).
3. Download referenced images; resumable, polite fetch. The Commons
   rate-limit lessons apply as defaults (standard thumbnail sizes, high
   DELAY, resume across sessions); S3 and the Met API should not throttle
   like Wikimedia, but keep DELAY high anyway.
4. Hand-verify >= 20 per category before the main run — 80–100
   verifications total. **(amendment)** This is the human cost of the
   replication; it is stated up front so it is visible before committing
   to the run. The Commons corpus taught us category-implied labels are
   noisy ("Category:Statues" contained animal statues). Images whose
   category-implied label is wrong are excluded before the run, with
   counts recorded. No exclusions after seeing pipeline results.
5. Seal the manifest: commit ids, category labels, source metadata,
   licenses, verification decisions. No additions after sealing — unlike
   the Commons top-ups, which left 9 images unmeasured.
6. Freeze: v9 taxonomy, 0.7 threshold, `routing.py` text-bearing rule,
   Pixtral vision prompt as-is. Exact versions below.
7. Run the pipeline 3 times on the sealed corpus (identical config) to
   quantify run-to-run variance on fresh material. Each run writes a
   fresh results file — the measure scripts skip records with
   `status: ok`, so a re-run into the same file silently does nothing.

## Frozen configuration

- Taxonomy: `humanoid_taxonomy_v9.json` (v9, adopted; derived from v7).
- Vision: Pixtral, model `pixtral-12b-2409` (`classify_images.py`
  `VISION_MODEL` default), prompt as-is (check-text-first).
- Decision: Jev, model `jev-latest`, five facets, calibrated confidence.
- Routing: 0.7 threshold + `routing.py` text-bearing signal, unchanged.
- Cost: ~$0.0003/image for the vision step; 3 runs over ~160–200 images
  is trivial.

## Success criteria (pre-registered)

1. **Pooled facet agreement >= 90%** on hand-verified labels.
2. **Auto-accept band miss rate** (above 0.7, non-routed): reported with a
   Wilson CI, no hard pass/fail. **(amendment)** Reference points measured
   on this repo's corpora:
   - Commons 240: 22/151 = 15% (v9-era corrections, `routing.py`'s actual
     rule — the confident band is 151 records).
   - Personal collection: 7/30 = 23% (v4-era stored answers, Wilson CI
     ~12–41%; 6 of the 7 misses are `representation`).
   The original proposal's <= 15% bar sits exactly at the Commons measured
   value with zero margin; on fresh material it can land above for reasons
   already measured as noise. At or below the Commons reference supports
   generalization; above it, report and analyze — do not re-tune.
3. **Routing burden**: reported as a number with no target (a measurement,
   not a KPI).
4. **Known failure families** (screenshot-of-text, depicted-vs-described):
   zero occurrences would be ideal; any occurrences are recorded, not
   patched.

## Ground truth and post-measurement review

- Category-implied labels (verified) serve as ground truth for the run, as
  with the Commons corpus.
- If feasible, review the full routed queue through `review_ui.py`
  afterward to get the same per-facet accuracy-vs-confidence tables as
  before — but this is post-measurement analysis, not a license to
  re-tune anything.

## Deliverables

- `REPLICATION_PROTOCOL.md` (this file, committed before the run:
  categories, sampling, exclusions, frozen versions, success criteria,
  decision rules).
- `fetch_replication_corpus.py` (resumable) and a committed manifest.
- `REPLICATION_RESULTS.md`: per-category and per-facet agreement,
  calibration/ECE, routing burden, run-to-run variance, comparison table
  against the Commons 240 result (96% pooled held-out; 95.1% vs all human
  corrections), and an explicit "does the loop's result generalize?"
  verdict with caveats.
- `STATUS.md` entry as usual.

## Reporting discipline

Report honestly, including failure. A mixed result is publishable as-is; a
curated result is not. The repo's credibility rests on rejected revisions
being documented.

## Privacy

Smithsonian and Met metadata and images are public (CC0) — no redaction
needed. The personal-collection privacy rules in `AGENTS.md` are unchanged
and still apply to everything else in this repo.
