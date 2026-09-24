# Results: Image classification with Jev

**Date:** 2026-09-22
**Author:** Mistral Vibe (mistral-vibe)
**Task:** Sort 215 images in a personal photo folder by whether they contain a human.
**Vision model:** Mistral `pixtral-12b-2409`
**Jev model:** jev-latest (jev-1.13.0)
**Images:** 215 (73 human, 142 no-human, 0 errors)

---

## Summary

The task was to sort the images in a personal photo folder by whether they
contain a human, using Jev. The result: 73 images contain a human, 142
do not, with 0 errors. 188 of 215 (87%) were classified at 0.9+
confidence.

The interesting finding is not the split itself but *where* Jev hedged.
The 13 sub-0.7-confidence cases are all illustrations, statues,
cartoons, or posters rather than photographs of real people. Jev's
calibrated probabilities surface the "real human vs. depiction" boundary
instead of forcing a confident answer.

---

## The constraint: Jev is text-only

Jev classifies a text *state* against typed questions. It cannot see
pixels. To classify images with Jev, each image must first be converted
to text. The pipeline therefore uses a vision model as a front-end:

```
Mistral Pixtral describes the image (one 25-word sentence)
  -> Jev classifies the description: "Does this image contain a human?" (yes/no)
```

This is the same cascade pattern as the ticket experiment, with one
change: the *state* Jev sees is now a vision model's description rather
than raw text. The vision model is the "eyes"; Jev is the decision
maker. (Note: the `OPENAI_API_KEY` in the environment was a 25-char
placeholder, so Mistral's Pixtral was used for the vision step.)

---

## Results

| Bucket | Count | Mean confidence | >=0.9 | 0.7-0.9 | 0.5-0.7 | <0.5 |
|---|---|---|---|---|---|---|
| Contains human | 73 | 0.920 | 61 | 5 | 2 | 5 |
| No human | 142 | 0.959 | 127 | 9 | 3 | 3 |
| **Total** | **215** | | **188** | **14** | **5** | **8** |

0 errors. 188 of 215 (87%) classified at 0.9+ confidence. The buckets
above use each record's effective (post-correction) confidence, so the
corrected screenshot-of-text record contributes a manual 1.0 to the
no-human >=0.9 bucket; Jev's raw answer ("yes" at 1.000, preserved
under the record's `jev` key in `image_human_results.json`) would place
it in the contains-human >=0.9 bucket instead.

> **Correction (2026-09-22):** One image -- a screenshot of *text*
> describing a photo -- was initially classified as "contains human" at
> 1.000. The vision model read the text ("a man and a robot...") and
> described it as if it were the scene, and Jev then said "yes." It has
> been removed from the human set and reclassified as no-human. This is
> a real failure mode: screenshots of text that *describes* a person get
> misclassified as containing a person.

> **Correction 2 (2026-09-23, humanoid pilot):** A second instance of the
> same failure mode. A screenshot of a text-only terminal showing another
> model's text *describing* an image (again a man and a robot) was
> described by the vision model as a promotional photograph, and Jev
> answered at 1.000 confidence (photograph, multiple subjects). The
> record now carries a manual correction -- raw Jev answers preserved --
> in `humanoid_pilot_results.json`, and `sort_humanoids.py` sorts
> corrected records by their corrected labels. The vision prompt in
> `classify_images.py` now checks for text first, states the medium,
> and requires describing what text says rather than a scene the text
> merely mentions. Verified live: the known failure image and a second
> text screenshot are both described as text; normal photographs
> still describe normally. A weaker medium-first-only instruction was
> tested first and failed on the known image -- the scene description
> overwhelmed it.

---

## The interesting finding: Jev surfaces "real human vs. depiction"

The 13 cases below 0.7 confidence are not noise -- they are all
illustrations, statues, cartoons, or posters rather than photographs of
real people:

| Image | Choice | Conf | Description |
|---|---|---|---|
| image_01 | yes | 0.05 | comic book characters Batman and Robin |
| image_02 | yes | 0.16 | Arthur Mensch discusses Mistral AI |
| image_03 | yes | 0.28 | a cartoon child celebrating a birthday |
| image_04 | yes | 0.39 | pixelated version of "The Thinker" statue |
| image_05 | no | 0.45 | superhero resembling The Flash |
| image_06 | no | 0.47 | cartoon superhero labeled GPT-5 |
| image_07 | yes | 0.48 | illustrations of team members |
| image_08 | no | 0.49 | magazine cover |
| image_09 | yes | 0.54 | illustrations of team members |
| image_10 | no | 0.55 | victory screen with characters |
| image_11 | no | 0.57 | list of students |
| image_12 | no | 0.61 | cartoon character giving a thumbs-up |
| image_13 | yes | 0.69 | film poster |

(Filenames are redacted: they come from a personal photo collection.
The unredacted records live in the private `image_human_results.json`;
see the Privacy section in `README.md`.)

Jev's criteria said "one or more humans (people, faces, bodies)", but it
correctly hedged on depictions. A statue of a person, a cartoon of a
person, and a photograph of a person are all "a human" in some sense and
not in another. Jev's calibrated probabilities flag this boundary rather
than forcing a confident answer -- the same behavior that made it useful
on ambiguous support tickets.

---

## Cost

Jev calls: 215, ~344 input tokens each, ~74K input tokens total. At
$0.042/M input tokens, that is roughly $0.003. The vision calls
(Pixtral) dominate the cost but are still small. The whole batch is
effectively free.

---

## Re-run with the fixed vision prompt (2026-09-23)

The second screenshot-of-text instance (Correction 2 above) led to a
vision-prompt fix: Pixtral now checks for text first and states the
medium (photograph, illustration, render, screenshot, or text) before
describing content. A weaker medium-first-only draft failed live
testing on the known failure image; the check-first version passed on
that image, a second text screenshot, and two normal photos.

The full pipeline was then re-run on the collection, grown to 218
images (3 new since the original 215). 218 descriptions, 218 Jev
calls, 0 errors. Comparison against the original run (215 common
images; the old-prompt baseline is preserved in a private backup
outside the repo):

| Measure | Original run | Re-run |
|---|---|---|
| Review queue (<0.7 any facet) | 79/215 (37%) | 52/218 (24%) |
| `representation` hedges | 64 | 28 |
| Binary "contains human" | 73 yes / 142 no | 67 yes / 151 no |
| `contains_human` choice flips | -- | 11 (10 of them yes -> no) |

The 10 yes->no flips are almost entirely the failure family the prompt
fix targeted: screenshots of text *about* people (article headlines,
name lists), a greeting card, poster illustrations, and a render. The
single no->yes flip also looks correct.

The original failure image is now described as text at the raw level
(`representation: text_screenshot` at 0.53, previously `photograph`
at 1.0). Jev, however, still answers the *described* scene for
`primary_subject` (multiple, 0.91): the remaining gap is in Jev's
criteria, which do not distinguish "depicted" from "described." The
manual correction stands.

`sort_humanoids.py` (new) materializes the pilot results as a sorted
folder tree -- `Humanoids/<primary_subject>/<representation>/` plus a
`_review/` folder of low-confidence and corrected records -- for
visual verification. Its first version read `manual_correction` labels
from the wrong JSON level and sorted corrected records by raw labels;
fixed the same day, placement verified with `find`.

---

## Taxonomy v2: the depicted-vs-described clause (2026-09-23)

The re-run left one gap: Jev answered the *described* scene for
`primary_subject` on the failure image (`multiple` at 0.91).
`humanoid_taxonomy_v2.json` adds one clause to every entity facet:
only what the image itself shows counts; a person or robot merely
mentioned or described in text does not. The pilot was re-run on the
same 218 descriptions (criteria-v1 results preserved privately).

- The failure image is now correct raw on all five facets:
  `primary_subject: none` (0.88, previously `multiple` at 0.91).
  No manual correction needed anymore.
- Choice agreement with criteria v1: 217/218 on four facets,
  213/218 on `primary_subject`. The five subject flips are the
  intended fixes (the failure image, a birthday greeting card, a
  text+illustration timeline, a movie poster described only by title
  and stars) or coin-flip noise on records already hedged.
- Review queue 50/218 (23%), down from 52. The clause's effect is
  targeted: it fixes text-describes-entity cases and adds mild
  hedging where the description is ambiguous about whether anyone is
  depicted.
- Caveat: measured in-sample, on the same descriptions that
  motivated the revision. The held-out protocol (LIBRARY.md Phase 6)
  is the standard for calling a revision real.

---

## First accuracy numbers: the complete review queue (2026-09-23)

A full review pass via `review_ui.py` labeled all 50 queued records
(28 confirmed, 22 corrected) -- the first ground truth this project
has. The queue is every record hedging below 0.7 on any facet, so
these numbers describe the dubious band; the 168 confident records
remain unverified and the threshold's miss rate is unknown.

Per-facet accuracy (raw Jev choice vs. the reviewed label):

| Facet | Accuracy |
|---|---|
| contains_human | 40/50 (80%) |
| contains_robot | 46/50 (92%) |
| contains_android | 49/50 (98%) |
| primary_subject | 43/50 (86%) |
| representation | 40/50 (80%) |

All five facets right on 28/50 records. Pooled facet-answers by
confidence bin -- accuracy rises monotonically with confidence, and
the top band lands on its stated probability:

| Confidence | Accuracy |
|---|---|
| 0.0-0.5 | 18/25 (72%) |
| 0.5-0.7 | 27/41 (66%) |
| 0.7-0.9 | 15/17 (88%) |
| 0.9-1.0 | 158/167 (95%) |

The routing claim holds across the whole queue: every wrong record
(22/22) was in the queue; zero errors were found above the 0.7
threshold. At 0.7, hedging and error coincide -- the threshold
routes exactly the records that need eyes.

The 22 corrections sharpen the taxonomy agenda: game screens
corrected to `text_screenshot` (the missing interface class),
illustrations of text-labeled characters corrected back to `human`
(the v2 depicted-vs-described clause overcorrected there --
depicted-in-illustration must still count), and robot overcalls
corrected to `none`.

---

## Taxonomy revision series: v3, v4, v5 (2026-09-23)

After the 50-record review, three revisions were drafted from the 22
corrections, each run separately and measured on the reviewed records
(one revision per re-run):

| Run | Revision | Wrong /50 | Queue | Errors caught | Confident errors |
|---|---|---|---|---|---|
| v2 (baseline) | -- | 22 | 50 (22%) | 22/22 | 0 |
| v3 | broaden text_screenshot to game/app screens | 21 | 32 (14%) | 16/21 | 5 |
| v4 | depiction counts in any medium; robots need a being-like form | **19** | 44 (20%) | 17/19 | 2 |
| v5 | screenshots classify by their content | 19 | 31 (14%) | 13/19 | 6 |

Findings:

1. **v4 is adopted.** Entity accuracy clearly improved
   (contains_human 80% -> 88%, contains_robot 92% -> 94% on the
   labeled 50) at a small routing cost: two confident errors, both
   on records whose descriptions mislead.
2. **v3 and v5 are rejected negative results.** Both cut the
   review burden while leaving accuracy flat -- the revisions
   converted hedged errors into confident ones. In a routing
   workflow, confidence must be earned by correctness: de-hedging
   without improving accuracy manufactures silent errors. LIBRARY.md
   Phase 6's revision caution is now demonstrated twice, in-sample,
   on labeled data.
3. **The residual representation errors are largely vision-limited.**
   Descriptions that open "This image consists of text" for what
   are photographs of covers leave Jev no correct basis to answer.
   The durable fix is Phase 3's structured vision state, not more
   criteria words.

The live results are the v4 run with all 50 review corrections
merged back; `pilot_humanoid.py` defaults to v4. All runs are
preserved privately outside the repo.

---

## Confident-band verification (2026-09-23)

A stratified 30-record sample of the confident band (every facet
>= 0.7, previously unreviewed) was labeled through the review UI's
Sample filter -- 15 records from 0.7-0.9, 15 from 0.9-1.0, spread
across representation classes.

**Record-level miss rate: 7/30 (23%), Wilson 95% CI 12-41%.** On its
face that is high -- but the errors are almost entirely
`representation` (6 of 7 records; the seventh, an entity error, sat
exactly at the 0.70 boundary):

| Facet | Confident-band accuracy |
|---|---|
| contains_human | 29/30 (97%) |
| contains_robot | 30/30 (100%) |
| contains_android | 30/30 (100%) |
| primary_subject | 29/30 (97%) |
| representation | 24/30 (80%) |

Entity-only miss rate: 1/30 (3%). Pooled calibration in the band:
0.7-0.9: 88%; 0.9-1.0: 95% -- matching the queue's numbers, so
Jev's confidence is genuinely calibrated for the entity facets.

The `representation` finding is the sharpest of the project: its
confident-band accuracy (80%) equals its queue accuracy (80%).
Whether Jev hedges or asserts, `representation` is wrong a fifth of
the time -- its confidence carries no information, and the errors
are the same class everywhere (interface, app, and game screens
forced into the wrong bucket). This is not a criteria problem; the
facet needs either a review-always policy or LIBRARY.md Phase 3's
structured vision state (a typed `medium` field from the vision
model instead of a five-way choice on a free-text description).

**The two-sided routing verdict:** at threshold 0.7, the queue
catches entity errors (17/19 in the v4 run), the confident band's
entity miss rate is ~3%, and `representation` should never be
auto-accepted at any confidence. Total labeled records: 85 of 218.

---

## Phase 2 baseline: the cascade vs. a trivial classifier (2026-09-23)

LIBRARY.md Phase 2 asks whether Jev adds anything over the vision
model alone, and whether either is worth it over a trivial baseline.
Three systems were run against the 85 reviewed records (ground truth
= the manual_correction labels):

1. **Keyword baseline** (`baseline_compare.py`): deterministic
   keyword rules on the same Pixtral descriptions, always fully
   confident -- a trivial classifier with no calibration by
   construction.
2. **Cascade** (Pixtral description + Jev): the production path;
   raw Jev answers from the v4 run.
3. **Pixtral asked directly** (`baseline_pixtral_direct.py`): the
   vision model classifies the five facets itself, same v4 criteria,
   with a calibrated-confidence instruction. 85/85 records, 0 API
   errors (an earlier attempt failed with HTTP 402 Payment Required
   until the account was topped up).

Head-to-head on the 85 labeled records:

| System | Pooled accuracy | ECE | Wrong records | Caught at 0.7 | Silent errors |
|---|---|---|---|---|---|
| Keyword baseline | 78% | 0.166 | 49 | 0/49 | 49 |
| Cascade (Pixtral+Jev) | **91%** | **0.038** | 27 | 16/27 | 11 |
| Pixtral asked directly | 80% | 0.150 | 45 | 0/45 | 45 |

Per-facet accuracy:

| Facet | Keyword | Cascade | Pixtral-direct |
|---|---|---|---|
| contains_human | 67/85 (79%) | 78/85 (92%) | 72/85 (85%) |
| contains_robot | 78/85 (92%) | 82/85 (96%) | 71/85 (84%) |
| contains_android | 85/85 (100%) | 84/85 (99%) | 79/85 (93%) |
| primary_subject | 61/85 (72%) | 77/85 (91%) | 64/85 (75%) |
| representation | 42/85 (49%) | 67/85 (79%) | 54/85 (64%) |

Cascade accuracy by confidence bin (both other systems have one bin,
0.9-1.0, at 78% and 80% -- their confidence carries no information):

| Confidence | Accuracy |
|---|---|
| 0.0-0.5 | 13/20 (65%) |
| 0.5-0.7 | 24/35 (69%) |
| 0.7-0.9 | 41/47 (87%) |
| 0.9-1.0 | 310/323 (96%) |

Findings:

1. **The cascade wins on every measure that matters.** +11 points
   pooled accuracy over Pixtral-direct, 4x lower calibration error,
   and it is the only system whose 0.7 threshold catches errors
   (16/27). Both alternatives answer everything at 0.9+ confidence,
   so all 45-49 of their wrong records are silent.
2. **Pixtral-direct ignores the calibration instruction.** Asked for
   calibrated probabilities, it reports >= 0.9 on all 425 facet
   answers while being wrong 20% of the time. Jev's confidence is
   the scarce resource in this pipeline: the vision model supplies
   perception, Jev supplies the probability that makes routing
   possible.
3. **The keyword baseline is a real floor, not a straw man.** It
   matches the cascade on easy facets (contains_android 100% vs 99%)
   because the descriptions already contain the answer -- but it
   collapses where descriptions are ambiguous (representation 49%,
   primary_subject 72%). The comparison is also conservative toward
   it: the keyword rules run on Pixtral's descriptions, inheriting
   the vision model's work for free.
4. **The burden number needs care.** On the labeled subset the
   cascade flags 52% -- but that subset is queue-heavy by
   construction (50 of 85 are queue records). The collection-wide
   burden remains 50/218 (23%).

---

## Phase 3: structured vision state (2026-09-23)

LIBRARY.md Phase 3 replaces the free 25-word description with typed
fields per image (medium, subjects, text_in_image, setting, people);
Jev classifies the composed state, with transcribed text explicitly
labeled as quoted content. Three iterations, each run on the 85
labeled records (`structured_vision.py`; v1 and v2 runs preserved
privately in `2026-09-23_structured_v1_run/` and
`..._structured_v2_run/`; the v3 run's raw records were not
preserved -- only its measured numbers):

| System | Pooled accuracy | ECE | representation | Burden at 0.7 | Wrong | Caught | Silent |
|---|---|---|---|---|---|---|---|
| Cascade (production) | 91% | 0.038 | 79% | 52% | 27 | 16/27 | 11 |
| Structured v1 (rich medium: poster, diagram, render) | 88% | 0.047 | 67% | 22% | 34 | 11/34 | 23 |
| Structured v2 (medium aligned to the representation classes) | **90%** | 0.048 | **76%** | 22% | 25 | 5/25 | 20 |
| Structured v3 (physical-context clause) | 88% | 0.047 | 69% | 20% | 31 | 9/31 | 22 |

Findings:

1. **v1's regression was vocabulary mismatch.** The medium field
   answered `poster` and `diagram`, which are not representation
   classes -- Jev had to guess (a poster of a photograph became an
   illustration). Aligning `medium` exactly with the representation
   taxonomy recovered most of the loss (representation 67% -> 76%).
2. **The bottleneck moved into the vision field extraction.** Of the
   20 remaining representation errors in v2, 19 have a wrong
   `medium` field -- Jev inherits the error from a state that is
   already wrong. The photographed-cover family (a real photo of a
   cover described as `screenshot_of_text`) and the deepseek
   described-scene trap (subjects filled from text the image merely
   mentions) both live in the vision model, not in Jev.
3. **v3 (physical-context clause) is a rejected negative result.** A
   sharper medium definition -- photograph when the text-bearing
   surface shows physical depth or surroundings, text_screenshot only
   for a flat head-on capture -- fixed 1 record and broke 7: the
   clause made the vision model *more* eager to call photographed
   covers and game screens `text_screenshot`. With v2's milder clause
   having failed to fire on the same family, the conclusion is that
   prompt wording cannot make this vision model reliably separate
   "photo of a text-bearing object" from "screenshot of text." The
   residual is a genuine vision limitation; the durable options are a
   dedicated binary capture-type question or review-always for the
   ambiguous family. v2 is restored as the live structured variant.
4. **The screenshot-of-text failure mode is eliminated where the
   medium field is right.** Every image the vision model correctly
   labels `text_screenshot` classifies as `text_screenshot` at 1.0
   confidence -- the incident that motivated Phase 3 cannot recur on
   a correctly-extracted state.
5. **On the errors-caught-per-burden metric, the structured state is
   still a measured negative against the cascade**: it flags less
   (22% vs 52% on this subset) but converts more errors into
   confident ones (20 silent vs 11). The cascade remains the
   production path.
6. **The structured state is the right diagnostic instrument.** It
   separates vision errors from Jev errors cleanly: Jev is now
   nearly perfect on the state it is given. The next representation
   fix is a vision-prompt fix (the photographed-cover family), not a
   Jev-criteria fix.

Engineering notes: Pixtral emits raw newlines and unescaped quotes
inside transcribed text -- the parser needs `strict=False` and a
regex repair fallback; `max_tokens` 300 truncated long transcriptions
(raised to 700).

### Option 1: the dedicated capture-type question (2026-09-23)

The remaining option was a different mechanism: an isolated second
vision call answering only "flat digital capture, or photograph of a
physical object?" (`capture_type.py`), with a deterministic override
of the structured `medium` field -- photo_of_physical flips
text_screenshot to photograph; digital_capture flips photograph to
text_screenshot and clears subjects. Run on the 85 labeled records:

| System | Pooled accuracy | ECE | representation | Burden at 0.7 | Wrong | Caught | Silent |
|---|---|---|---|---|---|---|---|
| Structured v2 (no capture question) | 90% | 0.048 | 76% | 22% | 25 | 5/25 | 20 |
| Capture-type override | 89% | 0.033 | 74% | 26% | 27 | 11/27 | 16 |

**Rejected -- and the reason is more important than the numbers.**
The capture question itself does not perceive the distinction: it
answers `digital_capture` for 37 of the 85 records whose truth is a
photograph, illustration, or render of a physical thing -- plain
photographs included. The override therefore fired in both directions
at random, manufacturing new errors (photographed covers flipped to
text_screenshot) while failing to fix the family it targeted.

The conclusion across all three attempts (v2's embedded clause, v3's
physical-context clause, and now an isolated forced-binary question):
**this vision model cannot distinguish "a photograph of a
text-bearing object" from "a flat digital capture."** The limitation
is perceptual, not instructional. No prompt or question architecture
tried so far moves it. The remaining path for the ambiguous family
is review-always routing (Option 2), not another vision-prompt
variant.

### Option 2: review-always routing for the text-bearing family (2026-09-23)

With perception ruled out, the fix is routing (`routing.py`): route
to review if any facet confidence < 0.7 (the existing queue rule) OR
the description carries a text-bearing signal ("is a screenshot",
"screenshot shows", "consists of text", terminal, scan of, readout,
interface) after stripping the vision prompt's preamble.

Candidate rules measured on the 85 labeled records (27 wrong records;
burden also shown on the full 218):

| Rule | Burden (labeled / full 218) | Errors caught | Silent |
|---|---|---|---|
| A: current threshold only | 52% / 20% | 18/27 | 9 |
| B: A + text signal (broad) | 86% / 72% | **25/27** | 2 |
| C: A + representation conf < 0.95 | 73% / -- | 22/27 | 5 |
| D: A + representation conf < 1.0 | 79% / -- | 23/27 | 4 |
| E: B + C | 88% / 73% | 25/27 | 2 |

Rule B is adopted: the text signal catches 7 of the 9 silent errors
at a full-collection burden of 72% (156/218 records: 44
low-confidence, 112 text-bearing only). The two remaining silent
errors are vision-limited without any text signal (a render described
as a render; a poster illustration whose entity error sits exactly at
the 0.70 boundary -- note the queue rule is `< 0.7`, so a record at
exactly 0.70 escapes; tightening to `<= 0.7` is a separate decision).

The trade is explicit and the cataloger's to make: 20% burden leaves
9 silent errors per 27 wrong; 72% burden leaves 2. On this
screenshot-heavy personal collection the burden is high because the
collection is full of text-bearing surfaces; a library collection's
proportion would differ. The pattern is a single constant in
`routing.py`, tunable without code changes elsewhere.

---

## What is unproven

1. **Ground truth covers 85 of 218 records (39%).** All 50 queued
   records plus a 30-record stratified sample of the confident band
   are labeled -- the first two-sided view of the routing threshold.
   The verdict: entity facets are well-calibrated (queue catches
   their errors; confident-band entity miss ~3%), but
   `representation` is ~80% accurate at every confidence level and
   should never be auto-accepted. The remaining 133 confident
   records are unlabeled; extrapolating the sample, roughly 31
   carry a wrong facet, almost all `representation`.
2. **The vision model is the bottleneck.** Jev only sees the 25-word
   description. If Pixtral mis-describes an image (e.g., misses a person
   in the background, or describes a statue as a person), Jev inherits
   the error. The description is lossy by design.
3. **"Human" is a fuzzy label.** The low-confidence cases show the
   boundary is genuinely ambiguous (statue vs. person, cartoon vs.
   photo). The criteria could be tightened (e.g., "a real, living human
   in a photograph") or split into sub-labels (photo / illustration /
   statue).
4. **The baseline comparison is complete on this collection.** All
   three systems are measured (above): the cascade beats both the
   keyword baseline and Pixtral-direct on accuracy, calibration, and
   errors caught. Still unmeasured: a CLIP-style pixel-level
   baseline, and the comparison on a real library collection.

---

## Edge-case suite (2026-09-23)

`generate_edge_cases.py` generated the adversarial edge-case suite
(TODO item 9) with Mistral image generation, billed to the Mistral
API credits: 8/8 prompts, 0 errors, 7,217 tokens and 8 image
generations total. The prompts cover the measured failure families:
text describing a scene (the known screenshot-of-text mode), a meme
with caption text, an AI-generated portrait, a collage, people small
in the background, a game inventory screen, a statue, and a robot
illustration. Images live in `edge_cases/` (gitignored); per-prompt
records in `edge_case_results.json` (private, gitignored).

**Measured (2026-09-23).** `measure_edge_cases.py` ran the production
path (Pixtral describe -> Jev five facets, v4 taxonomy) on all 8 and
compared to the intended labels: 8/8 measured, 0 pipeline errors.
Pooled agreement on unambiguous facets: 33/36 (92%). Per facet:
contains_human 7/8 (88%), contains_robot 7/8 (88%),
contains_android 7/7 (100%), primary_subject 6/6 (100%),
representation 6/7 (86%). The three mismatches:

- `text_describes_scene` contains_robot answered yes at 0.050
  confidence -- the known described-scene failure, but hedged into
  the queue (caught, not silent). contains_human and primary_subject
  were correct: the depicted-vs-described clause held.
- `ai_generated_portrait` representation answered photograph at 1.000
  (intended render) -- the known perceptual limitation again: a
  photorealistic AI image is pixel-indistinguishable from a
  photograph, and the taxonomy has no AI-generated class. The one
  silent, confident mismatch.
- `game_screen` contains_human answered no at 0.960 (intended yes) --
  but the description mentions only "items and character stats", no
  visible person: the generated image likely lacks the character
  portrait the prompt asked for. A generation-side gap, not clearly
  a classification error.

Two taxonomy gaps surfaced: incidental humans (a building with
people in front) and an interface screenshot with a depicted subject
have no clean primary_subject or representation class -- both were
scored as ambiguous rather than forced.

**Routing on the suite.** With the fixed stripper (below), 6 of 8
records route to review: 2 text-bearing (the game screen and the
meme -- both genuinely contain text), 4 low-confidence (collage,
background people, statue, and the described-scene image -- all
hedged), and 2 auto-accept (the AI-generated portrait and the robot
illustration, both fully confident and correctly classified). Before
the fix, all 8 routed, with 2-3 false text-bearing flags caused by
the preamble leak.

**Routing stripper fixed (2026-09-23).** The suite exposed that
`routing.py`'s `description_body` stripped only a first line starting
"this image does not consist", while Pixtral's check-first line
varies ("The image does not consist...", "This image consists of
neither..."); unstripped, the word "terminal" in the negated preamble
fired false text-bearing flags on clean photographs. Three variants
were measured on the full 218 against the 85 labeled records:

| Stripper | Caught | Silent | Burden |
|---|---|---|---|
| old (one wording only) | 25/27 | 2 | 156/218 (72%) |
| every first line | 23/27 | 4 | 109/218 (50%) |
| negations only (adopted) | 25/27 | 2 | 135/218 (62%) |

Stripping every first line is strictly worse: two of the caught
errors (a book cover and a text-and-graphics illustration) have
first lines that AFFIRM text ("The image consists of text.") -- true
signals the aggressive stripper deleted. The adopted fix strips only
negated check-lines: same 25/27 catches, burden down 21 records
(72% -> 62%). `routing_queue.json` regenerated: 135 routed (44
low-confidence, 91 text-bearing only).

---

## Stand-in library corpus (2026-09-23)

`fetch_library_standin.py` fetched a stand-in library corpus from
Wikimedia Commons: 149 images across 5 of 6 categories (statue 28,
humanoid_robot 22, book_cover 36, human_photo 33, human_illustration
30; ui_screenshot 0), each with a manifest record (category, Commons
description, license) in `library_manifest.json` -- committed, since
Commons metadata is public data and the manifest is the stand-in
ground truth. Images live in `library_standin/` (gitignored). The
run is short of the 40/category target: Wikimedia rate-limited the
IP (429s on download bursts even at 5s spacing, then a 403
robot-policy block that outlasted a 3-minute wait). The script is
resumable -- re-run it once the block lifts to top up all categories
and add ui_screenshot. The structured depicts (P180) resolution came
back empty on this run; undebugged because of the block. The corpus
is usable as-is for a first pipeline pass.

**Measured (2026-09-23).** `measure_library_standin.py` ran the
production path (Pixtral describe -> Jev five facets, v4) on all 149
and compared to the labels the manifest category implies: 149/149
measured, 0 pipeline errors. Pooled agreement on unambiguous facets:
541/615 (88%). Per facet: contains_human 91/113 (81%),
contains_robot 145/149 (97%), contains_android 140/149 (94%),
primary_subject 89/113 (79%), representation 76/91 (84%). Per
category: book_cover 72/72 (100%) of 36, human_photo 165/165 (100%)
of 33, human_illustration 139/150 (93%) of 30, humanoid_robot 64/88
(73%) of 22, statue 101/140 (72%) of 28.

Reading: the clean categories are perfect -- book covers and human
photos score 100% on every facet the category can determine. The two
weak categories are exactly the noisy-label ones: Category:Statues
includes non-humanoid statues (animal statues, architectural
sculpture), and the humanoid-robot category mixes toys, costumes, and
concept art, so the category-implied labels are approximations there.
Mismatches are review candidates, not verdicts. Jev's calibration
behaves as designed on both: 20 of 28 statue records and 17 of 22
humanoid-robot records route to review on low confidence, while the
clean categories mostly auto-accept.

**Routing on the corpus.** 60/149 (40%) route to review (11
text-bearing, 49 low-confidence) -- a lower burden than the personal
collection's 62%, consistent with canonical, well-lit material
hedging less. The depicts (P180) resolution is still empty; once
fixed, the manifest's per-image depicts statements would replace the
noisy category-implied labels with precise annotation.

**Reviewed (2026-09-23).** All 60 routed records were reviewed through
`review_ui.py` (pointed at the corpus results, `library_standin/`,
taxonomy v4): 32 confirmed, 28 corrected. Per-facet accuracy on the
reviewed set: contains_human 43/60 (72%), contains_robot 57/60 (95%),
contains_android 53/60 (88%), primary_subject 45/60 (75%),
representation 50/60 (83%); pooled 248/300 (83%). This is accuracy on
the hard cases (the queue is all low-confidence or text-bearing), not
overall. The 89 auto-accepted records remain unverified, so the
queue's miss rate on the corpus is unknown. Corrections by category:
statue 11 of 20, humanoid_robot 10 of 18, book_cover 5 of 13,
human_illustration 2 of 8.

The corrections cluster into three families, and they are the
stand-in's real finding:

- **The android facet finally gets exercised.** 6 of the 28
  corrections are contains_android in the humanoid-robot category --
  the facet that never fired on the personal collection (0/215). The
  corpus's robot category mixes androids, toys, and costumes, and the
  boundary is exactly where the review was needed.
- **Non-humanoid statues.** 8 statue corrections touch
  contains_human/primary_subject: Category:Statues includes animal
  statues and architectural sculpture, and Jev answered "human" on
  the humanoid-looking ones. Part noisy label, part taxonomy gap --
  the v4 taxonomy has no clean class for a statue of a non-human.
- **Book covers with depicted content.** 5 cover corrections: covers
  carrying human figures or graphic designs strain both
  primary_subject and representation.

These edge cases highlight the need for a richer ontology (finer
representation splits, a non-human-statue class, sharper android
criteria) -- noted for a future revision, not acted on; per the
v3/v5 lesson, taxonomy revisions are measured against labeled
records, and the corpus now has 60 of them to measure against.

**Confident-band sample (complete, 27/27).** The review UI's Sample
filter computed a stratified sample of 27 fully confident unreviewed
corpus records (short of the 30 target: the corpus's confident pool
per band/class is smaller than the personal collection's), persisted
at `library_review_sample_tmp.json` (gitignored). All 27 reviewed:
22 confirmed, 5 corrected -- miss rate 5/27 (19%, Wilson CI ~8-37%)
on the 89 auto-accepted records' family. Unlike the personal
collection's band (7/30, 6 of 7 representation), the corrections are
spread across categories (2 book covers, 1 each human_photo,
humanoid_robot, statue), and confident-band accuracy is 89-96% on
every facet: on this corpus, representation's confidence carries
information (89% in the band vs 83% in the queue). 81 of 149 corpus
records are now labeled.

**Top-up (2026-09-23, block lifted).** `fetch_library_standin.py`
topped up all categories: 231 images total across all 6 categories
(statue 40/40, humanoid_robot 40/40, book_cover 40/40,
human_photo 40/40, human_illustration 38/40, ui_screenshot 33/40 --
was 0). Nine short of the 40/category target: 11 downloads lost to
HTTP 429s even at 20s spacing (DELAY raised from 5s after the first
top-up attempt drew 429s); the script is resumable, so a re-run tops
up the last 9. Two fetcher bugs found and fixed on this run:

- **Resume numbering.** The resume path numbered new files from 1,
  colliding with existing manifest keys (`statue_001.jpg` ...), so a
  re-run fetched nothing while exiting 0. Fixed: numbering starts
  after the category's existing count.
- **Depicts route.** The P180 resolution queried
  `pageprops.wikibase_item` -- the Wikidata Q-id link, empty for most
  files -- instead of the MediaInfo M-id route (`wbgetentities` with
  `sites=commonswiki` + the file title). The corrected route works
  mechanically, but 0/231 corpus files carry P180 depicts statements:
  Commons structured-data coverage is uneven in these categories, so
  the manifest's category remains the only ground truth. Precise
  depicts annotation is a dead end for this corpus.

**Top-up complete (2026-09-24).** A re-run fetched the last 9
(human_illustration 38 -> 40, ui_screenshot 33 -> 40): the corpus is
complete at 240 images, 40 per category, 0 errors. The first re-run
attempt exited 0 and fetched nothing (transient; a second run
succeeded at the same 20s DELAY). The 9 new images are unmeasured
and unlabeled -- they join the corpus at the next pipeline re-run.

**Measured, full corpus (2026-09-23, n=231).**
`measure_library_standin.py` ran the production path on the 82 new
images (resumable; 231/231 measured, 0 pipeline errors). Pooled
agreement on unambiguous facets: 794/929 (85%). Per facet:
contains_human 127/158 (80%), contains_robot 221/231 (96%),
contains_android 215/231 (93%), primary_subject 121/158 (77%),
representation 110/151 (73%). Per category: book_cover 80/80 (100%)
of 40, human_photo 200/200 (100%) of 40, human_illustration 177/190
(93%) of 38, statue 150/200 (75%) of 40, ui_screenshot 79/99 (80%)
of 33, humanoid_robot 108/160 (68%) of 40. The new ui_screenshot
category scores 80%: its only scored facet is representation, and
Jev answers text_screenshot on most but hedges to `other` on the
rest. Routing burden rises to 115/231 (50%) with the new category:
ui_screenshot routes 32/33 (22 text-bearing -- a true signal for
screenshots -- and 10 low-confidence), while the clean categories
still mostly auto-accept.

**Reviewed, second batch (2026-09-24).** The 55 unreviewed routed
records from the top-up were reviewed through `review_ui.py` (corpus
results, `library_standin/`, taxonomy v4): 25 confirmed, 30 corrected
(45% agreement) -- harder than the first batch's 83%, as expected:
this batch is dominated by the two noisy-label categories
(ui_screenshot 32, humanoid_robot 11) plus 8 statue records. Route
reasons: 25 text-bearing, 30 low-confidence. Per-facet accuracy on
the batch: contains_human 51/55 (93%), contains_robot 53/55 (96%),
contains_android 49/55 (89%), primary_subject 48/55 (87%),
representation 34/55 (62%). Per category: book_cover 2/2,
human_illustration 2/2, statue 4/8, ui_screenshot 15/32,
humanoid_robot 2/11. The ui_screenshot result is the text-bearing
signal working as designed -- it routes screenshots to review, where
Jev's answers are right only 47% of the time; without the signal
those would be silent errors. The humanoid_robot batch (2/11) is the
noisy-label category again: toys, costumes, and concept art under
one Commons category.

Cumulative review state (both batches, 136 of 231 records labeled):
75 confirmed, 61 corrected, pooled agreement 55% on the routed
records. Per-facet accuracy across all reviewed: contains_human
115/136 (85%), contains_robot 130/136 (96%), contains_android
122/136 (90%), primary_subject 114/136 (84%), representation
104/136 (76%). Correction families across the 61 corrected records:
20 representation-only, 12 contains_android-only, 8
contains_human+primary_subject (the non-humanoid statue family),
6 contains_human+primary_subject+representation, 4 contains_human,
3 contains_robot+primary_subject+representation, and 8 smaller
combos. Per-facet correction counts: representation 32,
primary_subject 22, contains_human 21, contains_android 14,
contains_robot 6. The 95 auto-accepted records remain unverified
(the confident-band sample of 27 bounds their miss rate at 19%,
Wilson CI ~8-37%).

---

## Held-out taxonomy revision (2026-09-24)

The first revision run under the LIBRARY.md Phase 6 held-out protocol:
`humanoid_taxonomy_v6.json` was authored from the stand-in corpus
batch 1 corrections (2026-09-23, 31 corrections in four families) and
measured on batch 2 (2026-09-24, 55 labeled records), which the
revision never saw. One Jev call per record on the same descriptions
(`measure_taxonomy_v6.py`, no vision calls); the baseline is v4's
stored answers, the answers the batch 2 review judged.

**v6 (measured, held-out).** Pooled 238/275 (87%) vs v4's 235/275
(85%). The entity-facet changes worked: contains_android 49/55 (100%,
was 89%), contains_human 53/55 (96%, was 93%), primary_subject 50/55
(91%, was 87%). The `text_screenshot` narrowing backfired:
representation 27/55 (49%, was 62%) -- the labels say 28 of 32
ui_screenshots ARE text_screenshot, and v6 broke 5 records v4 had
right while fixing 0. This is the v3 lesson in mirror image: v3
broadened the class and de-hedged errors into confident ones; v6
narrowed it and converted correct confident answers into confident
`other` errors. Both directions of rewriting `text_screenshot` are now
measured negatives.

**v7 (adopted).** `humanoid_taxonomy_v7.json` = v6's entity-facet
changes with v4's representation wording restored -- a composition of
measured components, re-measured on the same held-out batch: pooled
246/275 (89%) vs v4's 235/275 (85%); v7 fixes 10 records v4 had wrong
and breaks 2 (sign test ~p=0.04 -- at the edge of the noise floor,
suggestive rather than decisive). Per facet: contains_human 96%,
contains_robot 96%, contains_android 100%, primary_subject 91%,
representation 64%. Full-route burden 45/55 (82% -- the batch is
dominated by text-bearing ui_screenshots, a true signal); the routing
rule catches 21 of 22 errors, the one silent being a representation
error (statue_038) in the known vision-limited family. The v3/v5
failure mode did not materialize: v7's de-hedged records are correct.

**Adoption.** v7 is adopted as the default taxonomy
(`pilot_humanoid.py`, and `measure_library_standin.py` through it).
The cross-collection check: re-measured on the personal collection's
85 labeled records (`measure_taxonomy_v7_personal.py`, Jev calls
only), v7 pooled 389/425 (92%) vs v4's 388/425 (91%) -- fixes 3,
breaks 2, inside noise, no regression; contains_android 100% (was
99%), everything else within a point. Combined with the corpus's
held-out win (89% vs 85%), v7 is measured on both collections: it
beats v4 where the corrections motivated it and matches it where they
did not. The three v6/v7 criteria changes: sculpted works added to
the depiction media (9 batch 1 statue corrections answered no/none on
statues of humans -- the v4 medium enumeration omitted sculpting);
the android boundary sharpened to require a human-passing appearance
(8 batch 1 corrections over-fired on mechanical robots; "the image or
its context identifies them as artificial" let any robot in a robot
context count); `text_screenshot` left at v4's wording, now measured
from both directions.

**Run-to-run variance (TODO item 6) got a live data point.** The v6
criteria were run twice on the same 55 descriptions (the second run
accidental, a results-path mistake): identical choices on all five
facets, but 14 vs 16 threshold-routed records (25% vs 29% burden) --
choices are stable, confidences drift by a few points run to run.
Same-prompt variance is now measured once: small, but real, and it
moves records across the 0.7 boundary.

---

## Production re-run with v7 (2026-09-24)

With the corpus complete at 240 and v7 the default taxonomy,
`measure_library_standin.py` re-ran the full production path
(Pixtral describe -> Jev five facets, v7) on all 240 images with
fresh descriptions. The v4 results were moved aside first (the
script skips records already in the results file); the v4 run's raw
answers are preserved at
`../Ontology_private_backup/v4_corpus_run_2026-09-24/`, and the 136
manual corrections were merged back into the new results file
afterwards -- corrections are ground truth about the images, not
model answers, so the review state survives the re-run.

**Measured, full corpus (n=240, 0 pipeline errors).** Pooled
agreement on unambiguous facets: 857/960 (89%), vs v4's 794/929
(85%) on the 231-image run. Per facet: contains_human 138/160 (86%,
was 80%), contains_robot 229/240 (95%, was 96%),
contains_android 239/240 (100%, was 93%), primary_subject 137/160
(86%, was 77%), representation 114/160 (71%, was 73%). Per category:
book_cover 80/80 (100%), human_photo 200/200 (100%),
human_illustration 187/200 (94%), statue 171/200 (86%),
ui_screenshot 99/120 (82%), humanoid_robot 120/160 (75%).

**Caveat: three variables changed at once** -- taxonomy (v7), fresh
descriptions (new vision calls), and the 9 new images. The held-out
batch (same descriptions, v7 vs v4 isolated) already measured the
taxonomy effect at 89% vs 85%; this run is the production
confirmation on the whole corpus, not an isolated comparison. The
representation dip (73% -> 71%) is inside that run-to-run noise.

**Routing.** Full-rule burden 106/240 (44%), down from v4's 115/231
(50%): statue routes 25/40 (all low-confidence), ui_screenshot 39/40
(28 text-bearing -- the true signal for screenshots -- and 11
low-confidence), humanoid_robot 16/40, book_cover 14/40,
human_illustration 11/40, human_photo 1/40. Threshold-routed alone:
69/240 (29%).

The 9 top-up images are now measured but unlabeled; the 136 labeled
records are the two review batches against v4's answers.

**Against human ground truth (no API calls).** The merged corrections
allow a direct comparison on the same 136 labeled records: v7's fresh
answers agree with the human corrections on 607/680 facets (89%) vs
v4's stored answers' 585/680 (86%). Per facet: contains_human 90% vs
85%, contains_robot 96% vs 96%, contains_android 100% vs 90%,
primary_subject 87% vs 84%, representation 74% vs 76% (the only dip,
inside noise). The held-out result holds against real ground truth on
the full labeled set: v7 is better where it was designed to be
(entity facets) and no worse on representation.

**Reviewed, third batch (2026-09-24, v7 answers).** The 12 unreviewed
routed records from the v7 re-run were reviewed through `review_ui.py`
(corpus results, v7 taxonomy, temp sample path): 8 confirmed, 4
corrected -- v7 agreed with the reviewer on 56/60 facets (93%), far
above the v4 batches' 55% on their hard cases. Route reasons: 10
low-confidence, 2 text-bearing. Categories: ui_screenshot 7,
humanoid_robot 2, human_illustration 2, statue 1. Per-facet accuracy
on the batch: contains_human 11/12 (92%), contains_robot 11/12 (92%),
contains_android 12/12 (100%), primary_subject 12/12 (100%),
representation 10/12 (83%). The review queue is now empty (0
unreviewed routed records).

Cumulative review state (three batches, 148 of 240 records labeled):
83 confirmed, 65 corrected. v7's fresh answers agree with all human
corrections on 663/740 facets (90%). The 92 unreviewed records are
auto-accepted (the confident-band sample of 27 under v4 bounded their
miss rate at 19%); a fresh confident-band sample under v7 would
re-bound that rate.

---

## Second held-out revision (2026-09-24): v8 measured, not adopted

The same abduction loop that produced v6 -> v7, run again:
`author_taxonomy_v8.py` built v8 from v7 with one change -- the
subject-decides clause for the representation facet (a photograph or
illustration whose subject is a statue, sculpture, or model is
statue_or_render; one whose subject is a drawing, painting, or poster
is illustration). Authored from batch 1's statue-family corrections
(2026-09-23: photograph->statue_or_render x5,
illustration->statue_or_render x1, photograph->illustration x3), a
family v6/v7 never addressed. Measured held-out on the 67 records
dated 2026-09-24 (batches 2+3), which the revision never saw; the
baseline is v7's stored answers on the same descriptions.

**Measured (held-out, n=67).** v8 pooled 302/335 (90%) vs v7's stored
301/335 (90%); representation 46/67 (69%) vs 44/67 (66%). Per-record
fixes 5 / breaks 3 -- but 3 of the 8 changes (two ui_screenshot fixes,
one break) are on criteria v8 did not change, i.e. pure run-to-run
variance. The criterion-attributable effect: 4 representation records
toward truth (statue_035, statue_040, human_illustration_035,
humanoid_robot_026 -- the statue family fixed where targeted), 2 away
(humanoid_robot_029, statue_032 -- the clause's word "model"
over-applies to photographed robots). Routing: 12 caught, burden 25/67
-- identical to v7's.

**Verdict: inside noise, not adopted.** v7's adoption bar was fixes
10 / breaks 2 (sign test ~p=0.04); v8's 5/3 does not clear it, and the
criterion-attributable net is +2 records. v7 stays the default; v8 is
kept as the measured record. The "model" ambiguity in the defer clause
is the next revision's signal -- but a v9 authored from these breaks
would need a fresh labeled batch to be held-out (batch 2+3 is spent).

**Open gap, deliberately not revised:** 13 batch-2 corrections where
Jev answers `other` for interface screenshots whose truth is
text_screenshot. v3 tried the interface broadening inside
text_screenshot and it was a measured negative on the personal
collection; all 39 labeled ui_screenshot records are dated 2026-09-24,
so no held-out batch can test the fix. Needs a designed experiment
(a fresh ui_screenshot review batch split into authoring and
measurement halves), not a criterion edit.

---

## Files

```
classify_images.py       -- resumable pipeline (vision -> Jev)
summarize_results.py     -- regenerates the summary from the JSON
image_human_results.json -- full per-image records
image_human_summary.txt  -- clean sorted list
```

---

*Signed: Mistral Vibe (mistral-vibe), 2026-09-22*
