# AGENTS.md — Images sub-project

Essential context for any agent working in this directory.

## Privacy (non-negotiable)

- `image_human_results.json`, `humanoid_pilot_results.json`, and
  `image_human_summary.txt` are **private** (gitignored): they hold
  real filenames and descriptions of a personal photo collection.
  Never commit them; never quote real filenames in public docs.
- In `RESULTS.md`, filenames are redacted (`image_01`, `image_02`,
  ...). Keep that convention in all public docs.
- Old-run baselines live outside the repo in
  `../Ontology_private_backup/` (e.g. `rerun_v1_2026-09-23/`). New
  backups go there too, not into the repo.

## Environment

- `PICTURES_DIR` — the folder of images to classify (set as a
  user-level env var on this machine).
- `MISTRAL_API_KEY` — Pixtral vision calls and Mistral image
  generation (`generate_edge_cases.py`). `TYPESAFE_API_KEY` — Jev.
- Scripts are stdlib-only Python (urllib, json, shutil); nothing to
  install. One exception: `review_ui.py` uses Pillow, if present, to
  convert TIFF to PNG on the fly (browsers cannot render TIFF);
  without Pillow it returns a clear error for TIFF only.

## Pipeline (all resumable, incremental saves)

- `classify_images.py` — Pixtral describes each image (the prompt
  checks for text first and states the medium), Jev answers
  contains_human. Writes `image_human_results.json`.
- `pilot_humanoid.py` — one Jev call per *stored* description, five
  facets from the taxonomy JSON (`TAXONOMY` env var selects the
  version; default `humanoid_taxonomy_v9.json`, the second
  held-out-validated revision). Writes
  `humanoid_pilot_results.json`. No vision calls.
