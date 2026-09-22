"""
Convergence experiment: run 3 iterations of the LLM-Jev feedback loop
on a 52-ticket set against the live Jev API.

At each iteration:
  1. Classify all tickets against the current ontology
  2. Collect feedback signals (low-confidence, low-margin, zero-traffic)
  3. (LLM step happens between iterations -- ontology files are pre-authored)
  4. Re-classify against the revised ontology

Output: before/after comparison tables and convergence analysis.

Requires TYPESAFE_API_KEY. Run: python convergence_experiment.py
"""

import json
import os
import urllib.request
from collections import Counter

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


def collect_leaves(node, acc):
    if not node.get("children"):
        acc.add(node["id"])
    else:
        for c in node["children"]:
            collect_leaves(c, acc)


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


def run_iteration(label, tickets, ontology_file):
    onto, ver = load_ontology(ontology_file)
    print(f"\n{'='*78}")
    print(f"ITERATION: {label} (ontology {ver})")
    print(f"{'='*78}")

    results = []
    total_tokens = 0
    for i, ticket in enumerate(tickets):
        r = classify_item(ticket, onto)
        r["ticket"] = ticket
        results.append(r)
        total_tokens += r["tokens"]

    # Summary stats
    confs = [r["overall_confidence"] for r in results]
    high = [r for r in results if r["overall_confidence"] >= 0.9]
    flagged = [r for r in results if r["overall_confidence"] < 0.5]
    low_margin = []
    for r in results:
        for step in r["path"]:
            ranked = sorted(step["distribution"].items(), key=lambda x: x[1], reverse=True)
            if len(ranked) >= 2 and (ranked[0][1] - ranked[1][1]) < 0.15:
                low_margin.append({
                    "ticket": r["ticket"],
                    "node": step["node"],
                    "top": ranked[0][0],
                    "top_p": ranked[0][1],
                    "second": ranked[1][0],
                    "second_p": ranked[1][1],
                })

    # Leaf distribution
    all_leaves = set()
    collect_leaves(onto, all_leaves)
    leaf_counts = Counter(r["leaf"] for r in results)
    zero_traffic = sorted(all_leaves - set(leaf_counts.keys()))

    print(f"\nTickets: {len(tickets)}")
    print(f"Jev calls: {len(tickets) * 2} (2 levels each)")
    print(f"Input tokens: {total_tokens}")
    print(f"Cost: ${total_tokens * 0.042 / 1_000_000:.4f}")
    print(f"Mean confidence: {sum(confs)/len(confs):.3f}")
    print(f"High-confidence (>=0.9): {len(high)}")
    print(f"Flagged (<0.5): {len(flagged)}")
    print(f"Low-margin decisions: {len(low_margin)}")
    print(f"Zero-traffic leaves: {zero_traffic}")

    print(f"\nLeaf distribution:")
    for leaf_id in sorted(all_leaves):
        count = leaf_counts.get(leaf_id, 0)
        marker = "  <- ZERO" if count == 0 else ""
        print(f"  {leaf_id}: {count}{marker}")

    if flagged:
        print(f"\nFlagged tickets (confidence < 0.5):")
        for r in flagged:
            dist = r["path"][0]["distribution"] if r["path"] else {}
            top2 = sorted(dist.items(), key=lambda x: x[1], reverse=True)[:2]
            dist_str = " vs ".join(f"{k}:{v:.2f}" for k, v in top2)
            print(f"  [{r['leaf']} conf={r['overall_confidence']:.3f}] {dist_str}")
            print(f"    '{r['ticket'][:70]}'")

    if low_margin:
        print(f"\nLow-margin decisions (top-2 within 0.15):")
        for lm in low_margin[:15]:
            print(f"  {lm['top']}({lm['top_p']:.2f}) vs {lm['second']}({lm['second_p']:.2f}) at {lm['node']}")
            print(f"    '{lm['ticket'][:65]}'")
        if len(low_margin) > 15:
            print(f"  ... and {len(low_margin)-15} more")

    return {
        "version": ver,
        "results": results,
        "total_tokens": total_tokens,
        "mean_confidence": sum(confs)/len(confs),
        "high_count": len(high),
        "flagged_count": len(flagged),
        "flagged": [{"ticket": r["ticket"], "leaf": r["leaf"], "conf": r["overall_confidence"]} for r in flagged],
        "low_margin": low_margin,
        "zero_traffic": zero_traffic,
        "leaf_counts": dict(leaf_counts),
    }


