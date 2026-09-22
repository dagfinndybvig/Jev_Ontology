# Convergence Experiment: 3 Iterations of the LLM-Jev Feedback Loop

**Date:** 2026-09-21
**Author:** Mistral Vibe (mistral-vibe)
**Jev model:** jev-latest (jev-1.13.0)
**Tickets:** 52 (messier and more realistic than prior sessions -- typos,
vague descriptions, compound issues, wrong customer framing)
**Iterations:** 3 (v3.0 -> v4.0 -> v5.0)
**Total Jev calls:** 312 (52 tickets x 2 levels x 3 iterations)
**Total input tokens:** 170,230
**Total cost:** $0.0071

---

## The question

Does the LLM-Jev feedback loop converge? When Jev detects
category misfits and the LLM revises the ontology, does the next
classification improve? Does the process stabilize, or does it
oscillate -- fixing one gap and opening another?

Prior experiments (LOOP.md) showed one iteration worked. This
experiment runs three iterations on a larger, messier dataset to
test whether the improvement continues and whether the system
introduces new problems while fixing old ones.

---

## What was done

1. Authored 52 support tickets covering all three branches of the
   ontology, including deliberate edge cases: typos, all-caps rants,
   vague tickets ("something is broken, help"), compound tickets
   (multiple issues in one), and adversarial framing.

2. Ran all 52 tickets through Jev against ontology v3.0 (the
   ontology from the closed-loop experiment in LOOP.md).

3. Collected feedback signals: flagged tickets (<0.5 confidence),
   low-margin decisions (top-2 within 0.15), zero-traffic leaves.

4. As the LLM, revised the ontology to v4.0 based on iteration 1
   signals.

5. Re-ran all 52 tickets against v4.0. Collected new signals.

6. As the LLM, revised the ontology to v5.0 based on iteration 2
   signals.

7. Re-ran all 52 tickets against v5.0. Collected final signals.

8. Compared leaf assignments, confidence, and signal counts across
   all three iterations.

---

## Results

### Aggregate metrics

| Metric | Iter 1 (v3.0) | Iter 2 (v4.0) | Iter 3 (v5.0) |
|---|---|---|---|
| Mean confidence | 0.940 | 0.945 | 0.948 |
| High-confidence (>=0.9) | 46 | 46 | 46 |
| Flagged (<0.5) | 3 | 2 | 2 |
| Low-margin decisions | 2 | 1 | 1 |
| Zero-traffic leaves | 0 | 0 | 0 |
| Input tokens | 53,950 | 56,330 | 59,950 |
| Cost | $0.0023 | $0.0024 | $0.0025 |

Mean confidence increased monotonically: 0.940 -> 0.945 -> 0.948.
Flagged tickets decreased: 3 -> 2 -> 2. Low-margin decisions
decreased: 2 -> 1 -> 1. All 13 leaf classes had traffic in every
iteration.

### Leaf stability

| Transition | Leaf changes |
|---|---|
| Iter 1 -> Iter 2 | 0 |
| Iter 2 -> Iter 3 | 1 |
| Iter 1 -> Iter 3 | 1 |

Only one ticket changed its leaf classification across all three
iterations. Leaf assignments are remarkably stable -- 51 of 52
tickets classified to the same leaf class in v3.0 and v5.0, despite
two ontology revisions.

### The one leaf change: GDPR ticket

```
"I need to know if you store EU customer data in the US for GDPR
 compliance."

  v3.0: FeatureRequest (0.440)  -- flagged, routed to Technical
  v4.0: FeatureRequest (0.488)  -- flagged, improved but wrong branch
  v5.0: SecurityConcern (1.000)  -- fixed, correct branch at high conf
```

This ticket required two revisions to fix. The first (v4.0) sharpened
the SecurityConcern definition to explicitly cover GDPR and compliance
questions. It improved the confidence slightly (0.440 -> 0.488) but
did not change the routing -- the ticket still went to
TechnicalAndProduct because the level-1 definition for
AccountAndAccess did not mention compliance or data handling. The
second revision (v5.0) added "compliance, data handling, and privacy
questions" to the AccountAndAccess top-level definition, which routed
the ticket correctly at level 1 and produced 1.000 confidence.

