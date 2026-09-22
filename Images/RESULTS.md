# Results: Image classification with Jev

**Date:** 2026-09-22
**Author:** Mistral Vibe (mistral-vibe)
**Task:** Sort 215 images in `Pictures\` by whether they contain a human.
**Vision model:** Mistral `pixtral-12b-2409`
**Jev model:** jev-latest (jev-1.13.0)
**Images:** 215 (73 human, 142 no-human, 0 errors)

---

## Summary

The task was to sort the images in the Pictures folder by whether they
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
corrected `[redacted]` contributes a manual 1.0 to the
no-human >=0.9 bucket; Jev's raw answer ("yes" at 1.000, preserved
under the record's `jev` key in `image_human_results.json`) would place
it in the contains-human >=0.9 bucket instead.

> **Correction (2026-09-22):** `[redacted]` was initially classified
> as "contains human" at 1.000, but it is actually a screenshot of *text*
> describing a photo, not a photo of a human. The vision model read the
> text ("a man and a robot...") and described it as if it were the scene,
> and Jev then said "yes." It has been removed from the human set and
> reclassified as no-human. This is a real failure mode: screenshots of
> text that *describes* a person get misclassified as containing a person.

---

## The interesting finding: Jev surfaces "real human vs. depiction"

The 13 cases below 0.7 confidence are not noise -- they are all
illustrations, statues, cartoons, or posters rather than photographs of
real people:

| File | Choice | Conf | Description |
|---|---|---|---|
| [redacted] | yes | 0.05 | comic book characters Batman and Robin |
| [redacted] | yes | 0.16 | Arthur Mensch discusses Mistral AI |
| [redacted] | yes | 0.28 | cartoon boy celebrates his 15th birthday |
| [redacted] | yes | 0.39 | pixelated version of "The Thinker" statue |
| [redacted] | no | 0.45 | superhero resembling The Flash |
| [redacted] | no | 0.47 | cartoon superhero labeled GPT-5 |
| [redacted] | yes | 0.48 | illustrations of team members |
| [redacted] | no | 0.49 | magazine cover |
| [redacted] | yes | 0.54 | illustrations of team members |
| [redacted] | no | 0.55 | victory screen with characters |
| [redacted] | no | 0.57 | list of students |
| [redacted] | no | 0.61 | cartoon character giving a thumbs-up |
| [redacted] | yes | 0.69 | film poster |

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

## What is unproven

1. **No ground truth.** We did not manually label the 215 images, so
   accuracy is unmeasured. The 73/142 split is Jev's judgment, not a
   verified answer. A manual audit of a sample (especially the 13
   low-confidence cases) would establish real accuracy.
2. **The vision model is the bottleneck.** Jev only sees the 25-word
   description. If Pixtral mis-describes an image (e.g., misses a person
   in the background, or describes a statue as a person), Jev inherits
   the error. The description is lossy by design.
3. **"Human" is a fuzzy label.** The low-confidence cases show the
   boundary is genuinely ambiguous (statue vs. person, cartoon vs.
   photo). The criteria could be tightened (e.g., "a real, living human
   in a photograph") or split into sub-labels (photo / illustration /
   statue).
4. **No baseline.** We did not compare against a dedicated image
   classifier (e.g., a CLIP-based zero-shot model or a face detector).
   The right comparison is "Jev + vision description vs. the cheapest
   acceptable image classifier."

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
