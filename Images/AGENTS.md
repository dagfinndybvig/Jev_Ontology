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
  facets from `humanoid_taxonomy_v1.json`. Writes
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
  a copy of the results and `REVIEW_SAMPLE` at a temp path.
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
