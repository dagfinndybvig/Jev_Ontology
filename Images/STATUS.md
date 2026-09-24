# Status: Where We Are, Where to Pick Up

**Last updated:** 2026-09-24 (original run and humanoid pilot 09-22;
routing, edge-case suite, stand-in corpus fetch/measure, and the
first review pass on 09-23; corpus top-up and second review pass on
09-23/09-24; corpus complete at 240 and the v7 production re-run on
09-24)
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
14. **Phase 2 baseline complete (all three systems).**
    `baseline_compare.py` measures accuracy, ECE, flag rate at 0.7,
    and errors caught against the 85 reviewed records. Keyword
    baseline (trivial, always confident): 78% pooled accuracy, ECE
    0.166, 0/49 errors caught. Pixtral-direct (85/85 after the
    account was topped up): 80%, ECE 0.150, 0/45 caught -- it
    reports >= 0.9 confidence on everything, ignoring the
    calibration instruction. Cascade (Pixtral+Jev): 91%, ECE 0.038,
    16/27 caught. The cascade wins on every measure; Jev supplies
    the calibrated probability that makes routing possible. See
    RESULTS.md ("Phase 2 baseline").
15. **Phase 3: structured vision state (two iterations).**
    `structured_vision.py` extracts typed fields (medium, subjects,
    text_in_image, setting, people) and Jev classifies the composed
    state. v1 (rich medium vocabulary) regressed on representation
    (67%) -- vocabulary mismatch with the taxonomy. v2 (medium
    aligned to the representation classes): pooled 90%, representation
    76%, burden 22% -- still a measured negative vs the cascade
    (91%, 79%, 16/27 caught vs 5/25). The decisive finding: 19 of 20
    remaining representation errors have a wrong vision `medium`
    field -- the bottleneck moved into the vision model, and the
    screenshot-of-text failure mode is eliminated where the medium
    is right. See RESULTS.md ("Phase 3").
16. **Vision-prompt revision v3 rejected.** A physical-context
    clause (photograph when a text-bearing surface shows depth or
    surroundings; text_screenshot only for flat head-on captures)
    was measured on the labeled 85: it fixed 1 record and broke 7
    (representation 76% -> 69%) -- the clause made the vision model
    more eager to call photographed covers and game screens
    `text_screenshot`. With v2's milder clause having failed on the
    same family, prompt wording is exhausted for this failure mode;
    it is a genuine vision limitation. v2 is restored as the live
    structured variant; the cascade stays the production path.
17. **Option 1 (capture-type question) falsified.** An isolated
    binary vision call -- "flat digital capture, or photograph of a
    physical object?" -- with a deterministic medium override
    (`capture_type.py`) was run on the labeled 85: pooled 89%,
    representation 74%, but the question itself answers
    `digital_capture` for 37 of 85 records whose truth is a photo,
    illustration, or render. The limitation is perceptual, not
    instructional; three question architectures have now failed on
    the same distinction. Review-always routing (Option 2) is the
    remaining path for the ambiguous family. See RESULTS.md
    ("Option 1").
18. **Option 2: review-always routing adopted.** `routing.py` routes
    to review on the existing 0.7 threshold OR a text-bearing signal
    in the description (measured on the labeled 85: catches 25/27
    errors vs 18/27 for the threshold alone). Full-collection
    burden: 156/218 (72%) -- 44 low-confidence, 112 text-bearing
    only. The two remaining silent errors are vision-limited with no
    text signal; one sits exactly at the 0.70 boundary (the queue
    rule is `< 0.7`). The trade is explicit: 20% burden / 9 silent
    errors vs 72% burden / 2. See RESULTS.md ("Option 2").
