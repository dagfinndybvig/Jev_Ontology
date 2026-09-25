# REPLICATION_RESULTS.md — Fresh-corpus replication of the Jev image-classification pipeline

**Status: measured (3 runs, 2026-09-25). Hand-verification (protocol step 4)
is still open** — see "Protocol deviation" below. The pipeline was frozen
throughout: v9 taxonomy, 0.7 threshold, text-bearing routing, Pixtral prompt
as-is. Nothing was tuned after seeing results.

## Protocol deviation (documented)

The protocol pre-registered hand-verification (>= 20 per category) before the
main run, with the manifest sealed before running. At the user's direction,
the 3x runs executed **before** hand-verification: the manifest is unsealed
and no exclusions have been made. Consequences, handled honestly:

- The primary comparison below is against **category-implied labels** (the
  same basis as the Commons corpus's first run), not hand-verified labels.
- When hand-verification happens (via `verify_replication.py`), the
  verified-subset numbers are computed and reported here as a post-hoc
  analysis on the same frozen pipeline with the same pre-registered success
  criteria — the criteria do not change.
- No exclusions were made after seeing results, and none will be attributed
  to them.

## Setup

- Corpus: 160 images, 40 per category, from Smithsonian Open Access
  (public, CC0): `portrait_photo` (npg), `human_painting` (saam),
  `human_sculpture` (saam), `graphic_design` (chndm). Categories drawn from
  the institution's own `object_type`/`topic` terms
  (REPLICATION_PROTOCOL.md). Fixed-seed sample (seed 20260925, pool 80),
  recorded in `replication_manifest.json` `_sampling`. 4 dead IDS links
  documented as error records; 160 ok records measured.
- Frozen config: `pixtral-12b-2409` vision prompt as-is; Jev `jev-latest`,
  five facets, `humanoid_taxonomy_v9.json`; routing 0.7 + text-bearing
  signal (`routing.py`).
- 3 identical runs, fresh results file per run
  (`replication_results_run{1,2,3}.json`).

## Results (vs. category-implied labels, n=160 per run)

Scored facets per record: 5 for the three human-content categories, 2 for
`graphic_design` (contains_human, primary_subject, representation are
ambiguous — prints and posters may or may not depict humans), so 680 scored
facets per run.

| facet | run 1 | run 2 | run 3 |
|---|---|---|---|
| contains_human | 104/120 (87%) | 104/120 (87%) | 103/120 (86%) |
| contains_robot | 160/160 (100%) | 160/160 (100%) | 160/160 (100%) |
| contains_android | 160/160 (100%) | 160/160 (100%) | 160/160 (100%) |
| primary_subject | 101/120 (84%) | 100/120 (83%) | 99/120 (82%) |
| representation | 109/120 (91%) | 109/120 (91%) | 110/120 (92%) |
| **pooled** | **634/680 (93.2%)** | **633/680 (93.1%)** | **632/680 (92.9%)** |

Per category (pooled across facets, run 1):

- `graphic_design`: 80/80 (100%) — but only robot/android are scored here;
  the ambiguous facets carry no information about this category.
- `portrait_photo`: 199/200 (100%) — one representation miss.
- `human_painting`: 196/200 (98%).
- `human_sculpture`: 159/200 (80%) — see the category-noise finding below.

## Run-to-run variance (fresh material)

- 147/160 records (92%) have **identical five-facet answers across all 3
  runs**; 13 records differ anywhere.
- Per-facet records with differing choices: primary_subject 9,
  representation 6, contains_human 4, contains_robot 0, contains_android 0.
- Routing burden: 31/160 (19%), 31/160 (19%), 26/160 (16%) — the spread is
  in the low-confidence band, not the text-bearing signal.
- Auto-accept band (non-routed) mismatching category labels: 14/129 (11%),
  13/129 (10%), 16/134 (12%).

## The category-noise finding (why the verification pass matters)

`human_sculpture`'s 80% is mostly **label noise, not pipeline error**: saam's
`object_type: Sculpture` includes animal sculptures. 16 of the 40 records
have Jev answering `contains_human: no` — and their descriptions are fish
carvings, a duck, a bird of prey, bronzes of animals. The pipeline is right;
the category-implied label (`contains_human: yes`) is wrong. This is the
same failure the Commons corpus taught ("Category:Statues" contained animal
statues), and it is exactly what the hand-verification pass exists to
exclude — before results, which is why the protocol ordered it first. The
verified-subset analysis will report `human_sculpture` both ways.

## Failure families

- Screenshot-of-text: 0 occurrences in any run (no screenshots exist in
  this corpus — the category was dropped at protocol stage).
- Depicted-vs-described: 2-3 descriptions per run begin "The image consists
  of text" — these are museum plaques and printed labels photographed with
  the object; the medium statement that follows is correct in each case
  examined. No misclassification traced to it in run 1.

## Comparison against the Commons 240

| | Commons 240 (stand-in) | Replication 160 (fresh) |
|---|---|---|
| Source | Wikimedia Commons, 6 categories | Smithsonian Open Access, 4 categories |
| Taxonomy at measurement | v7 (first run) / v9 (production re-run) | v9, frozen |
| Ground truth | category-implied labels (noisy) | category-implied labels (noisy) |
| Pooled agreement | 857/960 (89%, v7) / 94% (v9 production) | 634/680 (93.2%, run 1) |
| vs. human corrections | 95.1% (v9, 240/240 labeled) | pending hand-verification |
| Routing burden | 106/240 (44%) | 31/160 (19%) |

Caveats: the category mixes differ (no ui_screenshot here; graphic_design's
ambiguous facets are excluded from scoring), and the Commons comparison
basis is category-implied labels on both sides. The like-for-like statement
is: on noisy institutional labels, the frozen v9 pipeline pools at ~93% on
material that played no role in any revision — vs. 89% for v7 on the Commons
stand-in it was later revised on.

## Success criteria (pre-registered) — scorecard

1. **Pooled facet agreement >= 90% on hand-verified labels**: pending
   verification; against category-implied labels it is 92.9-93.2% (met on
   the noisier basis).
2. **Auto-accept band miss rate, reported with CI, no hard pass/fail**:
   10-12% mismatching category labels across runs — at or below the Commons
   reference (22/151 = 15%). Note this uses category labels as truth, which
   the human_sculpture finding shows are themselves wrong for ~16 records;
   the verified-subset number will be cleaner.
3. **Routing burden reported, no target**: 19% / 19% / 16%.
4. **Known failure families recorded, not patched**: screenshot-of-text 0;
   depicted-vs-described 2-3 preamble wobbles per run, no traced
   misclassification.

## Verdict: does the loop's result generalize?

**Yes, on this evidence, with the verification caveat.** The frozen v9
pipeline, on 160 images from an institution whose cataloging terms played no
role in any revision, pools at ~93% against noisy category-implied labels —
above the pre-registered 90% bar and above v7's 89% on the Commons stand-in
the loop was tuned on. Run-to-run variance on fresh material is small (92%
of records identical across 3 runs; the differences concentrate in
primary_subject and representation, the two hardest facets). The dominant
error source is the ground truth itself (animal sculptures inside
`object_type: Sculpture`), which is the verification pass's job to remove —
and it is still open. The residual risk: the verified-subset numbers could
move the pooled figure in either direction, and `human_sculpture`'s true
rate is unknown until then.

## Files

- `REPLICATION_PROTOCOL.md` — pre-registration (committed before the run).
- `fetch_replication_corpus.py` + `replication_manifest.json` — corpus and
  ground truth (committed; images gitignored in `replication_corpus/`).
- `replication_results_run{1,2,3}.json` — the three runs' per-image records
  (public data; committed).
- `verify_replication.py` — hand-verification UI (step 4, open).
- `measure_replication.py` — the measurement script (one fresh results file
  per run).