- `sort_humanoids.py` — copies images into
  `PICTURES_DIR\Humanoids\<primary_subject>\<representation>\` plus
  `_review\` (corrected records and anything the routing rule in
  `routing.py` flags: facet confidence < 0.7 or a text-bearing
  description signal). Honors `manual_correction`; the corrected
  labels are nested under its `correct` key.
- `review_ui.py` — localhost review app (127.0.0.1:8765): confirm or
  correct classifications through the browser; writes
  `manual_correction` blocks into `humanoid_pilot_results.json`.
  The queue view shows only unreviewed queued records by default and
  flags completion explicitly; each queued record is tagged with its
  routing reason (`text-bearing` or `low conf`) from
  `routing.py`'s `route_reason`. A Sample filter walks a fixed,
  stratified sample of 30 fully confident records (persisted at
  `../Ontology_private_backup/confident_sample_v1.json`) to bound
  the threshold's miss rate. For testing, point `REVIEW_RESULTS` at
  a copy of the results and `REVIEW_SAMPLE` at a temp path. To review
  the stand-in corpus instead of the personal collection, run with
  `REVIEW_RESULTS` at `library_standin_results.json`,
  `PICTURES_DIR` at `library_standin/`, `TAXONOMY` at
  `humanoid_taxonomy_v4.json`, and `REVIEW_SAMPLE` at a temp path
  (otherwise the Sample filter overwrites the personal collection's
  persisted sample).
- `baseline_pixtral_direct.py` — Phase 2 baseline: Pixtral classifies
  the five facets directly (v4 criteria) on the labeled records.
  Writes `baseline_pixtral_direct_results.json` (private,
  gitignored). Resumable; needs MISTRAL_API_KEY credits (a run
  failed with HTTP 402 Payment Required on 2026-09-23 until the
  account was topped up; the completed run is 85/85, 0 errors).
- `baseline_compare.py` — Phase 2 comparison: keyword baseline vs.
  cascade vs. Pixtral-direct vs. structured vision state (when
  present) against the manual_correction ground truth. Accuracy,
  ECE, flag rate at 0.7, errors caught. No API calls.
- `structured_vision.py` — Phase 3: Pixtral extracts typed fields
  (medium, subjects, text_in_image, setting, people), Jev classifies
  the composed state. Two resumable stages; writes
  `structured_vision_results.json` (private, gitignored). The medium
  vocabulary must stay aligned with the representation classes
  (v1's poster/diagram vocabulary was a measured regression). The
  parser needs `strict=False` and the regex repair fallback: Pixtral
  emits raw newlines and unescaped quotes inside transcribed text.
- `capture_type.py` — Option 1 experiment (falsified): an isolated
  binary capture question with a deterministic medium override.
  Writes `capture_type_results.json` (private, gitignored). Kept as
  the measured record: the vision model answers `digital_capture`
  for plain photographs -- the text-vs-physical distinction is
  perceptual, not fixable by question architecture.
- `routing.py` — Option 2 (adopted): routes records to review on the
  0.7 threshold OR a text-bearing signal in the description
  (measured: catches 25/27 errors vs 18/27 for the threshold alone).
  Writes `routing_queue.json` (private, gitignored). The text-signal
  pattern is a single constant, tunable without other code changes.
  The preamble stripper was fixed 2026-09-23 (see gotchas): same
  25/27 catches, burden 156/218 (72%) -> 135/218 (62%).
- `generate_edge_cases.py` — TODO item 9: generates the adversarial
  edge-case suite (text-describes-scene, memes, AI-generated people,
  collages, background people, app screens, statue/robot boundaries)
  with Mistral image generation. Creates the image-generation agent
  once (cached in `edge_case_agent.json`, reused across runs), then
  one conversations call per prompt; downloads the file by `file_id`.
  Writes `edge_case_results.json` (private, gitignored); images go to
  `edge_cases/` (gitignored). Resumable; skips `status: ok`. Needs
  MISTRAL_API_KEY credits (per-image rate plus a small token
  overhead; the first 8-image run cost 7,217 tokens + 8 generations).
  `EDGE_CASE_PROMPTS` selects a prompt-list JSON; positional args run
  named prompts only.
- `measure_edge_cases.py` — runs the production path on the generated
  suite: Pixtral describes each image (same prompt as
  `classify_images.py`), Jev answers the five facets (v4 taxonomy,
  same call shape as `pilot_humanoid.py`), and answers are compared
  to the intended labels each prompt was written to elicit. Facets
  whose truth the taxonomy cannot express are marked `ambiguous` and
  excluded from strict agreement. Also applies `routing.py`'s
  `route_reason` to each record. Writes
  `edge_case_pipeline_results.json` (private, gitignored). Resumable;
  needs both API keys.
- `fetch_library_standin.py` — fetches the stand-in library corpus
  from Wikimedia Commons: one category per taxonomy class
  (`CATEGORIES` below is data), a deterministic stride sample over
  the category members, 960px thumbnails (a Wikimedia standard size),
  and `library_manifest.json` as the stand-in ground truth (filename,
  category, Commons description, license, depicts statements). The
  manifest is committed (public data); images go to
  `library_standin/` (gitignored). Resumable: tops up to
  `LIBRARY_PER_CATEGORY` (default 40) per category. First run:
  149 images across 5 of 6 categories (statue 28, humanoid_robot 22,
  book_cover 36, human_photo 33, human_illustration 30;
  ui_screenshot 0) before Wikimedia rate-limited the IP. Top-up
  (2026-09-23, block lifted): 231 total across all 6 categories
  (statue 40, humanoid_robot 40, book_cover 40, human_photo 40,
  human_illustration 38, ui_screenshot 33) -- 9 short of target, 11
  downloads lost to HTTP 429s even at 20s spacing. Complete
  (2026-09-24): a re-run fetched the last 9 (human_illustration 40,
  ui_screenshot 40) -- 240 total, 40 per category, 0 errors. Note:
  a 429-blocked re-run exits 0 and fetches nothing (the script
  catches and continues); if a run fetches nothing, re-run later.
  DELAY is 20s (5s drew 429s on the top-up).
- `measure_library_standin.py` — runs the production path on the
  stand-in corpus: Pixtral describes each image (same prompt as
  `classify_images.py`), Jev answers the five facets (v4 taxonomy,
  same call shape as `pilot_humanoid.py`), and answers are compared
  to the labels the manifest category implies (facets the category
  cannot determine are marked `ambiguous` and excluded from strict
  agreement). Also applies `routing.py`'s `route_reason` and reports
  the burden per category. Writes `library_standin_results.json`
  (private, gitignored). Resumable; needs both API keys. First run:
  149/149, 0 errors, pooled agreement 541/615 (88%) — Commons
  categories are noisy labels, so mismatches are review candidates,
  not verdicts. Full-corpus v4 run: 231/231, 794/929 (85%).
  Production re-run with v7 (2026-09-24): 240/240, 0 errors, pooled
  857/960 (89%), routing burden 106/240 (44%). Resume trap: the
  script skips records already in the results file, so a full re-run
  requires moving the results JSON aside first (the v4 run's raw
  answers are backed up at
  `../Ontology_private_backup/v4_corpus_run_2026-09-24/`; the 136
  manual corrections were merged back into the new results file
  afterwards — corrections are ground truth, not model answers).
- `author_taxonomy_v6.py` / `author_taxonomy_v7.py` — build the
  held-out revision taxonomies from v4/v6 JSON (criterion text is
  data; the scripts patch and bump `_meta`). v6 was authored from
  batch 1 signals; v7 = v6's entity changes + v4's representation
  wording. Committed (public data).
- `author_taxonomy_v9.py` — builds v9 from v7 under the split-half
  protocol (ground truth complete at 240/240, so the held-out split
  is deterministic: md5(filename) first hex char, even = authoring
  half 132, odd = measurement half 108; every correction family in
  both halves). Three changes from the authoring half only: v8's
  subject-decides clause refined ("display model"; a real,
  functioning robot is photograph), text_screenshot extended to
  software interfaces, contains_human background-people clause.
  Committed (public data).
- `measure_taxonomy_v9.py` — the split-half held-out measurement:
  runs the taxonomy's five facets (Jev calls only) on the
  measurement half (side M of the same md5 split — `side()` must
  match the authoring script) and compares to the manual corrections
  and v7's stored answers, with per-record fixes/breaks. `TAXONOMY`
  selects the version, `RESULTS_OUT` the output file (default
  `taxonomy_v9_halfM_results.json`, private, gitignored). Resumable;
  needs TYPESAFE_API_KEY. Measured: v9 96% vs v7's 94%,
  representation 89% vs 80%, fixes 13 / breaks 4 — v9 adopted.
- `author_taxonomy_v10.py` — builds v10 from v9 under the same
  split-half protocol, from the v9 production residuals: printed
  matter and image-content screenshots excluded from
  text_screenshot; robot costumes and display/exhibit models added
  to statue_or_render. The background-people family is deliberately
  not revised (the descriptions do not mention the humans — a
  vision-layer limit). Committed (public data).
- `measure_taxonomy_v10.py` — the split-half held-out measurement
  for v10 (same md5 split, baseline v9's stored answers). Writes
  `taxonomy_v10_halfM_results.json` (private, gitignored).
  Measured: pooled identical to v9 (96%), fixes 2 / breaks 3 —
  inside noise, v10 not adopted.
- `measure_taxonomy_v6.py` — the Phase 6 held-out measurement: runs
  the taxonomy's five facets (Jev calls only, no vision) on the
  labeled records with `manual_correction` date 2026-09-24 (batch 2,
  55 records) and compares to the manual corrections and v4's stored
  answers. `TAXONOMY` selects the version, `RESULTS_OUT` the output
  file (default `taxonomy_v6_batch2_results.json`, private,
  gitignored). Resumable; needs TYPESAFE_API_KEY. Measured: v6 87%
  (text_screenshot narrowing regressed representation 62% -> 49%),
  v7 89% vs v4's 85% — v7 adopted.
- `measure_taxonomy_v7_personal.py` — re-measures a taxonomy (v7
  default) on the personal collection's 85 labeled records
  (`manual_correction` blocks in `humanoid_pilot_results.json`),
  compared to the manual corrections and v4's stored answers. Writes
  `taxonomy_v7_personal_results.json` (private, gitignored).
  Resumable; needs TYPESAFE_API_KEY. Measured: v7 92% vs v4's 91%,
  fixes 3 / breaks 2, inside noise — v7 became the default. Re-run
  with `TAXONOMY=humanoid_taxonomy_v9.json
  RESULTS_OUT=taxonomy_v9_personal_results.json`: v9 91% vs v4's
  91%, fixes 11 / breaks 11 — a wash, no regression (part of v9's
  adoption).
- Runs skip records with `status: ok`. Fresh descriptions require
  moving the results JSON aside first. Cost is small but real
  (~$0.0003 per image for the vision step).

## Conventions

- Manual corrections never overwrite raw Jev answers: add a
  `manual_correction` block (`date`, `correct`, `reason`,
  `raw_jev_preserved`) and leave the facet answers exactly as the
  model gave them.
- Corrections are documented as dated blockquotes in `RESULTS.md`.
- The review queue is defined as: any facet confidence < 0.7.
- Taxonomy and decision criteria are data
  (`humanoid_taxonomy_v1.json`); changing them is a JSON edit, not a
  code change.

## Docs discipline

After any run or behavior change, update `RESULTS.md`, `STATUS.md`,
`README.md`, `LIBRARY.md`, and `TODO.md` — with every number
recomputed from the result JSONs, never recalled from memory.
`STATUS.md` is the pickup point: session log, file map, next steps.

## Gotchas

- The git root is the parent directory (`Ontology/`); commit from
  there, not from `Images/`. Push only on explicit request.
- Mixed line endings: `README.md` is CRLF, the other docs are LF.
  If an exact-match edit fails on `README.md`, use a script with
  occurrence-count assertions instead.
- Verify file placement with `find`, not `grep` over multi-dir `ls`
  output — that produced a false verification once.
- To debug a browser-page bug in `review_ui.py`'s embedded script:
  extract the `<script>` block, `node --check` it for syntax, then
  run it with a stubbed DOM (`document`/`fetch` as small JS stubs --
  include `createTextNode`; a missing stub surfaces as an app bug
  that is really a harness gap) and the live API payloads curl'd to
  files. This found a nonexistent-function call that left the page
  stuck at "Loading..." while every server endpoint answered fine.
- Wikimedia Commons rate limits are aggressive (found live,
  2026-09-23): bursts of thumbnail downloads get HTTP 429 even at 5s
  spacing, and sustained fetching escalates to a 403 robot-policy
  block on the whole IP (API included) that outlasts a 3-minute
  wait. Use only the standard thumbnail sizes (960, 1280, ... --
  w.wiki/GHai; 1024 is not one), keep DELAY high, and resume across
  sessions rather than pushing through. The `depicts` (P180)
  resolution was debugged 2026-09-23: the old route queried
  `pageprops.wikibase_item` -- the Wikidata Q-id link, empty for most
  files -- instead of the MediaInfo M-id route (`wbgetentities` with
  `sites=commonswiki` + the file title, `props=claims|info`; the
  entity carries `title` for mapping back). The corrected route works
  mechanically, but 0/231 corpus files carry P180 statements:
  Commons structured-data coverage is uneven, so the manifest's
  category remains the only ground truth. Also fixed 2026-09-23: the
  resume path numbered new files from 1, colliding with existing
  manifest keys, so a re-run fetched nothing -- numbering now starts
  after the category's existing count.
- Known failure mode: screenshots of text *describing* a scene.
  Fixed at the vision layer (2026-09-23 prompt); the open half is
  Jev's criteria, which still answer a described scene — the
  "depicted vs. described" clause is pending.
- Mistral image generation API gotchas (found live, 2026-09-23): the
  REST conversations response carries the entries under the top-level
  `outputs` key, not `entries` (the SDK docs show `entries`); and the
  file download returns JPEG (JFIF) bytes even though the `tool_file`
  chunk reports `file_type: png` — sniff the magic bytes, don't trust
  the reported extension.
- `routing.py`'s preamble stripper (found by the edge-case suite,
  fixed 2026-09-23): `description_body` strips the model's check-first
  line only when it is a NEGATION ("does not consist", "consists of
  neither") -- Pixtral's negation wording varies, and unstripped the
  word "terminal" in it fired false `text_bearing` flags on clean
  photographs. Measured trade: stripping negations only keeps 25/27
  catches and drops the burden 156 -> 135 of 218 (72% -> 62%);
  stripping every first line also drops the burden (to 50%) but loses
  2 catches -- first lines that AFFIRM text ("The image consists of
  text.") are true signals and must be kept. If the vision prompt
  changes, re-check the preamble wording against
  `PREAMBLE_NEGATION`.
- `measure_taxonomy_v6.py` resume trap (found live, 2026-09-24): the
  script skips records with `status: ok`, so running it with the
  wrong `TAXONOMY` but the right `RESULTS_OUT` populates the output
  file with the wrong version's answers, and the corrected re-run
  then skips everything as "already done" — identical answers, exit
  0, no error. If a version's answers look suspiciously identical to
  a previous run's, delete the results file and re-run. (This
  produced a live run-to-run variance data point as a byproduct:
  identical v6 criteria, two runs, same choices, 14 vs 16
  threshold-routed.)
- Windows encoding (found in the 2026-09-25 audit): a bare
  `json.load(open(f))` fails on this machine — the default codec is
  cp1252 and the JSONs are UTF-8 (`UnicodeDecodeError` on the first
  non-ASCII byte). Always pass `encoding='utf-8'`. The pipeline
  scripts already do (all 79 `open()` calls); the trap is ad-hoc
  one-liner checks and any future code.
