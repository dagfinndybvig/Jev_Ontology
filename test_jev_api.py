"""Opt-in live API smoke check; importing this module never makes a request."""
import json
import os
import urllib.request

ENDPOINT = "https://api.typesafe.ai/v1/systemone"


def main():
    api_key = os.environ.get("TYPESAFE_API_KEY", "")
    if not api_key:
        raise SystemExit("Missing TYPESAFE_API_KEY")
    criteria = {
        "billing": "Payments, invoicing, refunds",
        "technical": "Bugs, outages, integrations",
        "sales": "Pricing, upgrades, new accounts",
    }
    body = {
        "model": "jev-latest",
        "state": "Help! My payouts have been failing for 3 days.",
        "questions": {"department": {
            "type": "choice", "instructions": "Which team should handle this?",
            "criteria": criteria,
        }},
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    answer = data["answers"]["department"]
    from mvp_jev_ontology import validate_choice
    validate_choice(answer, criteria)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
