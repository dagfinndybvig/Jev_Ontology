<img width="1280" height="509" alt="Buck Rogers and the robot Twiki" src="https://github.com/user-attachments/assets/a224fe33-2ed1-45da-b78d-335e9ce5de40" />

# Ontology + Jev

Exploring how to pair [Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev),
TypeSafe AI's "System One" decision model, with ontologies.

> **Pivot: visual ontology (2026-09-22).** The project is now moving
> toward the image side: classifying images in a university library
> collection against a revisable taxonomy, using the same LLM + Jev
> cascade. This is the use case that drives the work going forward.
> See the [`Images/`](Images/) sub-project, its
> [README](Images/README.md), and the plan in
> [Images/LIBRARY.md](Images/LIBRARY.md).

> **Jev + LLM + Ontology = Abduction**
>
> Jev classifies items against an ontology. The LLM revises the ontology
> when classification fails. The loop repeats. This is abduction --
> Peirce's "forming an explanatory hypothesis to account for a surprising
> fact" -- performed by a system. See `PHILOSOPHY.md`.

> **Status: work in progress.**
>
> This is an active research project, not a finished result. The
> convergence findings below are **tentative and in-sample**: they
> describe what the loop does on the tickets that drove the revisions.
> A small held-out test (see `CONVERGENCE.md`) does not establish
> generalization. Its reported variance runs were not retained, so the
> historical noise-floor comparison cannot be independently verified.
> Treat these observations as exploratory, not as production guarantees.
>
> Comments and suggestions are welcome -- open an issue or a PR.

## TL;DR -- what we learned

**Repository reliability update:** root entry points are import-safe. Run
`python -B -m unittest discover` from the repository root for the offline
root and Images suites. `python test_jev_api.py` is an explicit **paid/live**
smoke check; missing keys, HTTP failures, and invalid answers fail nonzero.
Alternate MVP ontologies must supply their own version metadata. Experiment
storage is now incremental, atomic, and provenance-checked. Existing
historical JSONs are read-only. The evidence corrections below distinguish
classification passes, model confidence, and measured accuracy.

We built a working MVP pairing an LLM-authored ontology with Jev and tested
78 unique synthetic tickets across five session groups: **190 classification
passes and 380 Jev calls**, including all three convergence iterations.
The recorded input-token estimate was $0.0085 at the historical rate; this
excludes ontology-authoring costs and the later held-out/variance work.

**1. Targeted revisions changed confidence on the authoring examples.** Jev's low-confidence signals
identified a genuine gap in the billing sub-tree. The LLM revised the
ontology (added a WrongfulCharge class). Re-running the same tickets,
all three hedged tickets improved from 0.56-0.68 to 1.000 confidence.
This is an in-sample confidence change, not a measured gain in general
classification accuracy. Other examples showed small confidence declines.

**2. Confidence can suggest boundaries worth inspecting.**
The 0.14 probability on RefundRequest for a duplicate-charge ticket
suggested a semantic gap. Adding a class reduced the hedging. This is a
useful hypothesis-generation signal, not evidence that support-ticket
confidence is calibrated or that every uncertain answer reveals a schema gap.

**3. Perfect confidence is a double-edged signal.** The jump from 0.560
to 1.000 after one revision is large enough that the new class may be
slightly too broad. On the "unrecognized charge" ticket, 3% probability
went to WrongfulCharge while returned confidence fell from 1.000 to 0.960.
These observations motivate inspection; they do not establish the cause.

**4. The recorded classification calls were inexpensive.** The five session
groups used 204,325 input tokens for 190 classification passes, approximately
$0.0085 at the recorded rate. Authoring, human review, operations, and
current provider pricing are not covered by that estimate.

**5. Convergence tested (3 iterations, 52 tickets).** The feedback
loop produces monotonically improving mean confidence (0.940 ->
0.945 -> 0.948) and decreasing flagged tickets (3 -> 2 -> 2). Leaf
assignments are highly stable: only 1 of 52 tickets changed leaf
class across two ontology revisions. But the system has a floor
(genuinely compound tickets that need multi-label, not better
definitions) and revisions have side effects (fixing one gap
opened a new one on a previously clean ticket). The loop converges
in a descriptive sense only -- diminishing confidence changes, not a convergence proof.
See `CONVERGENCE.md`.