# --------------------------------------------------------------------------- #
# 52 tickets: messier and more realistic than previous sessions
# --------------------------------------------------------------------------- #

TICKETS = [
    # --- Billing: Payment failures ---
    "My card keeps getting declined even though I know there's money on it.",
    "payment failed??? i updated my card info 3 times already and it still says declined",
    "The system won't accept my new credit card, it keeps erroring out on the payment page.",
    # --- Billing: Wrongful charges ---
    "You guys charged me TWICE for the same month. I want this fixed NOW.",
    "I cancelled my subscription in august but you still charged me in september. this is theft.",
    "I see a charge for $49 on my card but I don't even have an active subscription anymore.",
    "Why was I charged for the pro plan when I downgraded to basic last week?",
    # --- Billing: Refund requests ---
    "Can I get my money back? The product didn't work for me so I cancelled.",
    "I'd like to request a refund for the unused portion of my annual plan, I only used 2 months.",
    "refunding my last payment would be great since the feature I needed isn't available",
    # --- Billing: Subscription changes ---
    "I want to upgrade from basic to pro, how do I do that?",
    "Can I pause my subscription for 2 months while I'm on sabbatical?",
    "I need to switch from monthly to annual billing.",
    "Please cancel my subscription effective immediately.",
    # --- Billing: Invoice questions ---
    "My invoice shows a different amount than what we agreed on, can someone explain?",
    "What is this 'platform fee' line item on my bill? It was never there before.",
    "The tax calculation on my latest invoice looks wrong, I'm in Oregon so there should be no sales tax.",
    "Can you send me a copy of all my invoices from last year for tax purposes?",
    # --- Technical: Bug reports ---
    "The dashboard is completely blank when I log in, nothing loads at all.",
    "Every time I try to export a report I get a 500 error.",
    "The search function returns results that have nothing to do with what I typed.",
    "Mobile app crashes on startup after the latest update, I'm on iOS 17.",
    "when i click save it just spins forever and nothing gets saved",
    # --- Technical: Feature requests ---
    "It would be amazing if you could add bulk import for CSV files.",
    "I really need a way to schedule reports to run automatically every Monday.",
    "Can you add SSO support for Azure AD? We can't use the product without it at our company.",
    "Would be great to have a dark theme, the white background hurts my eyes.",
    # --- Technical: Integration problems ---
    "Our Salesforce integration keeps dropping the connection every few hours.",
    "The Slack notifications stopped working after we changed our workspace settings.",
    "Webhooks are returning 200 but the data isn't reaching our endpoint.",
    "Zapier integration says 'account not connected' even though I reconnected it twice.",
    # --- Technical: Performance issues ---
    "The reports page takes 45+ seconds to load, it used to be instant.",
    "Everything is really slow today, is there an outage? It's affecting our whole team.",
    "The app becomes unresponsive when I try to filter a large dataset (>10000 rows).",
    # --- Account: Login problems ---
    "I can't log in, it says my account is locked. I didn't do anything wrong.",
    "2FA isn't working, I'm not getting the SMS code and I'm locked out.",
    "every time i try to log in it redirects me back to the login page in a loop",
    "My SSO through Okta stopped working this morning, it was fine yesterday.",
    # --- Account: Access requests ---
    "I need admin access to the workspace, the previous admin left the company.",
    "Can you add 3 more seats to our plan? We have new team members starting Monday.",
    "I need to give my assistant read-only access to the reports section.",
    # --- Account: Security concerns ---
    "I think my account was hacked, there are logins from IPs I don't recognize.",
    "We got a phishing email that looks like it's from your company, where do I report it?",
    "I need to know if you store EU customer data in the US for GDPR compliance.",
    # --- Account: Account management ---
    "I need to change my email address from old@company.com to new@company.com.",
    "How do I delete my account and all associated data?",
    "Can you update the company name on our account from 'OldCo' to 'NewCo' after our rebrand?",
    # --- Cross-domain / compound / tricky ---
    "Your API is so slow it's timing out and now we're being charged for failed requests on top of it. Fix this.",
    "I cancelled my plan but I can still access the product, and I also got charged. What is going on?",
    "The Stripe integration broke after your latest update and now payments aren't processing and customers are complaining.",
    "Something is broken, help.",  # Extremely vague
    "I was charged for something I didn't buy and now I can't log in to dispute it because of a 2FA issue.",  # Triple compound
]


