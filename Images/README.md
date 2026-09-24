<img width="1900" height="1139" alt="Twiki and Buck" src="https://github.com/user-attachments/assets/0be69cb5-437b-4d33-b283-10360b4fdd15" />
"A visual ontology, Twiki. That is where we are going!"<br>
"Yes, Buck, and Jev is going to help us get there."<br><br>

# Images + Jev
Goal: a pipeline that auto-classifies digitized image collections
against a revisable taxonomy, routing uncertain items to human review.

See `LIBRARY.md` for the project plan for the library use-case.

Since we work in a university library, making a system for auto-classifying images according to some taxonomic scheme is a real use-case for us.

Classifying images with [Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev),
TypeSafe AI's "System One" decision model.

> **Vision describes, Jev decides.**
>
> Jev is text-only for the time being: it classifies a text *state* against typed questions.
> It cannot see pixels. So each image is first described by a vision model
> (Mistral Pixtral), and Jev then classifies that description. This is the
> same cascade pattern as the ticket ontology, with a vision model as the
> front-end.

Note: Once Jev becomes multimodal, we can shorten the pipeline and quite likely acheive amazing speed and economy.

Also note that while Jev is ridiculously cheap, Pixtral is also low cost, so on the whole the project is already economical as-is.

But being able to do this just with a Jev-like model would certainly be a game-changer, so we are holding our breath for that.

## The empirical case

Two collections, in order of appearance:

- **A personal photo collection (218 images, private).** The
  development corpus: real photographs of people, statues, robots,
  posters, and screenshots from one folder. It is where the
  pipeline, taxonomy, and review UX were built and measured
  (85 of 218 records labeled by review). Filenames and descriptions
  are private and never appear in public docs.
- **A stand-in library corpus (240 Wikimedia Commons images,
  public).** The empirical case for the library use-case: one
  Commons category per taxonomy class (statue, humanoid_robot,
  book_cover, human_photo, human_illustration, ui_screenshot),
  fetched by `fetch_library_standin.py` with a committed manifest
  (`library_manifest.json`) as the stand-in ground truth. It is
  digitized, catalog-like material -- covers, statues, illustrations,
  screenshots -- the closest available analog to a real library
  image collection. 136 of the 231 records measured so far are
  labeled by review (the 2026-09-24 top-up added 9 unmeasured
  images); the
  Commons categories are noisy labels, so review-corrected records,
  not the categories, are the measured ground truth.

The real target remains an actual library collection with a
cataloger (see `LIBRARY.md` Phase 0); both stand-ins exist to have
labeled material before that arrives.

## What this directory is

A growing sub-project of the Ontology + Jev work. The task that started it all: sort a folder
of images by whether they contain a human. The pipeline is:

```
Mistral Pixtral describes the image (checks for text first, states the medium, then a short description)
  -> Jev answers the five taxonomy facets (contains_human, contains_robot,
     contains_android, primary_subject, representation) with calibrated confidence
  -> routing.py flags low-confidence or text-bearing records for human review
```

The vision model is the "eyes"; Jev is the decision maker. Jev returns a
calibrated probability, so ambiguous cases (statues, cartoons, posters)
are flagged with low confidence rather than forced into an answer.

## What Jev contributes

Jev's role here is the **calibrated decision layer, not perception**. The
vision model does the perceptual work; Jev decides with a probability.
The Phase 2 baseline measured this directly on 85 labeled records
(`baseline_compare.py`): the cascade (Pixtral + Jev) reaches 91% pooled
accuracy with ECE 0.038 and catches 16/27 errors; Pixtral answering the
same five facets directly reaches 80% with ECE 0.150 and catches 0/45 --
it reports >= 0.9 confidence on everything, right or wrong. Jev is less
accurate than the vision model on any single answer and more trustworthy
overall, because it is the only component that knows what it does not
know.

What Jev genuinely adds:

- **Calibrated confidence.** Pixtral returns free text; Jev returns a
  probability. That probability is what makes routing possible: the 0.7
  threshold plus a text-bearing signal (`routing.py`) catches 25/27
  errors at a ~50% review burden, where the vision model's own
  confidence catches none.
- **Typed, deterministic output.** A structured choice per facet with
  probabilities -- no parsing, no format drift, directly usable in code.
