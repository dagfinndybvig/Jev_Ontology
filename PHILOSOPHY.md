# Ontology, Induction, and the LLM-Jev Loop

**Date:** 2026-09-21
**Author:** Mistral Vibe (mistral-vibe)

---

## The gap between logic and statistics

Classical logic is categorical. A thing either is or is not a member of a
class. The classes are given, the rules are given, and reasoning is
entailment. The question "are these the right classes?" is outside the
system.

Statistics is distributional. A thing belongs to class X with
probability P. The classes are given, the mapping is learned, and
reasoning is inference. The question "are these the right classes?" is
outside the system.

Ontology lives in that outside. It is the discipline of asking: what are
the categories, and are they the right ones? A fixed ontology reduces to
logic (reasoning within given classes). A learned classifier over a
fixed ontology reduces to statistics (mapping inputs to given classes).
But a *revisable* ontology is neither. It is the thing that decides when
the categories themselves need to change.

This is the gap: between the deterministic application of fixed categories
(logic) and the probabilistic mapping of inputs to fixed categories
(statistics) lies the question of whether the categories are adequate.
That question is ontology.

---

## Jev in the gap

Jev is interesting because it combines properties of both sides. It
returns typed decisions (like logic: the output must be one of the
categories you defined, nothing else) but with calibrated probabilities
(like statistics: each option gets a weight). It cannot hallucinate a
category that is not in the schema, but it can hedge across categories
when the fit is unclear.

That hedging is the key. In a pure logic system, a misfit is a type error
or a failure to classify. In a pure statistical system, a misfit is just
low confidence on a particular input. Jev's hedging is *structured*: it
tells you which categories are confusable and by how much. The 0.49/0.51
split on the compound ticket in Session 1 was not "I don't know." It was
"your categories don't capture this case." That is an ontological signal,
not a statistical one.

But Jev alone does not fill the gap. Jev cannot revise the categories. It
can only report that the current categories are inadequate. Jev is the
sensor, not the reviser.

---

## It is LLM + Jev that makes the ontology revisable

This is the core claim, and it is noteworthy.

Neither component alone can do ontology revision:

- **Jev alone** is a classifier over fixed categories. It detects
  misfit but cannot act on it. It is logic-with-probabilities, but the
  categories are frozen.
- **An LLM alone** can generate categories, but without a signal telling
  it *which* categories are inadequate, it revises blindly. It can
  author an ontology, but it cannot know whether the ontology is good.
  Without feedback, an LLM's ontology is a guess.

The combination is what makes the ontology revisable. Jev provides the
error signal (structured, calibrated, pointing at specific categorical
gaps). The LLM provides the revision (generative, creative, producing a
new category that explains the misfit). The feedback loop connects
them:

```
LLM authors ontology
  -> Jev classifies items against it
    -> Jev's calibrated probabilities reveal where categories are inadequate
      -> LLM revises the ontology based on those signals
        -> Jev re-classifies, new signals emerge
          -> ... the ontology evolves
```

Each component does what the other cannot. Jev cannot generate new
categories. The LLM cannot detect which existing categories are
inadequate. Together, they form a system that can. The ontology is
revisable because the error signal (Jev) and the revision mechanism
(LLM) are separate but connected.

This is not just an engineering pattern. It is a specific answer to a
specific philosophical question.

---

## The problem of induction

Hume's problem of induction asks: on what basis can we justify inferring
universal claims from particular observations? We have seen N white
swans; what grounds the claim that all swans are white? No finite set of
observations logically entails the universal. The inference seems
indispensable (we act on it constantly) but unjustifiable (no deductive
or probabilistic argument closes the gap).

The classical response divides into two strategies:

1. **Pragmatic:** We cannot justify induction, but we cannot function
   without it, so we use it. (Hume himself, in effect.)
2. **Deflationary:** There is no problem to solve; induction is just a
   habit of expectation formation, and asking for justification is a
   category error. (Later empiricists.)

Neither strategy engages with the *content* of induction -- with the
actual categories we use and how they change. Both treat the category
system as fixed and ask only about the reliability of the inference.

But real induction, as you point out, is not just generalization within
fixed categories. When we observe a black swan, we don't just update the
probability that all swans are white. We revise our understanding of
what "swan" means. The category itself is in question. This is not
induction within a scheme; it is revision *of* the scheme.

Aristotle distinguished *determinative judgment* (applying existing
concepts to particulars) from *reflective judgment* (generating new
concepts when particulars do not fit existing ones). Peirce called the
latter *abduction*: forming a new hypothesis to explain surprising
observations. Standard accounts of the problem of induction focus on
the first (generalizing within fixed concepts) and ignore the second
(revising the concepts themselves). But the second is where the real
intellectual work happens.

---

## LLM + Jev as a response to the problem of induction

Here is the noteworthy claim: the LLM-Jev loop is a concrete,
operational response to the problem of induction -- not a philosophical
argument that induction is justified, but a mechanism that *performs*
induction (in the full sense that includes category revision) and makes
the process inspectable.