def main():
    print(f"Jev model: jev-latest")
    print(f"Tickets: {len(TICKETS)}")

    # Run 3 iterations against pre-authored ontology versions
    iter1 = run_iteration("Iteration 1", TICKETS, "ontology_v3.json")
    iter2 = run_iteration("Iteration 2", TICKETS, "ontology_v4.json")
    iter3 = run_iteration("Iteration 3", TICKETS, "ontology_v5.json")

    # Convergence analysis
    print(f"\n{'='*78}")
    print("CONVERGENCE ANALYSIS")
    print(f"{'='*78}")

    print(f"\n{'Metric':<30} {'Iter 1 (v3.0)':<18} {'Iter 2 (v4.0)':<18} {'Iter 3 (v5.0)':<18}")
    print("-" * 84)
    print(f"{'Mean confidence':<30} {iter1['mean_confidence']:<18.3f} {iter2['mean_confidence']:<18.3f} {iter3['mean_confidence']:<18.3f}")
    print(f"{'High-confidence (>=0.9)':<30} {iter1['high_count']:<18} {iter2['high_count']:<18} {iter3['high_count']:<18}")
    print(f"{'Flagged (<0.5)':<30} {iter1['flagged_count']:<18} {iter2['flagged_count']:<18} {iter3['flagged_count']:<18}")
    print(f"{'Low-margin decisions':<30} {len(iter1['low_margin']):<18} {len(iter2['low_margin']):<18} {len(iter3['low_margin']):<18}")
    print(f"{'Zero-traffic leaves':<30} {len(iter1['zero_traffic']):<18} {len(iter2['zero_traffic']):<18} {len(iter3['zero_traffic']):<18}")
    print(f"{'Total tokens':<30} {iter1['total_tokens']:<18} {iter2['total_tokens']:<18} {iter3['total_tokens']:<18}")
    total_cost = (iter1['total_tokens'] + iter2['total_tokens'] + iter3['total_tokens']) * 0.042 / 1_000_000
    print(f"{'Cost':<30} ${iter1['total_tokens']*0.042/1e6:<18.4f} ${iter2['total_tokens']*0.042/1e6:<18.4f} ${iter3['total_tokens']*0.042/1e6:<18.4f}")
    print(f"{'TOTAL COST':<30} {'':<18} {'':<18} ${total_cost:<18.4f}")

    # Per-ticket leaf stability
    print(f"\nPer-ticket leaf changes:")
    leaf_changes_1to2 = 0
    leaf_changes_2to3 = 0
    leaf_changes_1to3 = 0
    conf_changes = []
    for i in range(len(TICKETS)):
        t = TICKETS[i]
        l1 = iter1["results"][i]["leaf"]
        l2 = iter2["results"][i]["leaf"]
        l3 = iter3["results"][i]["leaf"]
        c1 = iter1["results"][i]["overall_confidence"]
        c2 = iter2["results"][i]["overall_confidence"]
        c3 = iter3["results"][i]["overall_confidence"]

        if l1 != l2:
            leaf_changes_1to2 += 1
        if l2 != l3:
            leaf_changes_2to3 += 1
        if l1 != l3:
            leaf_changes_1to3 += 1

        if l1 != l2 or l2 != l3:
            print(f"  '{t[:60]}'")
            print(f"    v3.0: {l1} ({c1:.3f}) -> v4.0: {l2} ({c2:.3f}) -> v5.0: {l3} ({c3:.3f})")

    print(f"\nLeaf changes 1->2: {leaf_changes_1to2}")
    print(f"Leaf changes 2->3: {leaf_changes_2to3}")
    print(f"Leaf changes 1->3: {leaf_changes_1to3}")

    # Confidence trajectory for all tickets
    print(f"\nConfidence trajectory (all {len(TICKETS)} tickets):")
    improved_1to2 = 0
    improved_2to3 = 0
    worsened_1to2 = 0
    worsened_2to3 = 0
    for i in range(len(TICKETS)):
        c1 = iter1["results"][i]["overall_confidence"]
        c2 = iter2["results"][i]["overall_confidence"]
        c3 = iter3["results"][i]["overall_confidence"]
        if c2 > c1 + 0.01:
            improved_1to2 += 1
        elif c2 < c1 - 0.01:
            worsened_1to2 += 1
        if c3 > c2 + 0.01:
            improved_2to3 += 1
        elif c3 < c2 - 0.01:
            worsened_2to3 += 1

    print(f"  Iter 1->2: {improved_1to2} improved, {worsened_1to2} worsened, {len(TICKETS)-improved_1to2-worsened_1to2} flat")
    print(f"  Iter 2->3: {improved_2to3} improved, {worsened_2to3} worsened, {len(TICKETS)-improved_2to3-worsened_2to3} flat")

    # Save results to JSON for the writeup
    output = {
        "tickets": TICKETS,
        "iterations": [
            {
                "version": iter1["version"],
                "mean_confidence": iter1["mean_confidence"],
                "high_count": iter1["high_count"],
                "flagged_count": iter1["flagged_count"],
                "flagged": iter1["flagged"],
                "low_margin_count": len(iter1["low_margin"]),
                "zero_traffic": iter1["zero_traffic"],
                "leaf_counts": iter1["leaf_counts"],
                "total_tokens": iter1["total_tokens"],
                "results": [{"ticket": r["ticket"], "leaf": r["leaf"], "conf": r["overall_confidence"],
                             "path": [{"node": s["node"], "confidence": s["confidence"],
                                       "distribution": s["distribution"]} for s in r["path"]]}
                            for r in iter1["results"]],
            },
            {
                "version": iter2["version"],
                "mean_confidence": iter2["mean_confidence"],
                "high_count": iter2["high_count"],
                "flagged_count": iter2["flagged_count"],
                "flagged": iter2["flagged"],
                "low_margin_count": len(iter2["low_margin"]),
                "zero_traffic": iter2["zero_traffic"],
                "leaf_counts": iter2["leaf_counts"],
                "total_tokens": iter2["total_tokens"],
                "results": [{"ticket": r["ticket"], "leaf": r["leaf"], "conf": r["overall_confidence"],
                             "path": [{"node": s["node"], "confidence": s["confidence"],
                                       "distribution": s["distribution"]} for s in r["path"]]}
                            for r in iter2["results"]],
            },
            {
                "version": iter3["version"],
                "mean_confidence": iter3["mean_confidence"],
                "high_count": iter3["high_count"],
                "flagged_count": iter3["flagged_count"],
                "flagged": iter3["flagged"],
                "low_margin_count": len(iter3["low_margin"]),
                "zero_traffic": iter3["zero_traffic"],
                "leaf_counts": iter3["leaf_counts"],
                "total_tokens": iter3["total_tokens"],
                "results": [{"ticket": r["ticket"], "leaf": r["leaf"], "conf": r["overall_confidence"],
                             "path": [{"node": s["node"], "confidence": s["confidence"],
                                       "distribution": s["distribution"]} for s in r["path"]]}
                            for r in iter3["results"]],
            },
        ],
        "leaf_changes_1to2": leaf_changes_1to2,
        "leaf_changes_2to3": leaf_changes_2to3,
        "leaf_changes_1to3": leaf_changes_1to3,
        "total_cost": total_cost,
    }
    with open(os.path.join(SCRIPT_DIR, "convergence_results.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to convergence_results.json")


if __name__ == "__main__":
    main()
