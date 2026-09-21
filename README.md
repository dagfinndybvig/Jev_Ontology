# Ontology + Jev

Exploring how to pair [Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev),
TypeSafe AI's "System One" decision model, with ontologies.

## TL;DR -- what we learned

We built a working MVP that pairs an LLM-authored ontology with Jev's
calibrated classification, tested it against the live Jev API on 86 real
tickets across 5 sessions, closed the feedback loop, and ran a 3-iteration
convergence experiment. Total cost: $0.0085.

**1. The feedback loop converges.** Jev's low-confidence signals
identified a genuine gap in the billing sub-tree. The LLM revised the
ontology (added a WrongfulCharge class). Re-running the same tickets,
all three hedged tickets improved from 0.56-0.68 to 1.000 confidence.
One iteration, one revision, real improvement. No clean ticket got
meaningfully worse.

**2. Jev's calibration is a diagnostic tool, not just a classifier.**
The 0.14 probability on RefundRequest for a duplicate-charge ticket
wasn't noise -- it pointed at a real semantic gap. Adding the class
that gap implied eliminated the hedging. The probabilities are a map of
where the ontology is incomplete.

**3. Perfect confidence is a double-edged signal.** The jump from 0.560
to 1.000 after one revision is large enough that the new class may be
slightly too broad. A 3% side effect on the "unrecognized charge"
ticket confirms this. Perfect confidence on a too-broad class hides
ambiguity instead of surfacing it.

**4. The full cycle costs effectively nothing.** Authoring the ontology,
classifying 86 tickets, detecting the billing triangle, revising, and
re-running: $0.0085 total. The feedback loop can run on every batch
without budget as a constraint.

**5. Convergence tested (3 iterations, 52 tickets).** The feedback
loop produces monotonically improving mean confidence (0.940 ->
0.945 -> 0.948) and decreasing flagged tickets (3 -> 2 -> 2). Leaf
assignments are highly stable: only 1 of 52 tickets changed leaf
class across two ontology revisions. But the system has a floor
(genuinely compound tickets that need multi-label, not better
definitions) and revisions have side effects (fixing one gap
opened a new one on a previously clean ticket). The loop converges
in a weak sense -- diminishing returns, not perfect confidence.
See `CONVERGENCE.md`.

**6. The shape of convergence.** The system approaches a steady state
where further revisions trade improvements against regressions. It
does not converge on perfect confidence. It converges on the best
categories this revision mechanism can find for this dataset. The
gap between "best achievable" and "perfect" is the irreducible
residue of compound cases and side effects -- which is exactly what
the philosophical framing predicted.

**The biggest takeaway:** the cascade is not just a pipeline, it's a
learning loop. Jev's calibrated probabilities are the error signal, the
LLM is the optimizer, and the ontology is the model being trained. We
ran three gradient steps. The first worked dramatically. The later ones
showed diminishing returns and side effects. The process converges in
a weak sense, not a strong one -- which is more honest, and more
interesting, than either "it works perfectly" or "it doesn't work."

See `RESULTS.md` for the full assessment, `CONVERGENCE.md` for the
3-iteration experiment, `LOOP.md` for the first closed-loop experiment,
`PHILOSOPHY.md` for the connection to induction and Jevons, and
`SESSIONS.md` for all session logs.

---

## What is Jev?

Jev is a model that returns **typed, probabilistic decisions** instead of
generating text. You send it a *state* (the context to evaluate) and a set of
typed *questions* (Choice, Score, or Noul), and it returns calibrated answers
with probabilities in a single parallel pass.

| Property | Value |
|---|---|
| Endpoint | `POST https://api.typesafe.ai/v1/systemone` |
| Model | `jev-latest` (currently `jev-1.13.0`) |
| Speed | 70-500ms end-to-end (~256ms median) |
| Cost | $0.042 per million input tokens, output free |
| Question types | Choice (pick one of N, up to 255), Score (rate on a 2-10 scale), Noul (yes/no probability) |
| Key env var | `TYPESAFE_API_KEY` |

Because Jev returns probabilities rather than text, it cannot hallucinate or
produce type errors -- it only returns values you defined in the question
schema. That makes it a good fit for repetitive classification against a
fixed ontology.

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
  ontology.json          -- LLM-authored ontology v2.0 (3 levels, 12 leaves)
  ontology_v3.json       -- revised ontology v3.0 (13 leaves, adds
                           WrongfulCharge based on Jev feedback signals)
  ontology_v4.json       -- revised ontology v4.0 (sharpens
                           BugReport/IntegrationProblem boundary,
                           SecurityConcern covers GDPR)
  ontology_v5.json       -- revised ontology v5.0 (AccountAndAccess covers
                           compliance/data handling at level 1)
  mvp_jev_ontology.py    -- working MVP of the cascade
  convergence_experiment.py -- 3-iteration convergence test on 52 tickets
  close_loop.py          -- re-runs Session 2 tickets against v2.0 and v3.0
  generate_sessions.py   -- runs the three session batches against the
                           real Jev API and prints results
  test_jev_api.py         -- standalone smoke test for the Jev API
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

3. **Confidence tracking** -- each level's probability multiplies into a
   cumulative confidence. Low overall confidence flags tickets that span
   multiple sub-trees.

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

```bash
# With a real Jev API key (uses the live TypeSafe API):
set TYPESAFE_API_KEY=your-key-here
python mvp_jev_ontology.py

# Without a key (falls back to a keyword-based mock that returns the
# same data shape, so the pipeline logic still runs):
python mvp_jev_ontology.py
```

Python 3.10+. No dependencies beyond the standard library.

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

`SESSIONS.md` contains authentic session logs from three real Jev API runs
(26 tickets total, 52 Jev calls, ~25K input tokens, $0.001 cost):

- **Session 1: Mixed batch** (12 tickets) -- 11 classified at 0.99+
  confidence, 1 compound ticket flagged at 0.257.
- **Session 2: Billing-heavy** (8 tickets) -- reveals a "billing triangle"
  where RefundRequest, PaymentFailure, and SubscriptionChange overlap,
  with three tickets hedging at 0.56-0.68 confidence.
- **Session 3: Edge cases** (6 tickets) -- a prompt-injection attempt Jev
  resisted (2% shift), a vague ticket correctly routed to 0.300 confidence,
  and two cross-domain tickets producing genuine low-confidence signals.

To reproduce: `python generate_sessions.py` (requires `TYPESAFE_API_KEY`).

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