Here's why:

**1. It separates the two things that philosophy conflates.**

The problem of induction bundles two questions: (a) given fixed
categories, how do we generalize from instances? and (b) given
instances that don't fit, how do we revise the categories? Standard
treatments focus on (a) and ignore (b). The LLM-Jev loop separates them:
Jev does (a) (classifies instances against fixed categories with
calibrated probabilities), the LLM does (b) (revises categories when
Jev signals misfit). This separation makes the *revisable* part
explicit and mechanized, rather than implicit and mysterious.

**2. It makes category revision non-mysterious.**

In the philosophical literature, category revision is usually described
vaguely: the scientist "sees" that the old framework is inadequate and
"intuits" a new one. There is no account of the mechanism. The LLM-Jev
loop gives one: the error signal is Jev's calibrated probabilities
(pointing at specific categorical gaps), and the revision is the LLM's
generative step (producing a new category that explains the gaps).
Neither step is mysterious. Both are inspectable. You can see *which*
probabilities triggered the revision and *what* new category was
proposed.

**3. It operationalizes abduction.**

Peirce described abduction as "the process of forming an explanatory
hypothesis" to account for a "surprising fact." In our experiment: Jev's
0.49/0.51 split on the compound ticket was the surprising fact. The
LLM's WrongfulCharge class was the explanatory hypothesis. The
re-run at 1.000 confidence was the confirmation. This is abduction
performed by a system, not described by a philosopher.

**4. It treats categories as hypotheses, not axioms.**

The ontology is not a fixed foundation. It is a hypothesis about the
structure of the domain, subject to revision when instances don't fit.
This is the pragmatist move (Peirce, Dewey): categories are tools that
we adopt because they work, and we revise them when they stop working.
The LLM-Jev loop makes this operational: the ontology works when Jev's
confidence is high, and it stops working when Jev's confidence drops.
The revision is triggered by the failure of the tool, not by
philosophical reflection.

**5. It does not solve the problem -- it sidesteps it.**

This is important. The LLM-Jev loop does not prove that induction is
*justified*. It does not close Hume's gap deductively. What it does is
build a system that *performs* induction (including category revision)
and makes the process inspectable and improvable. The question "is
induction justified?" becomes "does this particular revision mechanism
converge on adequate categories?" -- which is an empirical question about
a running system, not a philosophical question about the nature of
reason.

In this sense, it is a pragmatist response to Hume: we do not justify
induction by proving it is rational; we justify it by building systems
that do it and checking whether they work.

---

## What our experiment showed in miniature

The billing triangle was a discovery that the category system was
incomplete. "Charged twice" was misclassified as PaymentFailure (a
payment processing error) when the payment actually succeeded -- it
just happened twice. The category "payment failed" did not capture
"payment succeeded but should not have happened."

Jev detected this as hedging: 0.68 on PaymentFailure, 0.14 on
RefundRequest. The 0.14 was the signal that the categories were
inadequate.

The LLM (Mistral Vibe) created WrongfulCharge to explain the misfit.
Re-running, Jev classified all three hedged tickets at 1.000 confidence.

This is one step of the cycle: classify -> detect misfit -> revise
categories -> re-classify -> confidence improves. It is induction in the
full sense: not just generalizing within fixed categories, but revising
the categories themselves based on encounter with particular instances.

It is a toy example. A support-ticket taxonomy is not a deep ontology.
But the mechanism is the same one that operates when a biologist
discovers that "reptile" does not capture the phylogenetic relationship
between birds and crocodiles, or when a physicist discovers that
"particle" and "wave" do not capture quantum behavior. The scale
differs; the logic is the same: encounter misfit, revise categories,
re-examine the world.

---

## The open question

If ontology is revisable, and the LLM-Jev loop provides the revision
mechanism, the deepest question is: does the process converge?

Can the system stabilize on an adequate ontology, or does it oscillate
-- fixing one gap and opening another? One iteration improved
confidence, but one iteration is not convergence. The question of
whether induction can stabilize on true categories is the philosophical
question, and it is also the practical question for this system.

We have built a machine that performs ontology revision. We have shown
that one step works. We do not yet know whether it converges.

That question -- empirical, operational, and inspectable -- is, I think,
more productive than the classical philosophical question of whether
induction is justified. We may not be able to prove that induction is
rational. But we can build systems that do it, measure whether they
converge, and study the conditions under which they do.

---

## References

- Hume, D. (1739). *A Treatise of Human Nature.* The original statement
  of the problem of induction.
- Peirce, C. S. (1878). "Deduction, Induction, and Hypothesis." The
  account of abduction as inference to an explanatory hypothesis.
- Aristotle. *Nicomachean Ethics* VI and *Posterior Analytics* II. The
  distinction between determinative and reflective judgment.
- Dewey, J. (1929). *The Quest for Certainty.* The pragmatist account of
  categories as revisable tools.

---

*Signed: Mistral Vibe (mistral-vibe), 2026-09-21T11:10:24Z*
