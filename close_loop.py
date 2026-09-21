"""Close the loop: re-run Session 2 billing tickets against ontology v2.0
and v3.0, then compare confidence to see if the revised definitions reduced
hedging."""
import json
import os
import urllib.request

API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
ENDPOINT = "https://api.typesafe.ai/v1/systemone"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_ontology(filename):
    with open(os.path.join(SCRIPT_DIR, filename), "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("_meta", {})
    onto = {k: v for k, v in data.items() if k != "_meta"}
    return onto, meta.get("version", "unknown")


def jev_choice(item_text, children, parent):
    criteria = {c["id"]: c["definition"] for c in children}
    state = (
        f"Support ticket to classify:\n\"{item_text}\"\n\n"
        f"Ontology context: \"{parent['label']}\" -- {parent['definition']}\n"
        f"Choose the most specific sub-class this ticket belongs to."
    )
    body = {
        "model": "jev-latest",
        "state": state,
        "questions": {
            "classify": {
                "type": "choice",
                "instructions": f"Which sub-class of \"{parent['label']}\" does this ticket belong to?",
                "criteria": criteria,
            }
        },
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    answer = data["answers"]["classify"]
    return {
        "choice": answer["choice"],
        "confidence": answer["confidence"],
        "distribution": answer["probabilities"],
        "usage": data.get("usage", {}),
    }


def classify_item(item_text, ontology):
    path = []
    current = ontology
    confidence = 1.0
    total_tokens = 0
    while current.get("children"):
        children = current["children"]
        result = jev_choice(item_text, children, current)
        total_tokens += result["usage"].get("input_tokens", 0)
        top_id = result["choice"]
        confidence *= result["confidence"]
        child_node = next(c for c in children if c["id"] == top_id)
        path.append({
            "node": top_id,
            "confidence": result["confidence"],
            "distribution": result["distribution"],
        })
        current = child_node
    leaf = path[-1]["node"] if path else ontology["id"]
    return {"path": path, "leaf": leaf, "overall_confidence": confidence, "tokens": total_tokens}


# The Session 2 billing tickets
SESSION2_TICKETS = [
    "My payment failed and I need to update my card details.",
    "I was charged for a plan I already cancelled last month.",
    "Can I get a refund for the unused portion of my annual subscription?",
    "I see a charge on my statement I don't recognize, can you explain it?",
    "I want to switch from monthly to annual billing to save money.",
    "The invoice shows the wrong company name and address.",
    "You charged me twice for the same subscription period.",
    "I cancelled my subscription but you still charged my card.",
]

# The three that hedged (the billing triangle)
HEDGED_TICKETS = [
    "I was charged for a plan I already cancelled last month.",
    "You charged me twice for the same subscription period.",
    "I cancelled my subscription but you still charged my card.",
]

# Session 2 results (from SESSIONS.md, captured 2026-09-21)
V2_RESULTS = {
    "My payment failed and I need to update my card details.": {"leaf": "PaymentFailure", "conf": 1.000},
    "I was charged for a plan I already cancelled last month.": {"leaf": "RefundRequest", "conf": 0.560},
    "Can I get a refund for the unused portion of my annual subscription?": {"leaf": "RefundRequest", "conf": 1.000},
    "I see a charge on my statement I don't recognize, can you explain it?": {"leaf": "InvoiceQuestion", "conf": 1.000},
    "I want to switch from monthly to annual billing to save money.": {"leaf": "SubscriptionChange", "conf": 1.000},
    "The invoice shows the wrong company name and address.": {"leaf": "InvoiceQuestion", "conf": 1.000},
    "You charged me twice for the same subscription period.": {"leaf": "PaymentFailure", "conf": 0.680},
    "I cancelled my subscription but you still charged my card.": {"leaf": "RefundRequest", "conf": 0.630},
}


def main():
    onto_v2, ver_v2 = load_ontology("ontology.json")
    onto_v3, ver_v3 = load_ontology("ontology_v3.json")

    print("=" * 78)
    print("CLOSED LOOP: Ontology v2.0 -> v3.0 comparison on Session 2 billing tickets")
    print(f"v2.0 ontology: {ver_v2}")
    print(f"v3.0 ontology: {ver_v3}")
    print("=" * 78)

    # Re-run ALL 8 Session 2 tickets against v3.0
    print("\n--- Re-running all 8 tickets against v3.0 ---\n")
    v3_results = {}
    total_tokens = 0
    for ticket in SESSION2_TICKETS:
        r = classify_item(ticket, onto_v3)
        v3_results[ticket] = {"leaf": r["leaf"], "conf": r["overall_confidence"], "path": r["path"]}
        total_tokens += r["tokens"]
        print(f"Ticket: {ticket}")
        print(f"  v2.0: {V2_RESULTS[ticket]['leaf']} (conf={V2_RESULTS[ticket]['conf']:.3f})")
        print(f"  v3.0: {r['leaf']} (conf={r['overall_confidence']:.3f})")
        for step in r["path"]:
            dist = ", ".join(f"{k}:{v:.2f}" for k, v in
                             sorted(step["distribution"].items(), key=lambda x: x[1], reverse=True))
            print(f"    -> {step['node']} (p={step['confidence']:.3f})  [{dist}]")
        print()

    # Summary comparison table
    print("\n" + "=" * 78)
    print("COMPARISON TABLE")
    print("=" * 78)
    print(f"\n{'Ticket':<55} {'v2.0 leaf':<20} {'v2.0 conf':<10} {'v3.0 leaf':<20} {'v3.0 conf':<10} {'Delta':<8}")
    print("-" * 123)
    for ticket in SESSION2_TICKETS:
        v2 = V2_RESULTS[ticket]
        v3 = v3_results[ticket]
        delta = v3["conf"] - v2["conf"]
        print(f"{ticket[:54]:<55} {v2['leaf']:<20} {v2['conf']:<10.3f} {v3['leaf']:<20} {v3['conf']:<10.3f} {delta:+.3f}")

    # Focus on the hedged tickets
    print("\n" + "=" * 78)
    print("FOCUS: The 3 hedged tickets (the billing triangle)")
    print("=" * 78)
    for ticket in HEDGED_TICKETS:
        v2 = V2_RESULTS[ticket]
        v3 = v3_results[ticket]
        delta = v3["conf"] - v2["conf"]
        improved = "IMPROVED" if delta > 0.05 else ("WORSE" if delta < -0.05 else "FLAT")
        print(f"\n  '{ticket[:60]}'")
        print(f"  v2.0: {v2['leaf']} (conf={v2['conf']:.3f})")
        print(f"  v3.0: {v3['leaf']} (conf={v3['conf']:.3f})")
        print(f"  Delta: {delta:+.3f}  [{improved}]")

    # Aggregate stats
    print("\n" + "=" * 78)
    print("AGGREGATE")
    print("=" * 78)
    v2_confs = [V2_RESULTS[t]["conf"] for t in SESSION2_TICKETS]
    v3_confs = [v3_results[t]["conf"] for t in SESSION2_TICKETS]
    v2_hedged = [V2_RESULTS[t]["conf"] for t in HEDGED_TICKETS]
    v3_hedged = [v3_results[t]["conf"] for t in HEDGED_TICKETS]

    print(f"\nAll 8 tickets:")
    print(f"  v2.0 mean confidence: {sum(v2_confs)/len(v2_confs):.3f}")
    print(f"  v3.0 mean confidence: {sum(v3_confs)/len(v3_confs):.3f}")
    print(f"\n3 hedged tickets only:")
    print(f"  v2.0 mean confidence: {sum(v2_hedged)/len(v2_hedged):.3f}")
    print(f"  v3.0 mean confidence: {sum(v3_hedged)/len(v3_hedged):.3f}")
    print(f"  Improvement: {sum(v3_hedged)/len(v3_hedged) - sum(v2_hedged)/len(v2_hedged):+.3f}")
    print(f"\nv3.0 cost: {total_tokens} input tokens = ${total_tokens * 0.042 / 1_000_000:.4f}")


if __name__ == "__main__":
    main()