- **Criteria-as-state.** The decision rules are data
  (`humanoid_taxonomy_v7.json`), not code. Eight revisions (v1-v8) were
  authored and measured without touching the pipeline. v7 -- the first
  held-out-validated revision (LIBRARY.md Phase 6): authored from one
  review batch, measured on a batch it never saw -- beats v4 on the
  stand-in corpus (89% vs 85%, contains_android 100%) and matches it on
  the personal collection (92% vs 91%). Five
  rejections are documented, two as the v3/v5 lesson: de-hedging
  without accuracy gains manufactures silent errors, and v6's
  text_screenshot narrowing showed the same failure in mirror image --
  the regression was invisible at authoring time, which is why the
  held-out protocol exists. The result also held in production: the
  full-corpus re-run with v7 reaches 89% pooled (v4's run: 85%) and
  93% agreement with the human corrections on all 240 labeled records
  (v4's stored answers: 86%). The latest rejection, v8 (a
  subject-decides clause for representation, authored from the
  statue-family corrections), measured inside noise on the held-out
  batch (fixes 5 / breaks 3, three of the eight changes pure
  run-to-run variance): the loop's bar is measured gains, not
  plausible criteria. The third revision, v9 (the clause refined,
  text_screenshot extended to software interfaces, and a
  background-people clause), was measured under a split-half
  protocol -- ground truth is complete at 240/240, so the held-out
  split became deterministic (md5(filename) parity: authoring half
  132, measurement half 108, every correction family in both
  halves) -- and adopted: pooled 96% vs v7's 94% on the measurement
  half, representation 89% vs 80%, fixes 13 / breaks 4, neutral on
  the personal collection (91% vs 91%): v9 is now the default.
- **A real check on the LLM.** Pixtral verifies; Jev falsifies. Its
  dissent is the signal: every taxonomy gap found in this project
  (android boundaries, non-humanoid statues, representation splits)
  surfaced first as a Jev low-confidence cluster, and the review
  corrections cluster in the same families.

Where it is thin:

- **Jev never sees the image.** It sees a short text description, so its
  understanding is bounded by that summary -- and the residual errors
  live exactly there: 19 of 20 remaining representation errors have a
  wrong `medium` field in the description. The decision layer is nearly
  exhausted; the frontier is the interface.
- **Jev inherits vision errors.** A screenshot-of-text image was the
  proof: Pixtral transcribed text as if it were a scene, and Jev said
  "yes" because it only saw the description. (Fixed 2026-09-23 with a
  check-text-first vision prompt; the described-scene gap in Jev's
  criteria is measured and documented in RESULTS.md.)
- **The check is not complete.** ~19% of Jev's confident answers were
  wrong in the confident-band sample (5/27, Wilson CI ~8-37%), and
  `representation`'s hedging carries no information (~80% accurate at
  every confidence level). A human stays in the loop for the ambiguous
  family.

The epistemic summary: accuracy came not from a better judge, but from
institutionalizing disagreement between a perceiver that verifies and a
decider that falsifies. Once Jev becomes multimodal, the interface
disappears -- and the open question is whether the calibration survives
direct perception as well as it survives the paraphrase.

> **From scaffolding to measured system.** The directions listed here
> when this section was first written are now done and measured: the
> single yes/no became a five-facet taxonomy (v7, the first
> held-out-validated revision, is the default); the multiple-questions
> pass is the production path; calibration-driven routing is
> `routing.py` (threshold + text-bearing signal, wired into the sorter
> and the review UI); and the criteria-as-ontology loop ran seven
> times (v1-v7, four rejections documented), producing one
> held-out-validated revision. What remains is the corpus pipeline
> re-run with v7 once the Wikimedia rate-limit block lifts, and the
> real library collection itself. See `TODO.md` and `STATUS.md`.

## Files

