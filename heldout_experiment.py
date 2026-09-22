"""
Held-out generalization test for the LLM-Jev feedback loop.

The convergence experiment (convergence_experiment.py) runs the loop on the
same 52 tickets it measures improvement on. That is in-sample: the revision
signals and the evaluation come from the same tickets, so "improvement" can
just be the ontology memorizing the eval set.

This script fixes that. It splits the 52 tickets into a TRAIN set (used to
generate revision signals) and a HELD-OUT set (never used to trigger a
revision). The LLM revision step is authored from train signals only. We then
measure whether mean confidence on the HELD-OUT set improves -- the real test
of generalization.

Usage:
    python heldout_experiment.py <ontology_file> [--save <key>]

The split is deterministic (seed 42) and persisted to heldout_split.json so
the same tickets stay in train/holdout across runs.

Requires TYPESAFE_API_KEY.
"""

import json
import os
import random
import sys
import urllib.request
from collections import Counter

API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SPLIT_PATH = os.path.join(SCRIPT_DIR, "heldout_split.json")

# --------------------------------------------------------------------------- #
# Tickets (same 52 as convergence_experiment.py)
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


# --------------------------------------------------------------------------- #
# Ontology + Jev helpers (mirrors convergence_experiment.py)
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Split
# --------------------------------------------------------------------------- #

def get_split():
    if os.path.exists(SPLIT_PATH):
        with open(SPLIT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    rng = random.Random(42)
    idx = list(range(len(TICKETS)))
    rng.shuffle(idx)
    n_train = int(len(TICKETS) * 0.70)
    split = {"train": idx[:n_train], "holdout": idx[n_train:]}
    with open(SPLIT_PATH, "w", encoding="utf-8") as f:
        json.dump(split, f, indent=2)
    return split


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #

def classify_set(tickets, ontology):
    results = []
    total_tokens = 0
    for t in tickets:
        r = classify_item(t, ontology)
        r["ticket"] = t
        results.append(r)
        total_tokens += r["tokens"]
    return results, total_tokens


def summarize(results):
    confs = [r["overall_confidence"] for r in results]
    return {
        "n": len(results),
        "mean": sum(confs) / len(confs),
        "high_ge_0.9": sum(1 for c in confs if c >= 0.9),
        "flagged_lt_0.5": sum(1 for c in confs if c < 0.5),
        "min": min(confs),
    }


def collect_signals(results, ontology):
    """Return the feedback signals the LLM would use to revise the ontology."""
    all_leaves = set()
    collect_leaves(ontology, all_leaves)
    leaf_counts = Counter(r["leaf"] for r in results)
    zero_traffic = sorted(all_leaves - set(leaf_counts.keys()))

    low_conf = [r for r in results if r["overall_confidence"] < 0.5]
    low_margin = []
    for r in results:
        for step in r["path"]:
            ranked = sorted(step["distribution"].items(), key=lambda x: x[1], reverse=True)
            if len(ranked) >= 2 and (ranked[0][1] - ranked[1][1]) < 0.15:
                low_margin.append({
                    "ticket": r["ticket"],
                    "node": step["node"],
                    "top": ranked[0][0],
                    "top_p": round(ranked[0][1], 3),
                    "second": ranked[1][0],
                    "second_p": round(ranked[1][1], 3),
                })
    return {
        "zero_traffic": zero_traffic,
        "leaf_counts": dict(leaf_counts),
        "low_conf": [{"ticket": r["ticket"], "leaf": r["leaf"], "conf": round(r["overall_confidence"], 3)}
                     for r in low_conf],
        "low_margin": low_margin,
    }


def main():
    if len(sys.argv) < 2:
        print("usage: python heldout_experiment.py <ontology_file> [--save <key>]")
        sys.exit(1)
    onto_file = sys.argv[1]
    save_key = None
    if "--save" in sys.argv:
        save_key = sys.argv[sys.argv.index("--save") + 1]

    split = get_split()
    train = [TICKETS[i] for i in split["train"]]
    holdout = [TICKETS[i] for i in split["holdout"]]

    ontology, ver = load_ontology(onto_file)

    print(f"Ontology: {onto_file} (version {ver})")
    print(f"Train: {len(train)} tickets | Holdout: {len(holdout)} tickets")
    print("=" * 78)

    train_res, train_tokens = classify_set(train, ontology)
    hold_res, hold_tokens = classify_set(holdout, ontology)

    ts = summarize(train_res)
    hs = summarize(hold_res)
    print(f"\nTRAIN   ({ts['n']}): mean={ts['mean']:.3f}  high(>=0.9)={ts['high_ge_0.9']}  "
          f"flagged(<0.5)={ts['flagged_lt_0.5']}  min={ts['min']:.3f}")
    print(f"HOLDOUT ({hs['n']}): mean={hs['mean']:.3f}  high(>=0.9)={hs['high_ge_0.9']}  "
          f"flagged(<0.5)={hs['flagged_lt_0.5']}  min={hs['min']:.3f}")
    print(f"Tokens: train={train_tokens} holdout={hold_tokens} "
          f"cost=${(train_tokens + hold_tokens) * 0.042 / 1_000_000:.4f}")

    # Signals from TRAIN only (this is what the LLM revision step sees)
    sig = collect_signals(train_res, ontology)
    print("\n" + "=" * 78)
    print("TRAIN FEEDBACK SIGNALS (what the LLM revision step sees)")
    print("=" * 78)
    print(f"\nZero-traffic leaves: {sig['zero_traffic']}")
    print(f"\nLeaf distribution (train):")
    for leaf_id in sorted(sig["leaf_counts"]):
        print(f"  {leaf_id}: {sig['leaf_counts'][leaf_id]}")
    print(f"\nLow-confidence (<0.5) train tickets:")
    for lc in sig["low_conf"]:
        print(f"  [{lc['leaf']} conf={lc['conf']:.3f}] {lc['ticket'][:70]}")
    print(f"\nLow-margin (top-2 within 0.15) train decisions:")
    for lm in sig["low_margin"]:
        print(f"  {lm['top']}({lm['top_p']:.2f}) vs {lm['second']}({lm['second_p']:.2f}) at {lm['node']}")
        print(f"    {lm['ticket'][:65]}")

    # Save for comparison
    out_path = os.path.join(SCRIPT_DIR, "heldout_results.json")
    results_store = {}
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            results_store = json.load(f)
    results_store[save_key or ver] = {
        "ontology_file": onto_file,
        "version": ver,
        "train": ts,
        "holdout": hs,
        "train_tokens": train_tokens,
        "holdout_tokens": hold_tokens,
        "signals": sig,
        "holdout_detail": [{"ticket": r["ticket"], "leaf": r["leaf"], "conf": round(r["overall_confidence"], 3)}
                           for r in hold_res],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results_store, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
