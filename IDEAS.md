# Jev + Ontologies: Ideas

Jev is TypeSafe AI's "System One" model. It returns typed, probabilistic
decisions (Choice, Score, Noul, probabilities) in a single parallel pass
instead of generating text — ~40-200x faster and ~40-400x cheaper than
frontier LLMs on classification tasks ($0.042/MTok input, free output,
median end-to-end latency ~256ms). That profile maps onto ontology work,
where the recurring problem is "given this state, which node / term / type
does it belong to, and how sure are we?"

Primitives (from TypeSafe docs): Choice (pick among options), Score
(rate relevance/quality), Noul (retrieve/filter), confidence/calibration
(probabilities you can route on).

References that informed these notes:
- TypeSafe launch post: https://typesafe.ai/blog/introducing-system-one-models-and-jev
- DataCamp overview: https://www.datacamp.com/blog/system-one-models-jev
- Pydantic docs (integration + caveats): https://pydantic.dev/docs/ai/models/typesafe/
- LangChain guide: https://www.langchain.com/blog/building-a-harness-with-jev
- DEV.to practical guide: https://dev.to/valyuai/how-to-use-jev-a-practical-guide-to-typesafes-system-one-model-g5e
- Kingy AI review: https://kingy.ai/blog/typesafe-jev-review-the-ai-model-that-doesnt-generate-text/
- Awesome-Jev-TypeSafe (community projects): https://github.com/jexp/awesome-jev-typesafe
  - Includes `jev-folio-recursive-classifier` (FOLIO Document Types ontology,
    recursive Choices, beam search, confidence-gated leaf stopping).
  - Includes `jev-benchmark`, `jev-research-eval`, `jev-playground`.
- ai4curation gene-review issue (VDCL validity taxonomy with Jev):
  https://github.com/ai4curation/ai-gene-review/issues/3062

---

## 1. Recursive / hierarchical classification down the tree

Most natural fit. Already has a reference implementation
(`jev-folio-recursive-classifier`).

- Walk the ontology top-down.
- At each node, ask Jev a Choice over that node's children.
- Descend the winner; stop at a leaf when confidence clears a gate or when
  a leaf is reached.
- Add beam search (keep top-k branches per level) to recover from a wrong
  early pick.
- Jev returns all probabilities in parallel, so a per-level multi-child
  Choice is cheap.

Good for: legal documents (FOLIO), clinical notes (SNOMED CT), product
catalogs (Google Product Taxonomy / Schema.org), financial instruments
(FIBO), gene/protein function (GO / EC).

## 2. Ontology term assignment / entity linking

Retrieve candidate terms by lexical or embedding similarity, then:
- Use Jev Score to rerank candidates against the passage.
- Final Choice among the top-k.
- Low cost ($0.042/MTok + free output) lets you score many candidates per
  query without blowing the context budget.

Good for: document-to-term tagging, named entity grounding, knowledge-graph
slot filling.

## 3. Multi-label mapping onto a broad taxonomy

Jev emits all probabilities in parallel rather than autoregressively, so
mapping a record to multiple co-occurring ontology terms is a single call.

- Use calibrated probabilities to set an inclusion threshold rather than
  hard-coding top-1.
- Examples: clinical note -> several SNOMED findings; financial instrument
  -> multiple FIBO categories; product -> multiple Schema.org types.

Good for: rich metadata tagging where one record spans several concepts.

## 4. Validation / consistency gate during ontology population

When ingesting new instances or asserted axioms:
- Ask Jev a Choice ("does this assertion fit under class X?") before
  writing it.
- Calibration lets the pipeline abstain and escalate uncertain assertions
  to a deterministic reasoner or a human.
- Per the Pydantic docs: a Jev-built guard belongs *alongside* deterministic
  checks, not instead of them, since adversarial text in the state can
  move Jev's classification.

Good for: ETL into a knowledge graph, schema conformance gates, data
quality pipelines.

## 5. Evidence-grounded assessment into a validity taxonomy

Template from the ai4curation gene-review issue:
- Assemble a bounded evidence dossier (provenance-tagged).
- Do exact ontology lookups / comparisons in code.
- Have Jev make the final typed judgment (a Choice over the validity
  categories) and report a calibrated confidence.
