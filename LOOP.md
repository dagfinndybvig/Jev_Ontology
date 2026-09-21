# Closed Loop: Ontology Revision Driven by Jev Feedback

**Date:** 2026-09-21
**Author:** Mistral Vibe (mistral-vibe)
**Jev model:** jev-latest (jev-1.13.0)
**Cost:** $0.0004 (9,024 input tokens, 16 Jev calls)

---

## What was tested

Session 2 revealed a "billing triangle": three tickets that hedged between
RefundRequest, PaymentFailure, and SubscriptionChange, all involving
charges that should not have happened:

| Ticket | v2.0 leaf | v2.0 confidence | Runner-up |
|---|---|---|---|
| Charged for a plan I already cancelled | RefundRequest | 0.560 | InvoiceQuestion 0.22 |
| Charged twice for same subscription period | PaymentFailure | 0.680 | RefundRequest 0.14 |
| Cancelled subscription but still charged | RefundRequest | 0.630 | SubscriptionChange 0.16 |

The hypothesis: the ontology's billing definitions overlapped. The fix:
add a `WrongfulCharge` class for "charges that should not have happened"
and sharpen the sibling definitions so the boundary is clear.

## What changed (v2.0 -> v3.0)

**Added:** `WrongfulCharge` -- "The customer was charged successfully but
the charge should not have happened. Includes duplicate charges, charges
after cancellation, and charges for cancelled plans. The root cause is a
billing system error, not a payment processing failure."

**Sharpened:**
- `PaymentFailure`: now explicitly excludes successful charges that
  should not have been made. Focuses on declined/failed/expired-card
  payments where the payment did not go through.
- `RefundRequest`: now explicitly excludes billing errors (use
  WrongfulCharge). Focuses on proactive money-back requests for
  legitimate charges the customer is unhappy with.
- `SubscriptionChange`: now explicitly about forward-looking plan
  changes, not correcting past charges.

## Result

All 8 Session 2 tickets re-run against v3.0:

| Ticket | v2.0 leaf | v2.0 conf | v3.0 leaf | v3.0 conf | Delta |
|---|---|---|---|---|---|
| My payment failed and I need to update my card details. | PaymentFailure | 1.000 | PaymentFailure | 1.000 | +0.000 |
| I was charged for a plan I already cancelled last month. | RefundRequest | **0.560** | WrongfulCharge | **1.000** | **+0.440** |
| Can I get a refund for the unused portion of my annual subscription? | RefundRequest | 1.000 | RefundRequest | 1.000 | +0.000 |
| I see a charge on my statement I don't recognize, can you explain it? | InvoiceQuestion | 1.000 | InvoiceQuestion | 0.960 | -0.040 |
| I want to switch from monthly to annual billing to save money. | SubscriptionChange | 1.000 | SubscriptionChange | 1.000 | +0.000 |
| The invoice shows the wrong company name and address. | InvoiceQuestion | 1.000 | InvoiceQuestion | 1.000 | +0.000 |
| You charged me twice for the same subscription period. | PaymentFailure | **0.680** | WrongfulCharge | **1.000** | **+0.320** |
| I cancelled my subscription but you still charged my card. | RefundRequest | **0.630** | WrongfulCharge | **1.000** | **+0.370** |

## The three hedged tickets

All three now classify as `WrongfulCharge` at 1.000 confidence:

```
v2.0: RefundRequest  (0.560)  ->  v3.0: WrongfulCharge  (1.000)  +0.440
v2.0: PaymentFailure (0.680)  ->  v3.0: WrongfulCharge  (1.000)  +0.320
v2.0: RefundRequest  (0.630)  ->  v3.0: WrongfulCharge  (1.000)  +0.370
```

The hedging is gone. Each ticket that previously split probability across
two or three classes now lands cleanly on a single class. The new class
captured exactly the semantic gap the feedback loop identified.

## Aggregate

| Metric | v2.0 | v3.0 |
|---|---|---|
| Mean confidence (all 8 tickets) | 0.859 | 0.995 |
| Mean confidence (3 hedged tickets) | 0.623 | 1.000 |
| Improvement (hedged tickets) | -- | +0.377 |

One previously-clean ticket shifted slightly: "I see a charge on my
statement I don't recognize" dropped from 1.000 to 0.960, with 3% now
going to WrongfulCharge. This is a minor side effect -- the unrecognized
charge could be wrongful, so the hedging is not wrong. No ticket got
worse by more than 0.04.

## What this proves

The feedback loop converges. Jev's low-confidence signals from v2.0
identified a genuine gap in the ontology (no class for "charge that
should not have happened"). An LLM revised the ontology based on those
signals. Re-running against v3.0, the same tickets that hedged at
0.56-0.68 now classify at 1.000 -- and the previously clean tickets
stayed clean.

This is the full cycle: **LLM authors -> Jev filters -> feedback signals
-> LLM revises -> Jev re-filters -> confidence improves.**

## What it does not prove

- **One revision, one batch.** This is a single loop iteration on 8
  tickets. Convergence over multiple iterations on a larger dataset is
  untested. The revision could introduce new ambiguities that only
  surface on different tickets.
- **The 1.000 confidences are suspicious.** Going from 0.560 to 1.000
  is a large jump. It could mean the new class is genuinely a better
  fit, or it could mean the definition is broad enough that Jev routes
  anything charge-related there. The "unrecognized charge" ticket
  dropping to 0.960 is a hint that the new class may be slightly too
  broad.
- **No held-out test.** We revised the ontology and re-ran the same
  tickets. A proper evaluation would revise on a training set and
  measure on a held-out set to confirm the improvement generalizes
  beyond the tickets that generated the signal.

## Cost

$0.0004 for 8 tickets x 2 levels = 16 Jev calls, 9,024 input tokens.
The closed loop -- feedback detection plus re-run -- cost less than
one cent.

---

*Signed: Mistral Vibe (mistral-vibe), 2026-09-21T11:10:24Z*