19. **Routing rule wired into the sorter and the review UI.**
    `routing.py` now exposes `route_reason(rec)` (None |
    "low_confidence" | "text_bearing"); `route(rec)` is reason is not
    None. `sort_humanoids.py` places a record in `_review\` when it is
    corrected OR `route_reason` is not None (previously: low
    confidence only). `review_ui.py` tags each queued record in the
    pane with `[queued: text-bearing]` or `[queued: low conf]` so the
    reviewer knows why it is in the queue. Verified: routing output
    unchanged (156/218), all three modules compile, and a DOM-stub
    harness of the UI's embedded script renders both queue tags.
20. **Edge-case suite generated (TODO item 9).** `generate_edge_cases.py`
    renders the adversarial edge cases with Mistral image generation,
    billed to the Mistral API credits (the Vibe subscription's image
    generations were exhausted; the included API credits were unused).
    The image-generation agent is created once and cached
    (`edge_case_agent.json`); each prompt is one conversations call and
    one file download. First run: 8/8 prompts, 0 errors, 7,217 tokens
    and 8 image generations total, images in `edge_cases/` (gitignored).
    Two live API gotchas found and documented in AGENTS.md: the REST
    conversations response nests entries under `outputs` (not
    `entries`), and the file download returns JPEG bytes despite
    `file_type: png` -- the script sniffs magic bytes. The suite is
    generated but not yet measured: the next step is running the 8
    images through the pipeline (describe -> classify -> sort) and
    comparing to the intended labels.
21. **Edge-case suite measured.** `measure_edge_cases.py` ran the
    production path (Pixtral describe -> Jev five facets, v4) on all
    8 and compared to the intended labels: 8/8 measured, 0 pipeline
    errors, pooled agreement 33/36 (92%) on unambiguous facets
    (contains_human 7/8, contains_robot 7/8, contains_android 7/7,
    primary_subject 6/6, representation 6/7). The known
    described-scene failure reappeared but hedged into the queue
    (contains_robot yes at 0.050 -- caught, not silent); the one
    silent error is the AI-generated portrait called `photograph` at
    1.000 -- the known perceptual limitation, and the taxonomy has no
    AI-generated class. Two taxonomy gaps surfaced (incidental
    humans; UI with a depicted subject have no clean class). The
    suite also exposed a routing brittleness: the preamble stripper
    in `routing.py` misses two of Pixtral's check-first line
    variants, so the word "terminal" in the preamble fires false
    text-bearing flags (2-3 of the suite's 4). Fixing it changes the
    measured 156/218 burden -- re-run `routing.py` on the full
    collection before adopting a change. See RESULTS.md
    ("Edge-case suite").
22. **Routing stripper fixed; taxonomy gaps documented.** Three
    stripper variants were measured on the full 218 against the 85
    labeled records: the old one-wording stripper (25/27 caught,
    156/218 burden), stripping every first line (23/27, 109/218 --
    strictly worse: two caught errors have first lines that affirm
    text, true signals), and stripping only negated check-lines
    (25/27, 135/218). The negation-only fix was adopted: same 25/27
    catches, burden 72% -> 62%; `routing_queue.json` regenerated
    (135 routed: 44 low-confidence, 91 text-bearing only). On the
    suite, the two false text-bearing flags now auto-accept and the
    true signals remain. The two taxonomy gaps (incidental humans;
    UI with a depicted subject) are recorded as design notes in
    `humanoid_taxonomy_v4.json` -- documented, not revised, per the
    v3/v5 lesson (n=1 synthetic evidence; revisit with the library
    collection). See RESULTS.md ("Routing stripper fixed").
23. **Stand-in library corpus fetched (partial).**
    `fetch_library_standin.py` pulls one Wikimedia Commons category
    per taxonomy class and writes `library_manifest.json` (committed;
    public data) as the stand-in ground truth: filename, category,
    Commons description, license, and depicts statements. First run:
    149 images across 5 of 6 categories (statue 28, humanoid_robot
    22, book_cover 36, human_photo 33, human_illustration 30;
    ui_screenshot 0) -- short of the 40/category target because
    Wikimedia rate-limited the IP (429s on bursts, then a 403
    robot-policy block that outlasted a 3-minute wait). The script is
    resumable: re-run it once the block lifts to top up all
    categories and add ui_screenshot. The depicts resolution came
    back empty -- undebugged because of the block (see AGENTS.md
    gotchas). The corpus is usable as-is for a first pipeline pass.
24. **Stand-in corpus measured (first pipeline pass).**
    `measure_library_standin.py` ran the production path (Pixtral
    describe -> Jev five facets, v4) on all 149 corpus images and
    compared to the labels the manifest category implies: 149/149,
    0 pipeline errors, pooled agreement 541/615 (88%) on unambiguous
    facets (contains_human 81%, contains_robot 97%,
    contains_android 94%, primary_subject 79%, representation 84%).
    book_cover and human_photo are perfect on scored facets; statue
    (72%) and humanoid_robot (73%) are weak exactly where the Commons
    categories are noisy labels (Category:Statues includes
    non-humanoid statues). Routing burden 60/149 (40%) -- lower than
    the personal collection's 62% -- concentrated in statue (20/28
    low-confidence) and humanoid_robot (17/22): the calibration
    hedges where the labels are unreliable. Results in
    `library_standin_results.json` (private, gitignored). See
    RESULTS.md ("Stand-in library corpus").
25. **Stand-in corpus review completed (60/60).** All 60 routed
    records were reviewed through `review_ui.py` (corpus results,
    `library_standin/`, taxonomy v4): 32 confirmed, 28 corrected.
    Per-facet accuracy on the reviewed set: contains_human 72%,
    contains_robot 95%, contains_android 88%, primary_subject 75%,
    representation 83%; pooled 248/300 (83%) -- accuracy on the hard
    cases, not overall; the 89 auto-accepted records remain
    unverified. The corrections cluster into three families: the
    android facet finally exercised (6 contains_android corrections
    in humanoid_robot -- the facet that never fired on the personal
    collection), non-humanoid statues (8 corrections; Category:Statues
    includes animal statues and architectural sculpture), and book
    covers with depicted content (5). The edge cases highlight the
    need for a richer ontology -- noted for a future revision, not
    acted on; the corpus now has 60 labeled records to measure a
    revision against. See RESULTS.md ("Stand-in library corpus").
    The Sample filter was also used on the corpus: a stratified
    sample of 27 fully confident unreviewed records (short of the
    30 target -- the corpus's confident pool per band/class is
    smaller) was computed and persisted at
    `library_review_sample_tmp.json` (gitignored); 27/27 reviewed:
    22 confirmed, 5 corrected -- miss rate 5/27 (19%, Wilson CI
    ~8-37%), corrections spread across categories (2 book covers,
    1 each human_photo, humanoid_robot, statue) rather than
    concentrated in representation. Confident-band accuracy is
    89-96% on every facet -- on this corpus, representation's
    confidence carries information (89% in the band vs 83% in the
    queue), unlike the personal collection where it carried none.
    81 of 149 corpus records are now labeled. A GUI confusion during
    the sample review (samples appearing not to load) was a stale
    browser tab, not a code bug: the server and front-end verified
    clean end to end (endpoints 200, DOM-stub harness rendered the
    sample correctly against live payloads).
26. **Corpus top-up complete (231 images, all 6 categories).** The
    Wikimedia block had lifted; `fetch_library_standin.py` topped up
    all categories: statue 40/40, humanoid_robot 40/40, book_cover
    40/40, human_photo 40/40, human_illustration 38/40,
    ui_screenshot 33/40 (was 0) -- 231 total, 9 short of the
    40/category target (11 downloads lost to HTTP 429s even at 20s
    spacing; resumable, re-run to top up the last 9 -- a 2026-09-24
    re-run was 429-blocked on the category listing itself, even after
    a 200s wait; resume in a later session). Two fetcher
    bugs found and fixed on this run: the resume path numbered new
    files from 1, colliding with existing manifest keys, so a re-run
    fetched nothing (fixed: numbering starts after the category's
    existing count); and the depicts resolution queried
    `pageprops.wikibase_item` -- the Wikidata Q-id link, empty for
    most files -- instead of the MediaInfo M-id route
    (`wbgetentities` with `sites=commonswiki` + file title). The
    corrected route works mechanically, but 0/231 corpus files carry
    P180 depicts statements: Commons structured-data coverage is
    uneven, so the manifest's category remains the only ground truth.
    The pipeline ran on the 82 new images: 231/231 measured, 0
    errors, pooled agreement 794/929 (85%) on unambiguous facets
    (contains_human 80%, contains_robot 96%, contains_android 93%,
    primary_subject 77%, representation 73%). Per category:
    book_cover and human_photo 100%, human_illustration 93%, statue
    75%, ui_screenshot 80% (its only scored facet is representation),
    humanoid_robot 68%. Routing burden 115/231 (50%) -- ui_screenshot
    routes 32/33 (22 text-bearing, a true signal for screenshots).
    See RESULTS.md ("Top-up").
27. **Second review pass complete (55/55; 136/231 labeled).** The 55
    unreviewed routed records from the top-up were reviewed through
    the UI: 25 confirmed, 30 corrected (45% agreement -- harder than
    the first batch's 83%, as expected: the batch is dominated by
    ui_screenshot (32) and humanoid_robot (11), the two noisy-label
    categories). Per-facet accuracy on the batch: contains_human 93%,
    contains_robot 96%, contains_android 89%, primary_subject 87%,
    representation 62%. Per category: book_cover 2/2,
    human_illustration 2/2, statue 4/8, ui_screenshot 15/32,
    humanoid_robot 2/11. The ui_screenshot number is the text-bearing
    routing signal earning its keep: it routes screenshots to review,
    where Jev is right only 47% of the time -- without the signal
    those would be silent errors. Cumulative: 136 of 231 records
    labeled (75 confirmed, 61 corrected, pooled 55% on routed
    records); correction families led by representation-only (20)
    and contains_android-only (12). The 95 auto-accepted records
    remain unverified; the confident-band sample bounds their miss
    rate at 19% (Wilson CI ~8-37%). See RESULTS.md ("Reviewed,
    second batch").
28. **First held-out taxonomy revision (v6 rejected, v7 adopted).**
    The Phase 6 protocol ran for real: v6 was authored from batch 1's
    31 corrections (sculpted works added to the depiction media -- the
    v4 enumeration omitted sculpting, so statues of humans answered
    no/none; the android boundary sharpened to require a human-passing
    appearance; text_screenshot narrowed so covers classify by their
    surface) and measured on batch 2's 55 labeled records, which the
    revision never saw (`measure_taxonomy_v6.py`, Jev calls only).
    v6: pooled 87% vs v4's 85% -- the entity changes worked (android
    100%, was 89%; contains_human 96%; primary_subject 91%) but the
    text_screenshot narrowing regressed representation 62% -> 49%,
    breaking 5 records v4 had right and fixing 0: the v3 lesson in
    mirror image, both directions of rewriting that class are now
    measured negatives. v7 (v6's entity changes + v4's representation
    wording, a composition of measured components) re-measured on the
    same batch: pooled 89% vs 85%, fixes 10 / breaks 2 (sign test
    ~p=0.04, at the edge of the noise floor), android 100%, and the
    routing property holds (21 of 22 errors caught by the full rule;
    the one silent is the known representation family). v7 is adopted
    for the stand-in corpus (set `TAXONOMY=humanoid_taxonomy_v7.json`
    on corpus runs; script defaults stay at v4, the personal
    collection's measured best). A live run-to-run variance data point
    fell out: identical v6 criteria, two runs, same choices, 14 vs 16
    threshold-routed -- confidences drift a few points run to run
    (TODO item 6). See RESULTS.md ("Held-out taxonomy revision").
29. **v7 re-measured on the personal collection; default switched.**
    `measure_taxonomy_v7_personal.py` ran v7 on the personal
    collection's 85 labeled records (Jev calls only): pooled 389/425
    (92%) vs v4's 388/425 (91%) -- fixes 3, breaks 2, inside noise,
    no regression; contains_android 100% (was 99%). Combined with the
    corpus's held-out win, v7 is measured on both collections and is
    now the default taxonomy (`pilot_humanoid.py`, and
    `measure_library_standin.py` through it); `TAXONOMY` still
    selects any version. See RESULTS.md ("Held-out taxonomy
    revision", Adoption).
30. **Corpus top-up completed (240 images, 40 per category).** The
    last 9 fetched (human_illustration 38 -> 40, ui_screenshot
    33 -> 40), 0 errors, at the same 20s DELAY. The first re-run
    attempt today exited 0 and fetched nothing -- the category
    listing was still 429-blocked (the script catches and continues,
    so it looks like a clean no-op); a second run ~10 minutes later
    succeeded. The corpus is complete at the 40/category target.
    The 9 new images are unmeasured and unlabeled; they join at the
    next pipeline re-run (next steps item 2). See RESULTS.md
    ("Top-up complete").
31. **Production re-run with v7 complete (240/240, 0 errors).**
    `measure_library_standin.py` re-ran the full pipeline (fresh
    descriptions, v7 facets) on all 240 images. The v4 results were
    moved aside to `../Ontology_private_backup/v4_corpus_run_2026-09-24/`
    (the script skips records already in the results file); the 136
    manual corrections were merged back into the new results file
    afterwards, so the review state survives. Pooled agreement
    857/960 (89%) vs v4's 794/929 (85%): contains_human 86% (was
    80%), contains_robot 95% (was 96%), contains_android 100% (was
    93%), primary_subject 86% (was 77%), representation 71% (was
    73%). Routing burden 106/240 (44%, was 115/231 = 50%).
    Caveat: taxonomy, descriptions, and the 9 new images all changed
    at once -- the held-out batch already isolated the taxonomy
    effect (89% vs 85%); this is the production confirmation. The 9
    top-up images are measured but unlabeled. See RESULTS.md
    ("Production re-run with v7").
32. **v7 vs human ground truth on the corpus (no API calls).** The
    merged corrections allow a direct comparison on the same 136
    labeled records: v7's fresh answers 607/680 facets (89%) vs v4's
    stored 585/680 (86%). Per facet: contains_human 90% vs 85%,
    contains_android 100% vs 90%, primary_subject 87% vs 84%,
    representation 74% vs 76% (only dip, inside noise). The held-out
    result holds against real ground truth. Next: review the 12
    unreviewed routed records (94 of the 106 routed were already
    reviewed in the two batches; their corrections came back in the
    merge) -- review UI running with v7 taxonomy and a temp sample
    path. See RESULTS.md ("Production re-run with v7").
33. **Third review pass complete (12/12; 148/240 labeled; queue
    empty).** The 12 unreviewed routed records from the v7 re-run
    were reviewed through the UI (v7 taxonomy, temp sample path): 8
    confirmed, 4 corrected -- v7 agreed with the reviewer on 56/60
    facets (93%), far above the v4 batches' 55% on their hard cases.
    Route reasons: 10 low-confidence, 2 text-bearing. Cumulative:
    148 of 240 records labeled (83 confirmed, 65 corrected); v7's
    fresh answers agree with all human corrections on 663/740 (90%).
    The review queue is empty. Next: the next held-out taxonomy
    revision, authored from the correction families (the same
    abduction loop as v6 -> v7). See RESULTS.md ("Production re-run
    with v7", third batch).

## Where things live

| Thing | Path |
|---|---|
| Pilot plan and results write-up | `Images/LIBRARY.md` |
| Run write-up (both corrections, re-run, taxonomy v2) | `Images/RESULTS.md` |
| Pilot taxonomy v4 (current, adopted) | `Images/humanoid_taxonomy_v4.json` |
| Taxonomy v7 (adopted for the stand-in corpus; first held-out revision) | `Images/humanoid_taxonomy_v7.json` |
| Taxonomies v1-v3, v5, v6 (history; v3, v5, and v6's text_screenshot narrowing measured rejections) | `Images/humanoid_taxonomy_v*.json` |
| Held-out revision authoring + measurement (public) | `Images/author_taxonomy_v6.py`, `Images/author_taxonomy_v7.py`, `Images/measure_taxonomy_v6.py` |
| Held-out revision run records (private, gitignored) | `Images/taxonomy_v6_batch2_results.json`, `Images/taxonomy_v7_batch2_results.json` |
| Pilot script (public; `TAXONOMY` env var selects version, v4 default) | `Images/pilot_humanoid.py` |
| Sorter (public) | `Images/sort_humanoids.py` |
| Review UI (public; localhost web app) | `Images/review_ui.py` -> http://localhost:8765 |
| Phase 2: Pixtral-direct baseline (public) | `Images/baseline_pixtral_direct.py` |
| Phase 2: three-system comparison (public) | `Images/baseline_compare.py` |
| Phase 3: structured vision state (public) | `Images/structured_vision.py` |
| Option 1: capture-type experiment (public, falsified) | `Images/capture_type.py` |
| Option 2: routing rule (public) | `Images/routing.py` |
| Edge-case generator (public) | `Images/generate_edge_cases.py` |
| Edge-case measurement (public) | `Images/measure_edge_cases.py` |
| Library stand-in fetcher (public) | `Images/fetch_library_standin.py` |
| Library stand-in measurement (public) | `Images/measure_library_standin.py` |
| Library stand-in manifest (public; the stand-in ground truth) | `Images/library_manifest.json` |
| Library stand-in images (private, gitignored) | `Images/library_standin/` |
| Library stand-in results (private, gitignored) | `Images/library_standin_results.json` |
| Edge-case images (private, gitignored) | `Images/edge_cases/` |
| Edge-case run records + agent cache (private, gitignored) | `Images/edge_case_results.json`, `Images/edge_case_pipeline_results.json`, `Images/edge_case_agent.json` |
| Pixtral-direct results (private, gitignored) | `Images/baseline_pixtral_direct_results.json` |
| Structured vision results (private, gitignored) | `Images/structured_vision_results.json` |
| Routing queue (private, gitignored) | `Images/routing_queue.json` |
| Sorted folder tree (private) | `PICTURES_DIR\Humanoids\` (+ `_review\`) |
| Pilot per-image results (private, gitignored) | `Images/humanoid_pilot_results.json` |
| Original-run results (private, gitignored) | `Images/image_human_results.json` |
| Confident-band sample (private) | `../Ontology_private_backup/confident_sample_v1.json` |
| Baselines (private) | `../Ontology_private_backup/` (`rerun_v1_2026-09-23/` = old prompt; `2026-09-23_criteria_v1_run/`; `2026-09-23_criteria_v2_reviewed/` = reviewed ground truth; `2026-09-23_taxonomy_v3_run/`, `..._v4_run/`, `..._v5_run/`) |
| Review queue printout | rerun `python pilot_humanoid.py` (instant; resumable) |

## Next steps, in order

1. ~~**Integrate the routing rule into the sorter and review UI.**~~
   Done (2026-09-23, commit a884d95): `route_reason` is wired into
   `sort_humanoids.py`'s `_review\` placement and the review UI's
   queue tags; the 135 routed records are walkable.
2. **A real library collection.** The 218-image set is personal
   photos; the pipeline, taxonomy, and review UX are ready for
   library material, where the android facet and the held-out
   revision protocol (LIBRARY.md Phase 6) actually apply. A stand-in
   now exists, complete at 240 Commons images across all 6
   categories (40 per category after the 2026-09-24 top-up;
   `library_standin/`, manifest committed), fully re-run with v7
   (240/240, 0 errors, pooled 857/960 = 89% vs v4's 85%; routing
   burden 44%), with three completed review passes (60/60, 55/55
   under v4, then 12/12 under v7: 83 confirmed, 65 corrected; v7
   agreed with the reviewer on 93% of the third batch). 148 records
   are labeled (the corrections are merged into the v7 results; v4's
   raw answers are backed up at
   `../Ontology_private_backup/v4_corpus_run_2026-09-24/`). The
   first held-out taxonomy revision is done: v7 adopted and now the
   default (pooled 89% vs v4's 85% on the corpus's held-out batch,
   92% vs 91% on the personal collection, android 100% on both; see
   RESULTS.md "Held-out taxonomy revision"). The review queue is
   empty. Next: the second held-out taxonomy revision, authored from
   the 65 corrections' families and measured held-out on a fresh
   batch. Depicts annotation is a dead end for this corpus: 0/231
   files carry P180 statements.
3. ~~**Measure the edge-case suite.**~~ Done (2026-09-23): 8/8
   measured, pooled agreement 33/36 (92%); see RESULTS.md
   ("Edge-case suite"). Residuals: the AI-generated portrait is
   pixel-indistinguishable from a photograph (perceptual, no taxonomy
   class), and the routing preamble stripper is brittle (AGENTS.md
   gotchas).
4. ~~**Decide on the routing preamble stripper.**~~ Done
   (2026-09-23): negation-only stripping adopted -- same 25/27
   catches, burden 156 -> 135 of 218 (72% -> 62%). See RESULTS.md
   ("Routing stripper fixed").

The android question is settled by the review: the collection
contains no androids (the Twiki image is a robot, not an android).
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