- Keep the model's probability separate from any schema-defined
  confidence score (don't conflate the two).

Good for: curation workflows, scientific claim validation, gene/protein
function prediction assessment (VDCL), systematic review triage.

## 6. Routing queries to the right ontology / namespace

Use Jev as the fast decision layer that classifies an incoming query by
domain and routes it to the matching ontology-backed module; escalate
only the hard minority to a frontier LLM.

This is TypeSafe's recommended "cascade" pattern: Jev classifies and
routes cheaply, code enforces policy, a frontier model writes the reply.

Good for: multi-domain assistants, federated knowledge graphs, search
front-ends that span several ontologies.

## 7. Subsumption / "is-a" questions as classification

Pose `is X a subtype of Y?` as a Choice.
- Won't replace an OWL reasoner for formal entailment.
- But for fuzzy or text-described entities where formal reasoning can't
  run, a calibrated probabilistic answer is useful.
- Fast enough (~256ms) to ask at query time over many candidate parents.

Good for: autocomplete on class hierarchy, suggesting placement of a new
entity, relaxing rigid OWL where descriptions are textual.

## 8. RAG relevance filtering backed by the ontology

Retrieve wide, then run a Jev Noul/Choice per passage to filter for
ontology-relevance before anything expensive sees the context window.

TypeSafe's own RAG and citation-check cookbooks use this shape; the
filter costs less than the context it saves.

Good for: ontology-grounded Q&A, knowledge-base search, literature
retrieval scoped to a sub-tree of an ontology.

---

## Most promising: LLM-authored ontology, Jev-filtered

The cascade that plays to each model's strengths:

`LLM authors the ontology (expensive, infrequent) → Jev filters/classifies against it (cheap, high-volume, per item)`

The key constraint is that Jev can't generate the ontology itself — it
returns decisions, not text. So the LLM does the authoring step and
produces a materialized ontology (classes, hierarchy, definitions,
properties) as structured state. Jev then consumes that state plus each
item and returns a Choice/Score/Noul decision.

Why this works well:
- **Right tool per step.** Authoring an ontology is a generative,
  exploratory task — that's what LLMs are for. Filtering thousands of
  items against a fixed ontology is a repetitive classification task —
  that's what Jev is for, at ~40-200x the speed and a fraction of the
  cost.
- **Jev takes the ontology as state.** Pass the class definitions,
  hierarchy, and scope notes as input (natural language + structured
  JSON), and Jev decides which class each item belongs to. No retraining
  per ontology — just swap the state.
- **Feedback loop.** Jev's per-item decisions feed back into refining
  the LLM-authored ontology: classes that get near-zero traffic, classes
  that overlap and confuse Jev, or items Jev is uncalibrated on all
  signal where the ontology needs tightening. Re-run the LLM with those
  signals as input.
- **Validation gate before deploy.** Run Jev as a validation gate on the
  LLM-authored ontology (idea #4) before deploying it: feed sample items
  and check whether Jev distributes them sensibly across classes. If
  everything piles into one class or Jev is uncalibrated, send the
  ontology back to the LLM for revision. Cheap to run, catches bad
  ontologies early.

Caveats specific to this two-stage approach:
1. **Garbage in, garbage out.** Jev classifies against whatever ontology
   you hand it, cleanly and confidently. If the LLM produced
   inconsistent, overlapping, or ill-defined classes, Jev's filtering
   will reflect that. Validate the LLM-authored ontology (coverage,
   disjointness, definition clarity) before trusting Jev's output.
2. **Stability across regenerations.** Regenerating the ontology with
   the LLM can shift class boundaries, making Jev's prior decisions
   stale. Version the ontology and tag each Jev decision with the
   ontology version.
3. **Jev still moves on adversarial text.** Items containing injected
   instructions or misleading framing can shift Jev's classification.
   Keep deterministic checks (regex/keyword guards, exact-match
   overrides) in the loop for safety-critical paths.
4. **Eval both stages separately.** Measure the LLM-authored ontology
   (do classes partition the space cleanly?) and Jev's filtering on it
   (calibration, abstention rate, per-class accuracy) separately, so you
   know which stage to fix when the pipeline degrades.

This combines ideas #4 (validation gate) and #6 (routing/cascade) and
sits on top of #1 (recursive classification) as the deployment shape —
which is why it looks like the strongest single direction.

---

## Caveats (apply to all of the above)

1. **Adversarial text moves Jev.** Jev treats state as data, not as
   hostile input. Injected instructions or misleading framing in the
   state can shift its classification. Keep deterministic checks in the
   loop for safety-critical paths.
2. **Eval on your data before replacing anything.** Launch-week demos
   routinely skip this. The right comparison is "Jev vs the cheapest
   acceptable system for this decision," not "Jev vs ChatGPT" in the
   abstract. Measure calibration error, abstention rate, and run-to-run
   variance on your own tickets/records.
3. **A classifier in the loop is a component.** It needs the same
   measurement as any classifier you'd deploy on its own. A router right
   80% of the time sends one request in five to the wrong model, and
   nothing in the run will tell you.
4. **Typed outputs are not biological / domain correctness.** A typed
   decision and a calibrated probability do not establish that the
   assignment is actually correct in the domain. Evaluate confidence on
   your data; don't trust vendor claims blindly.
5. **Separate model confidence from schema confidence.** If your
   ontology schema has its own confidence/validity field, keep that
   distinct from Jev's probability so the two meanings don't collide.

---

## Status: MVP built and validated

The "most promising" cascade above has been implemented as a working MVP
and tested against the live Jev API. See `mvp_jev_ontology.py`,
`ontology.json`, and `SESSIONS.md` in this repository.

What has been validated:
- **LLM-authored ontology.** An LLM (Mistral Vibe) generated a 3-level,
  12-leaf SaaS support-ticket ontology, stored as `ontology.json` with
  metadata (version, author, prompt).
- **Recursive Jev classification.** The MVP walks the tree top-down, asking
  Jev a Choice question at each node, using the child class definitions as
  criteria. No retraining needed -- swap the JSON and the pipeline adapts.
- **Confidence gating works.** 17 of 26 real tickets classified at 0.97+
  confidence. Compound and cross-domain tickets correctly produced low
  confidence (0.25-0.40), flagging them for human review.
- **Adversarial resistance tested.** A prompt-injection attempt moved the
  distribution by 2 percentage points, not enough to change the
  classification. Consistent with TypeSafe's design, but not relied on.
- **Feedback loop is actionable.** Zero-traffic classes, low-margin
  decisions within the billing sub-tree, and the compound-ticket pattern
  all produce concrete signals for re-prompting the LLM.
- **Cost is negligible.** 26 tickets through a 3-level ontology = 52 Jev
  calls, ~25K input tokens, $0.001 total.

What remains to build:
- Beam search (currently greedy descent only; top-k branches per level
  would recover from wrong early picks).
- Multi-label path for compound tickets (currently forced to a single
  leaf).
- Eval harness with calibration error and per-level accuracy metrics.
- Live LLM call for ontology authoring (currently the ontology is
  pre-generated; the script loads it from JSON).
- Run-to-run variance measurement (Jev's determinism across repeated
  calls on the same input).