**6. Convergence remains a hypothesis.** Three iterations show diminishing
changes on this dataset, not proof of a steady state, an optimum, or an
irreducible error floor. The held-out mean-confidence change was +0.003825,
versus +0.012494 on train. Accuracy and statistical significance were not
established; the historical repeat-run evidence is unavailable.

**The biggest takeaway:** this is a working classifier-tuning pilot.
Humans/LLMs authored revisions between runs; there is no automated optimizer
or gradient-training step. Independent labeled data and retained repeated
runs are needed before making stronger learning or deployment claims.

See `RESULTS.md` for the full assessment, `CONVERGENCE.md` for the
3-iteration experiment, `LOOP.md` for the first closed-loop experiment,
`PHILOSOPHY.md` for the connection to induction and Jevons, and
`SESSIONS.md` for all session logs.

---

## What is Jev?

Jev is a model, named after William Stanley Jevons, that returns **typed, probabilistic decisions** instead of
generating text. You send it a *state* (the context to evaluate) and a set of
typed *questions* (Choice, Score, or Noul), and it returns decisions with
confidence and probability fields. Calibration must be measured for the
actual task; it was not established for these support tickets.

The following performance/pricing details are historical assumptions from
the original experiment, not current provider guarantees.

| Property | Value |
|---|---|
| Endpoint | `POST https://api.typesafe.ai/v1/systemone` |
| Model | `jev-latest` (historical transcripts report `jev-1.13.0`; alias not pinned) |
| Speed | 70-500ms end-to-end (~256ms median) |
| Cost | $0.042 per million input tokens, output free |
| Question types | Choice (pick one of N, up to 255), Score (rate on a 2-10 scale), Noul (yes/no probability) |
| Key env var | `TYPESAFE_API_KEY` |

Typed choices constrain the output vocabulary; they do **not** prevent
confidently wrong classifications, malformed responses, or transport errors.
The runners validate response shapes and values before accepting a result.

## The core idea

```
LLM authors the ontology (expensive, infrequent)
  -> Jev filters / classifies items against it (cheap, high-volume, per item)
```

This is the "cascade" pattern TypeSafe recommends: use the right tool for
each step. An LLM is good at generating structure from a domain description
(a generative, exploratory task). Jev is good at classifying thousands of
items against that structure (a repetitive decision task, at a fraction of
the cost and latency of an LLM).

The ontology acts as *state* passed to Jev -- class definitions, hierarchy,
and scope notes become the criteria for Jev's Choice questions. No retraining
is needed; you just swap the state when the ontology changes.

A feedback loop closes the cycle: Jev's per-item decisions reveal where the
ontology needs refinement (zero-traffic classes, low-confidence items, low-
margin decisions), which feeds back into re-prompting the LLM.

## Files

```
Ontology/
  IDEAS.md               -- eight ideas for Jev + ontologies, with the
                           "LLM-authored, Jev-filtered" cascade marked as
                           most promising, plus caveats and current status
  PHILOSOPHY.md          -- the LLM-Jev loop as a response to the problem
                           of induction: how the system performs category
                           revision (abduction), not just classification
  CONVERGENCE.md         -- 3-iteration convergence experiment on 52
                           tickets: does the feedback loop stabilize or
                           oscillate?
  RESULTS.md             -- signed assessment of the experiment: what
                           worked, what is unproven, and conclusions
  LOOP.md                -- closed-loop experiment: ontology revised based
                           on Jev feedback, re-run, confidence improved
  SESSIONS.md            -- authentic session logs from real Jev API calls
  TODO.md                -- next steps: multi-label, variance, held-out
                           eval, beam search, adversarial suite, and more
  ontology.json          -- LLM-authored ontology v2.0 (3 levels, 12 leaves)
  ontology_v3.json       -- revised ontology v3.0 (13 leaves, adds
                           WrongfulCharge based on Jev feedback signals)
  ontology_v4.json       -- revised ontology v4.0 (sharpens
                           BugReport/IntegrationProblem boundary,
                           SecurityConcern covers GDPR)
  ontology_v5.json       -- revised ontology v5.0 (AccountAndAccess covers
                           compliance/data handling at level 1)
  ontology_heldout_v1.json -- train-only revision authored for the held-out
                           generalization test (from v2.0 train signals)
  mvp_jev_ontology.py    -- working MVP of the cascade
  convergence_experiment.py -- 3-iteration convergence test on 52 tickets
  close_loop.py          -- runs v3.0 against a rounded historical v2.0 baseline
  generate_sessions.py   -- runs the three session batches against the
                           real Jev API and prints results
  test_jev_api.py        -- standalone smoke test for the Jev API
  heldout_experiment.py  -- held-out generalization test (36 train / 16
                           held-out; revision authored from train signals)
  heldout_variance.py    -- retains repeated runs and descriptive variance
  experiment_state.py   -- provenance-checked, atomic ticket checkpoints
  test_images.py / test_* -- offline discovery and regression coverage
  run_iter1.py / run_iter2.py -- single-iteration signal dumps used to
                           author the v4.0 / v5.0 revisions
  convergence_results.json -- saved results of the 3-iteration run
  heldout_results.json    -- saved results of the held-out test
  heldout_split.json      -- deterministic train/held-out split (seed 42)
  Images/                 -- sub-project: classifying digitized image
                           collections against a revisable taxonomy via
                           Pixtral + Jev (five facets, calibrated
                           confidence, review routing); ten taxonomy
                           versions, a 240-image stand-in corpus with
                           complete ground truth, and a pre-registered
                           fresh-corpus replication on Smithsonian
                           material (97.0-97.5% pooled agreement on 140
                           hand-verified records; see Images/README.md;
                           personal-image data is private; public
                           replication manifests/results are committed)
```