```
classify_images.py                  -- resumable pipeline (vision -> Jev)
summarize_results.py                -- regenerates the summary from the JSON
image_human_results.sample.json     -- anonymized sample of the record format
image_human_results.json (private)  -- full per-image records (gitignored)
image_human_summary.txt (private)   -- clean sorted list, real filenames (gitignored)
fix_false_positive.py               -- corrects one record, preserving raw output
copy_humans.py                      -- copies human-classified images to a subfolder
RESULTS.md                          -- writeup of the run and findings
LIBRARY.md                          -- project plan for the library use-case
TODO.md                             -- outline of the fuller multi-question project
STATUS.md                           -- session pickup notes: where we are, next steps
humanoid_taxonomy_v1-v3, v5.json    -- pilot taxonomy history (v3 and v5: measured rejections)
humanoid_taxonomy_v4.json          -- pilot taxonomy v4 (current): depiction in any
                                     medium counts; robots need a being-like form
pilot_humanoid.py                  -- re-classifies the stored descriptions
                                     (TAXONOMY env var selects the version)
sort_humanoids.py                  -- copies images into a sorted Humanoids tree
review_ui.py                       -- localhost review app: confirm/correct classifications
humanoid_pilot_results.json (private) -- pilot per-image results (gitignored)
generate_edge_cases.py             -- generates the adversarial edge-case suite
                                     (Mistral image generation, API credits)
edge_cases/ (private)              -- generated edge-case images (gitignored)
measure_edge_cases.py             -- runs the pipeline on the edge-case suite and
                                     compares to the intended labels
edge_case_pipeline_results.json (private) -- measurement records (gitignored)
fetch_library_standin.py          -- fetches a stand-in library corpus from
                                     Wikimedia Commons (categories are data)
library_manifest.json             -- stand-in ground truth: category, description,
                                     license per image (committed; public data)
library_standin/ (private)        -- fetched corpus images (gitignored)
measure_library_standin.py       -- runs the pipeline on the stand-in
                                     corpus and compares to the manifest
library_standin_results.json (private) -- measurement records (gitignored)
```

## Running it

Requires `MISTRAL_API_KEY` (vision) and `TYPESAFE_API_KEY` (Jev), plus
`PICTURES_DIR` pointing at the folder of images to classify.

```bash
export PICTURES_DIR="C:/path/to/your/pictures"
python classify_images.py   # processes all images, saves incrementally
python summarize_results.py # prints the sorted summary
python pilot_humanoid.py    # 5-facet classification (TAXONOMY selects the version)
python sort_humanoids.py    # copies images into a sorted Humanoids tree
python review_ui.py         # localhost review app: http://localhost:8765
python generate_edge_cases.py  # generates the edge-case suite into edge_cases/
```

## Results

215 images classified: 73 contain a human, 142 do not, 0 errors. 87%
at 0.9+ confidence. The 13 sub-0.7-confidence cases are all
illustrations, statues, cartoons, or posters rather than photos of real
people -- Jev's calibration surfaces the "real human vs. depiction"
boundary. See `RESULTS.md` for the full writeup.

**Re-run (2026-09-23):** the pipeline was re-run on 218 images with
the fixed vision prompt: review queue 52/218 (24%, down from 37%),
representation hedges halved, and both known screenshot-of-text
false positives caught at the vision layer. The humanoid pilot and
the sorted verification tree are described in `STATUS.md`.

**Stand-in corpus (2026-09-23/24):** a 240-image Wikimedia Commons
corpus (`library_standin/`, manifest committed, all 6 categories,
complete at 40 per category after the 2026-09-24 top-up), fully
re-run with v9: 240/240 measured, 94%
agreement against the category-implied labels (v7's run: 89%); the routed records
reviewed in four passes (60/60 and 55/55 under v4, 12/12 under v7, then the 72 remaining auto-accepted records confirmed under v7: 172 confirmed, 68
corrected overall); all 240 records
labeled (95.1% facet agreement with the human corrections under v9). See `RESULTS.md` ("Stand-in library corpus").

## Caveats

- **No ground truth.** The split is Jev's judgment; accuracy is
  unmeasured. A manual audit of a sample would establish real accuracy.
- **The vision model is the bottleneck.** Jev only sees the short text
  description, so a mis-description propagates.
- **"Human" is fuzzy.** Statue vs. person, cartoon vs. photo. The
  criteria could be tightened or split into sub-labels.
- **No baseline.** We did not compare against a dedicated image
  classifier.

## Privacy

The classified images are a personal photo collection, so the per-image
data is kept private:

- `image_human_results.json` and `image_human_summary.txt` contain
  real filenames and vision-model descriptions of personal photos.
  They are **gitignored** and never pushed; only
  `image_human_results.sample.json` (anonymized records) is committed.
- In `RESULTS.md`, filenames are replaced with anonymous IDs
  (`image_01`, `image_02`, ...); the mapping is not published.
- Scripts take the image folder from the `PICTURES_DIR` environment
  variable rather than a hardcoded local path.

If you re-run the pipeline on your own photos, keep the results file
out of any public repository the same way.

Note: this protects the *current* state of the repository. Data
committed in earlier revisions remains in git history until the history
is rewritten.

See the parent `../README.md` for the broader Ontology + Jev project.
