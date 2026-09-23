<img width="1900" height="1139" alt="Twiki and Buck" src="https://github.com/user-attachments/assets/0be69cb5-437b-4d33-b283-10360b4fdd15" />
"A visual ontology, Twiki. That is where we are going!"<br>
"Yes, Buck, and Jev is going to help us."

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

Note: Once Jev becomes the multimodal, we can shorten the pipeline and quite likely acheive amazing speed and economy.

Also note that while Jev is ridiculously cheap, Pixtral is also low cost, so on the whole the project is already economical as-is.

But being able to do this just with a Jev-like model would certainly be a game-changer, so we are holding our breath for that.

## What this directory is

A small sub-project of the Ontology + Jev work. The task: sort a folder
of images by whether they contain a human. The pipeline is:

```
Mistral Pixtral describes the image (one 25-word sentence)
  -> Jev classifies the description: "Does this image contain a human?" (yes/no)
```

The vision model is the "eyes"; Jev is the decision maker. Jev returns a
calibrated probability, so ambiguous cases (statues, cartoons, posters)
are flagged with low confidence rather than forced into an answer.

## What Jev contributes

Jev's role here is the **calibrated decision layer, not perception**. The
vision model does the perceptual work; Jev decides with a probability.

What Jev genuinely adds:

- **Calibrated confidence.** Pixtral returns free text; Jev returns a
  probability. That probability is what lets us set a threshold (0.7)
  and flag the 13 depictions as ambiguous instead of forcing a yes/no.
- **Typed, deterministic output.** A structured `choice: yes/no` with
  probabilities -- no parsing, no format drift, directly usable in code.
- **Criteria-as-state.** The decision rule ("one or more humans (people,
  faces, bodies)") is passed as data, not code. You can tighten it to
  "a real, living human in a photograph" without retraining or touching
  the pipeline.
- **Consistency across the batch.** One criteria set applied to all 215
  descriptions; a vision model asked directly might drift in how it
  reads "human" from image to image.

Where it is thin:

- **Jev never sees the image.** It sees a 25-word description, so its
  "understanding" is bounded by that summary.
- **The vision model could likely answer directly.** Ask Pixtral "does
  this contain a human?" and it would probably be right; Jev is an extra
  hop.
- **Jev inherits vision errors.** A screenshot-of-text image is the proof:
  Pixtral transcribed text as if it were a scene, and Jev said "yes"
  because it only saw the description.
- **The bottleneck is the vision model.** The 13 low-confidence cases are
  depictions *because* Pixtral described them as statues/cartoons; Jev
  just attached a number to that.

For a single yes/no "contains human" question, Jev's marginal value is
mostly calibration and a stable, re-criterionable decision interface --
real, but narrow. It grows when the decision is harder: a multi-class
taxonomy, hierarchical routing, thresholding for human review, or
changing criteria without retraining. That is the same "LLM authors, Jev
filters" cascade as the ticket work.

> **This is scaffolding, not the end state.** The current pipeline is a
> minimal demonstration that the cascade works end to end: a vision model
> describes, Jev decides. The point is to *increase* Jev's contribution
> from here -- to make Jev do more of the meaningful work, not just a
> thin yes/no on a vision description. Concrete directions:
>
> - **Richer decisions.** Replace the single yes/no with a multi-class
>   taxonomy (human / animal / object / text / landscape) or a
>   hierarchical ontology, so Jev's Choice question does real work.
> - **Multiple questions in one pass.** Ask Jev several questions per
>   image (contains human? is it a photo? is it a depiction?) in a single
>   call, using its calibration to route.
> - **Calibration-driven routing.** Use Jev's confidence to decide
>   auto-classify vs. human review, rather than a fixed threshold.
> - **Criteria as the ontology.** Treat the decision criteria as the
>   ontology to be revised from Jev's low-confidence signals, closing the
>   same feedback loop as the ticket work.
>
> See `TODO.md` for the full outline of this more ambitious project.

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
humanoid_taxonomy_v1.json          -- pilot taxonomy: humanoid facets as data
pilot_humanoid.py                  -- re-classifies the 215 descriptions against it
humanoid_pilot_results.json (private) -- pilot per-image results (gitignored)
```

## Running it

Requires `MISTRAL_API_KEY` (vision) and `TYPESAFE_API_KEY` (Jev), plus
`PICTURES_DIR` pointing at the folder of images to classify.

```bash
export PICTURES_DIR="C:/path/to/your/pictures"
python classify_images.py   # processes all images, saves incrementally
python summarize_results.py # prints the sorted summary
```

## Results

215 images classified: 73 contain a human, 142 do not, 0 errors. 87%
at 0.9+ confidence. The 13 sub-0.7-confidence cases are all
illustrations, statues, cartoons, or posters rather than photos of real
people -- Jev's calibration surfaces the "real human vs. depiction"
boundary. See `RESULTS.md` for the full writeup.

## Caveats

- **No ground truth.** The split is Jev's judgment; accuracy is
  unmeasured. A manual audit of a sample would establish real accuracy.
- **The vision model is the bottleneck.** Jev only sees the 25-word
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