## The MVP

`mvp_jev_ontology.py` demonstrates the full pipeline end to end:

1. **Ontology** -- a 3-level, 12-leaf taxonomy of customer support tickets
   for a SaaS product, authored by an LLM (Mistral Vibe) and stored in
   `ontology.json`. The ontology is loaded at runtime, not hardcoded in
   the script. The `_meta` key records the version, author, and prompt
   used to generate it. To use a different ontology, replace the JSON
   file -- the script adapts automatically.

2. **Recursive classification** -- each ticket walks the tree top-down. At
   each node, Jev is asked a Choice question over the node's children, using
   the child class definitions as criteria. The winner is descended into,
   and the process repeats until a leaf is reached.

3. **Confidence tracking** -- each level's returned `confidence` field
   multiplies into a cumulative score. This is not the same field as the
   choice distribution, nor a proven calibrated probability of leaf accuracy.
   The score is used as an exploratory review signal.

4. **Feedback loop** -- after all tickets are classified, the pipeline
   reports:
   - **Zero-traffic classes** -- leaves that received no items, candidates
     for removal or merging.
   - **Low-confidence items** -- tickets where the cumulative confidence
     fell below 0.5, suggesting the relevant class definitions need
     tightening.
   - **Low-margin decisions** -- levels where the top two options were
     within 0.15 of each other, indicating overlapping definitions.
   - **Ambiguous tickets** -- tickets that span two sub-trees (e.g.,
     "charged twice and can't access account" touches both Billing and
     Account), suggesting the ontology needs a multi-label or compound-issue
     class.

### Running it

```powershell
# With a real Jev API key (uses the live TypeSafe API):
$env:TYPESAFE_API_KEY = 'your-key-here'
python mvp_jev_ontology.py

# Without a key (falls back to a keyword-based mock that returns the
# same data shape, so the pipeline logic still runs):
Remove-Item Env:TYPESAFE_API_KEY -ErrorAction SilentlyContinue
python mvp_jev_ontology.py
```

Python 3.10+. No dependencies beyond the standard library.

### Safe experiment runs

Ticket experiments use `experiment_state.py` with the same atomic,
revision-checked JSON store as Images. Each completed ticket is saved with
its full path, distributions, confidence, token count, and response model
identifier when provided. The output also retains the ontology and input
snapshots. A failed ticket is saved as an error and stops the run; restarting
retries it without reclassifying completed tickets.

Defaults are `convergence.results.json`, `heldout.train.results.json`,
`heldout.holdout.results.json`, `heldout.both.results.json`,
`variance.results.json`, `sessions.results.json`, `closed_loop.results.json`,
and `iteration.<version>.results.json`. These files are gitignored.
`RESULTS_OUT` selects a different **`*.results.json`** file, relative to the
repository root or absolute. Use a fresh filename for an independent repeat,
changed corpus, changed ontology, or changed implementation. A matching
completed run can be reported again without an API key or new calls.
Reported tokens/cost represent the whole stored run, including resumed work.

The held-out runner defaults to **train only**:

```powershell
python heldout_experiment.py ontology.json
# Author and freeze a revision using only the training signals.
$env:RESULTS_OUT = 'revision.holdout.results.json'
python heldout_experiment.py ontology_heldout_v1.json --stage holdout
Remove-Item Env:RESULTS_OUT
```

`--stage both` is explicit opt-in evaluation, not a train-only authoring
workflow. `--save` labels a run; it does not select its output file.
`SPLIT_PATH` selects a separate split for a new corpus. Splits must cover
distinct ticket texts exactly once, with no overlap, and are bound to the
ordered corpus. The original index-only split is accepted only with its
exact historical corpus and partition fingerprints; it is not rewritten.

Legacy `convergence_results.json` and `heldout_results.json` are never
overwritten or automatically relabeled. `jev-latest` is a provider alias:
reported model-version changes within a run are rejected, but an unchanged
identifier is not proof of immutable remote weights. Missing response model
identifiers are retained as unknown, not replaced with a claimed version.
`close_loop.py` compares against a rounded historical v2 transcript, not a
fresh v2 run. The single-iteration wrappers retain full flagged-ticket and
low-margin signal dumps, including when reporting a completed checkpoint.

### What the output looks like

```
Ticket: I was charged twice and now I can't access my account.
  Leaf: LoginProblem  (confidence 0.257)
  Path:
    -> AccountAndAccess (p=0.260)  [AccountAndAccess:0.51, BillingAndPayments:0.49, TechnicalAndProduct:0.00]
    -> LoginProblem (p=0.990)  [LoginProblem:1.00, SecurityConcern:0.00, AccessRequest:0.00, AccountManagement:0.00]
```

The near-tie at level 1 (0.51/0.49) and the resulting 0.257 cumulative
confidence is the signal that this ticket spans two sub-trees. The feedback
loop catches it and suggests re-prompting the LLM to add a compound-issue
class.

## Results

`SESSIONS.md` contains authentic session logs from five real Jev API runs
(190 classification passes over 78 unique tickets, 380 Jev calls,
~204K input tokens, $0.0085 cost):

- **Session 1: Mixed batch** (12 tickets) -- 11 at 0.99+ confidence,
  1 compound ticket flagged at 0.257.
- **Session 2: Billing-heavy** (8 tickets) -- reveals a "billing triangle"
  where RefundRequest, PaymentFailure, and SubscriptionChange overlap.
- **Session 3: Edge cases** (6 tickets) -- prompt-injection resisted (2%
  shift), vague ticket routed to 0.300, cross-domain tickets flagged.
- **Session 4: Closed loop** (8 tickets) -- ontology revised to v3.0,
  all 3 hedged tickets improved from 0.56-0.68 to 1.000 confidence.
- **Session 5: Convergence** (52 tickets, 3 iterations) -- mean confidence
  0.940 -> 0.945 -> 0.948. Converges in a weak sense with diminishing
  returns. See `CONVERGENCE.md`.

See also `RESULTS.md` for the signed assessment and `LOOP.md` for the
first closed-loop experiment.

To run the workflows again: `python generate_sessions.py`,
`python close_loop.py`, and `python convergence_experiment.py` (new work
requires `TYPESAFE_API_KEY`). Fresh runs may differ from the historical
transcripts; use the output/resume rules above.

## Caveats

- **Adversarial text moves Jev.** Jev treats state as data, not as hostile
  input. Injected instructions in the state can shift its classification.
  Keep deterministic checks in the loop for safety-critical paths.
- **Eval on your data.** Run evals on your own tickets before replacing an
  existing classifier. The right comparison is "Jev vs the cheapest
  acceptable system for this decision," not "Jev vs ChatGPT" in the
  abstract.
- **Garbage in, garbage out.** Jev classifies against whatever ontology you
  hand it, cleanly and confidently. Validate the LLM-authored ontology
  (coverage, disjointness, definition clarity) before trusting Jev's output.
- **Version your ontology.** If you regenerate the ontology with the LLM,
  class boundaries may shift. Tag each Jev decision with the ontology
  version so stale decisions can be detected.
- **Separate model confidence from schema confidence.** If your schema has
  its own confidence/validity field, keep that distinct from Jev's
  probability so the two meanings don't collide.

See `IDEAS.md` for the full list of eight approaches and a deeper
discussion of the "most promising" cascade pattern.

---

## About

This project was produced as a workshop between Dagfinn Dybvig and
Mistral Vibe on 2026-09-21.