---

## Per-ticket analysis of the three signaled tickets

### Ticket 1: Slack notifications (BugReport vs IntegrationProblem)

```
"The Slack notifications stopped working after we changed our
 workspace settings."

  v3.0: IntegrationProblem (0.330)  -- flagged, 50/50 tie at level 2
  v4.0: IntegrationProblem (high confidence)  -- fixed
  v5.0: IntegrationProblem (high confidence)  -- stable
```

**Fix:** Sharpened the BugReport definition to exclude third-party
integration failures ("If a third-party integration stopped working
after an external change, use IntegrationProblem instead"). Added
to IntegrationProblem: "If a previously working integration broke
after the customer changed settings on the third-party side, this
is an integration problem, not a product bug."

**Result:** Fixed in one iteration. The 50/50 tie at level 2
collapsed to a clean IntegrationProblem classification. Stable
in iteration 3.

### Ticket 2: GDPR compliance (level-1 routing failure)

```
"I need to know if you store EU customer data in the US for GDPR
 compliance."

  v3.0: FeatureRequest (0.440)  -- flagged
  v4.0: FeatureRequest (0.488)  -- flagged, slight improvement
  v5.0: SecurityConcern (1.000)  -- fixed
```

**Fix:** Required two iterations. v4.0 sharpened the
SecurityConcern definition to cover GDPR/compliance, but the
fix was at the wrong level -- Jev was routing to
TechnicalAndProduct at level 1 before the SecurityConcern
definition could apply. v5.0 fixed the level-1 definition of
AccountAndAccess to explicitly mention "compliance, data
handling, and privacy questions."

**Result:** Fixed in two iterations. The key learning: ontology
revision must target the level where the misfit occurs. Sharpening
a leaf definition does not help if the routing error is at a
higher level.

### Ticket 3: Triple compound (genuinely unresolvable)

```
"I was charged for something I didn't buy and now I can't log in
 to dispute it because of a 2FA issue."

  v3.0: LoginProblem (0.337)  -- flagged
  v4.0: LoginProblem (0.346)  -- flagged, flat
  v5.0: LoginProblem (0.304)  -- flagged, flat
```

**What happened:** This ticket combines a wrongful charge
(billing), a login problem (account), and a 2FA issue (account
security). No single-label ontology can classify it correctly
because it genuinely belongs to three classes simultaneously.

**Result:** Did not improve across three iterations. This is the
floor of the system -- the minimum confidence it cannot go below
with a single-label ontology. The feedback loop correctly
identifies this ticket as unresolvable, which is itself useful:
it signals that the ontology needs a multi-label path for
compound tickets, not further definition sharpening.

---

## Oscillation check

### A new signal appeared in iteration 3

```
"Can you add SSO support for Azure AD? We can't use the product
 without it at our company."

  v3.0: FeatureRequest (high confidence)  -- not flagged
  v4.0: FeatureRequest (high confidence)  -- not flagged
  v5.0: FeatureRequest (0.366)  -- flagged
```

This ticket was not flagged in iterations 1 or 2 but became
flagged in iteration 3. The v5.0 FeatureRequest definition was
narrowed to exclude "questions about how existing data features
work" (to help separate feature requests from product questions).
This narrowing appears to have made the definition too tight,
causing the SSO feature request -- which is a legitimate feature
request -- to hedge.

This is a mild oscillation signal: fixing one definition
(FeatureRequest, to help the GDPR routing) introduced a new
ambiguity on a previously clean ticket. The ticket was already
classified correctly (FeatureRequest); the revision made it
worse, not better.

### Confidence trajectory

| Transition | Improved | Worsened | Flat |
|---|---|---|---|
| Iter 1 -> 2 | 2 | 5 | 45 |
| Iter 2 -> 3 | 4 | 6 | 42 |

The mean confidence increased, but individual tickets fluctuated.
In iteration 2->3, 4 tickets improved and 6 worsened (by more than
0.01). The SSO ticket above is one of the worsened ones. This
suggests that while the aggregate is improving, the revisions
have side effects on individual tickets.

---

## Interpretation

### What converges

1. **Signal-driven fixes work.** Both signal-driven revisions
   (Slack boundary, GDPR routing) produced correct, stable
   classifications. When Jev's hedging points at a specific
   categorical gap, an LLM revision targeted at that gap fixes
   it.

2. **Mean confidence improves monotonically.** 0.940 -> 0.945
   -> 0.948. The improvement is small and diminishing, but it is
   in the right direction across all three iterations.

3. **Leaf assignments are stable.** Only 1 of 52 tickets changed
   leaf class across three iterations. The ontology revisions
   are not disrupting the classification of tickets that were
   already correct.

### What does not converge

1. **Genuinely compound tickets.** The triple compound ticket
   (wrongful charge + login + 2FA) stayed at ~0.33 across all
   three iterations. No single-label ontology revision can fix
   it. The system has a floor determined by the number of
   genuinely multi-label tickets in the dataset.

2. **Revisions have side effects.** The v5.0 FeatureRequest
   narrowing, intended to help GDPR routing, introduced a new
   low-confidence case (SSO feature request). 6 of 52 tickets
   worsened in iteration 2->3. The system is not monotonically
   improving every ticket -- the aggregate improves while
   individual tickets can regress.

3. **Diminishing returns.** The mean confidence improvement
   shrank each iteration: +0.005, then +0.003. The flagged
   count plateaued at 2 after iteration 2. The easy fixes are
   exhausted quickly; the remaining low-confidence tickets are
   either genuinely compound or require increasingly precise
   definition tuning with side effects.

### The shape of convergence

The system does not converge to 1.000 mean confidence. It
converges toward a floor determined by:

- The fraction of genuinely compound tickets (which need
  multi-label, not better definitions).
- The side effects of each revision on previously clean tickets.

It does converge in a weaker sense: the number of flagged
tickets decreases, the mean confidence increases, and leaf
assignments stabilize. The revisions become progressively less
impactful and the system approaches a steady state where
further revisions trade improvements against regressions.

This is consistent with the philosophical framing in
PHILOSOPHY.md: the ontology is a hypothesis about the structure
of the domain. It can be improved, but it cannot be perfected.
The feedback loop does not converge on true categories; it
converges on the best categories this revision mechanism can
find for this dataset. The gap between "best achievable" and
"perfect" is the irreducible residue of genuinely compound
cases and the side effects of revision.

---

## Cost

| Iteration | Tokens | Cost |
|---|---|---|
| Iter 1 (v3.0) | 53,950 | $0.0023 |
| Iter 2 (v4.0) | 56,330 | $0.0024 |
| Iter 3 (v5.0) | 59,950 | $0.0025 |
| **Total** | **170,230** | **$0.0071** |

Three full iterations of the feedback loop on 52 tickets cost less
than one cent. The per-iteration cost is stable (~$0.0024), so
running 10 iterations would cost roughly $0.025 -- still negligible.

---

## What this suggests and what it does not

The findings below are **tentative and in-sample**. They describe what
the loop does on the 52 tickets that drove the revisions. The held-out
test (next section) shows these gains do not transfer to unseen tickets
beyond noise, so treat them as observations about a fixed dataset, not
as general properties of the mechanism.

**Tentative conclusions (in-sample):**
- The feedback loop produces monotonically improving aggregate
  confidence across multiple iterations on the training set.
- Signal-driven ontology revisions fix specific classification
  problems and the fixes are stable across subsequent iterations.
- Leaf assignments are highly stable -- revisions do not disrupt
  correct classifications.
- The system has a floor it cannot pass: genuinely compound
  tickets that require multi-label classification, not better
  definitions.
- Revisions have side effects: fixing one gap can open another,
  though the aggregate still improves.

**Does not establish:**
- Convergence on a larger or different dataset. 52 tickets is
  still small. A 1000-ticket dataset might reveal different
  patterns.
- Convergence over more iterations. The diminishing returns
  suggest a steady state, but 3 iterations is not enough to
  confirm it. The system might start oscillating at iteration 5
  or 10.
- That the floor is truly irreducible. A multi-label path might
  fix the compound ticket. Beam search might fix the SSO ticket
  by keeping both FeatureRequest and IntegrationProblem as
  candidates. These are untested.
- Generalization to a different domain. The ontology is for
  SaaS support tickets. A legal ontology (FOLIO) or a clinical
  ontology (SNOMED) might behave differently.
- Generalization to held-out tickets. Tested 2026-09-22 (see the
  held-out test below): the loop's improvement does not transfer to
  unseen tickets beyond run-to-run noise.

---

## Held-out generalization test (2026-09-22)

The convergence experiment above measures improvement on the same 52
tickets that drive the revisions. That is in-sample: the revision
signals and the evaluation come from the same tickets, so "improvement"
can just be the ontology memorizing the eval set. This section reports a
held-out test that fixes that.

### Design

1. Split the 52 tickets into **36 train / 16 held-out** (seeded, saved
   to `heldout_split.json`).
2. Classified both sets against the clean `v2.0` baseline (the original
   LLM-authored ontology, uncontaminated by these tickets).
3. Collected revision signals from **train only**.
4. Authored a fresh revision (`ontology_heldout_v1.json`) from those
   train signals alone. The held-out tickets never influenced it.
5. Re-evaluated the held-out set against the revision.

### Results

| | Train (36) | Holdout (16) |
|---|---|---|
| v2.0 baseline | mean 0.901 | mean 0.928 |
| heldout_v1 (train-only revision) | mean 0.914 | mean 0.932 |
| Δ | **+0.013** | **+0.004** |

The train set improved by +0.013. The held-out set improved by +0.004.

### The noise floor

To interpret the +0.004, I re-ran the **same** held-out set against the
**same** `v2.0` ontology five times to measure Jev's run-to-run
variance:

```
mean confidence: 0.9279 -> 0.9324, spread = 0.0045, std = 0.0015
```

The +0.004 holdout "improvement" is entirely inside the ±0.0045 noise
floor. It is not signal.

The per-ticket detail makes this unambiguous. The tickets that improved
on holdout were in branches the revision never touched (billing: the
$49 charge 0.750 -> 0.790, the "charged for pro plan" 0.330 -> 0.400).
The one ticket in the branch the revision *did* touch -- the Stripe
IntegrationProblem -- actually got **worse** (0.768 -> 0.739). The
revision changed nothing in billing, so those "improvements" are pure
sampling variance.

### Verdict

**The loop does not generalize.** The train improvement (+0.013) is real
but in-sample -- the ontology is fitting the tickets that generated its
revision signals. On held-out data the effect is indistinguishable from
noise. This is the overfitting signature.

Two reinforcing observations:

- **Side effects, as predicted.** The revision introduced a *new*
  low-confidence train ticket (the GDPR question, now routing to
  FeatureRequest at 0.447) -- the "fix one gap, open another" pattern.
- **The convergence numbers are suspect.** The headline 0.940 -> 0.945
  -> 0.948 (+0.008) was measured in-sample on the same tickets that
  drove the revisions. Given a noise floor of ~0.0045 on just 16
  tickets, and that the convergence set was in-sample, that +0.008 is
  not strong evidence of convergence.

### What this means for the convergence claim

The in-sample experiment showed the loop improves the ontology on the
tickets it sees. The held-out test shows that improvement does not
transfer to unseen tickets beyond noise. The loop is a reasonable
*classifier-tuning* mechanism for a fixed dataset, but it is not yet
demonstrated to be a *learning* mechanism that produces a better
ontology in general.

The single clean step in the original work (billing triangle ->
WrongfulCharge -> 1.000) was one in-sample revision; the held-out test
shows that kind of gain does not transfer.

---

*Signed: Mistral Vibe (mistral-vibe), 2026-09-21T11:39:12Z*
