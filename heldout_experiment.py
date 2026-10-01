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
    python heldout_experiment.py <ontology_file> [--stage train|holdout|both]
    RESULTS_OUT selects a fresh *.results.json file; --save labels the run.

The split is deterministic (seed 42) and persisted to heldout_split.json so
the same tickets stay in train/holdout across runs.

Requires TYPESAFE_API_KEY.
"""

import json
import argparse
import os
import random
import sys
import urllib.request
from collections import Counter
from mvp_jev_ontology import validate_choice
from experiment_state import run_experiment, save_summary
from Images.json_store import fingerprint, load_json, save_json

API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SPLIT_PATH = os.environ.get("SPLIT_PATH") or os.path.join(SCRIPT_DIR, "heldout_split.json")
LEGACY_CORPUS = "848bb7c6bf3f145004b686d1da79378876e5a836f606c0ab558f2fd1ccd1d346"
LEGACY_SPLIT = "09af96d6b2dfcefd57bfd8b356e7533e4126c4a2ecd0f678074265edf2a0bd5d"

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
    validate_choice(answer, criteria)
    return {
        "choice": answer["choice"],
        "confidence": answer["confidence"],
        "distribution": answer["probabilities"],
        "usage": data.get("usage", {}),
        "model": data.get("model"),
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
            "model": result["model"],
        })
        current = child_node
    leaf = path[-1]["node"] if path else ontology["id"]
    return {"path": path, "leaf": leaf, "overall_confidence": confidence, "tokens": total_tokens}


# --------------------------------------------------------------------------- #
# Split
# --------------------------------------------------------------------------- #

def get_split():
    if (any(not isinstance(ticket, str) or not ticket.strip() for ticket in TICKETS)
            or len(set(TICKETS)) != len(TICKETS)):
        raise ValueError("Held-out corpus requires distinct, nonempty ticket texts")
    split = load_json(SPLIT_PATH, missing_ok=True)
    corpus = fingerprint(TICKETS)
    is_new = split.revision is None
    if is_new:
        rng = random.Random(42)
        idx = list(range(len(TICKETS)))
        rng.shuffle(idx)
        n_train = int(len(TICKETS) * 0.70)
        split.update(train=idx[:n_train], holdout=idx[n_train:],
                     _meta={"schema": 1, "seed": 42, "corpus_sha256": corpus})
    train, holdout = split.get("train"), split.get("holdout")
    if (not isinstance(train, list) or not isinstance(holdout, list)
            or not train or not holdout
            or any(type(i) is not int for i in train + holdout)
            or len(set(train + holdout)) != len(train + holdout)
            or set(train + holdout) != set(range(len(TICKETS)))):
        raise ValueError("Split must be two nonempty, disjoint partitions covering the corpus exactly")
    meta = split.get("_meta")
    if meta is None:
        if corpus != LEGACY_CORPUS or fingerprint(split) != LEGACY_SPLIT:
            raise ValueError("Unbound legacy split; use a fresh SPLIT_PATH")
    elif not isinstance(meta, dict) or meta.get("schema") != 1 or meta.get("corpus_sha256") != corpus:
        raise ValueError("Split corpus changed; use a fresh SPLIT_PATH")
    if is_new:
        save_json(SPLIT_PATH, split)
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
    if not results:
        raise ValueError("Cannot summarize an empty cohort")
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ontology_file")
    parser.add_argument("--stage", choices=("train", "holdout", "both"), default="train",
                        help="Default train never evaluates or displays holdout results")
    parser.add_argument("--save", help="Run label (RESULTS_OUT selects the file)")
    args = parser.parse_args()
    split = get_split()
    ontology, ver = load_ontology(args.ontology_file)
    cohorts = ("train", "holdout") if args.stage == "both" else (args.stage,)
    batches = {name: {"tickets": [TICKETS[i] for i in split[name]],
                      "ontology": ontology, "version": ver} for name in cohorts}
    groups, document = run_experiment(
        f"heldout.{args.stage}.results.json", batches, classify_item, API_KEY, __file__,
        config={"split": dict(split), "label": args.save or ver, "stage": args.stage})
    summary = {"version": ver}
    print(f"Ontology: {args.ontology_file} (version {ver})")
    for name, results in groups.items():
        stats = summarize(results)
        summary[name] = stats
        summary[f"{name}_tokens"] = sum(r["tokens"] for r in results)
        print(f"{name.upper()} ({stats['n']}): mean={stats['mean']:.3f} "
              f"high(>=0.9)={stats['high_ge_0.9']} flagged(<0.5)={stats['flagged_lt_0.5']} "
              f"min={stats['min']:.3f}")
    if "train" in groups:
        summary["signals"] = collect_signals(groups["train"], ontology)
        print("\nTRAIN FEEDBACK SIGNALS (train records only)")
        print(json.dumps(summary["signals"], indent=2, ensure_ascii=False))
    print("Jev calls represented:", sum(len(r["path"]) for rows in groups.values() for r in rows))
    save_summary(document, summary)
    print(f"\nSaved to {document.path}")


if __name__ == "__main__":
    main()
