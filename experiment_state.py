"""Ticket experiment checkpoints using the Images atomic, revision-checked store."""
from datetime import datetime, timezone
import math
import json
import os
from pathlib import Path

from Images.json_store import fingerprint, load_json, save_json
from Images.run_state import prepare_run
import mvp_jev_ontology

ROOT = Path(__file__).resolve().parent


def output_path(default):
    path = Path(os.environ.get("RESULTS_OUT") or default)
    if not path.is_absolute():
        path = ROOT / path
    if not path.name.endswith(".results.json"):
        raise ValueError("Use a new *.results.json output; historical result files are read-only")
    return path.resolve()


def validate_result(result, ontology):
    current = ontology
    confidence = 1.0
    for step in result["path"]:
        children = {child["id"]: child for child in current.get("children", [])}
        mvp_jev_ontology.validate_choice({
            "choice": step["node"], "confidence": step["confidence"],
            "probabilities": step["distribution"],
        }, children)
        current = children[step["node"]]
        confidence *= step["confidence"]
    reported = result["overall_confidence"]
    if (current.get("children") or result["leaf"] != current["id"]
            or isinstance(reported, bool) or not isinstance(reported, (int, float))
            or not math.isfinite(reported) or not math.isclose(reported, confidence, abs_tol=1e-12)):
        raise ValueError("Invalid completed classification path or cumulative confidence")
    tokens = result["tokens"]
    if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
        raise ValueError("Invalid input-token count")
    if any(step.get("model") is not None
           and (not isinstance(step["model"], str) or not step["model"])
           for step in result["path"]):
        raise ValueError("Invalid response model identifier")


def run_experiment(default, batches, classify, api_key, *implementation, config=None):
    """Save after every completed ticket; refuse changed or unproven resumes."""
    path = output_path(default)
    document = load_json(path, missing_ok=True)
    identity = {"schema": 1, "requested_model": "jev-latest",
                "batches": batches, "experiment": config or {}}
    if document:
        if (set(document) - {"_meta", "records", "summary"}
                or not isinstance(document.get("records"), dict)
                or document.get("_meta", {}).get("identity") != identity):
            raise ValueError("Experiment identity changed or is absent; choose a fresh RESULTS_OUT")
    else:
        document.update(_meta={"identity": identity,
                               "created_at": datetime.now(timezone.utc).isoformat()}, records={})
    inputs = {}
    for name, batch in batches.items():
        if not batch["tickets"]:
            raise ValueError(f"Empty experiment batch: {name}")
        for index, ticket in enumerate(batch["tickets"]):
            if not isinstance(ticket, str) or not ticket.strip():
                raise ValueError("Tickets must be nonempty strings")
            inputs[f"{name}:{index}"] = {"ticket": ticket}
    records = document["records"]
    if any(not isinstance(record, dict) for record in records.values()):
        raise ValueError("Invalid experiment record")
    stamps = prepare_run(records, identity, inputs, __file__,
                         mvp_jev_ontology.__file__, *implementation)
    observed_models = set()
    for name, batch in batches.items():
        for index, ticket in enumerate(batch["tickets"]):
            record = records.get(f"{name}:{index}", {})
            if record.get("status") == "ok":
                validate_result(record, batch["ontology"])
                if record.get("ticket") != ticket:
                    raise ValueError("Stored ticket differs from the experiment input")
                observed_models.update(step["model"] for step in record["path"] if step.get("model"))
    if len(observed_models) > 1:
        raise ValueError("Stored run mixes response model versions; select a fresh RESULTS_OUT")
    pending = [key for key in inputs if records.get(key, {}).get("status") != "ok"]
    if pending and not api_key:
        raise SystemExit("Missing TYPESAFE_API_KEY; no API calls or writes made")
    grouped = {}
    for name, batch in batches.items():
        grouped[name] = []
        for index, ticket in enumerate(batch["tickets"]):
            key = f"{name}:{index}"
            if records.get(key, {}).get("status") != "ok":
                result = None
                try:
                    result = classify(ticket, batch["ontology"])
                    validate_result(result, batch["ontology"])
                    models = {step["model"] for step in result["path"] if step.get("model")}
                    if len(models | observed_models) > 1:
                        raise ValueError("Response model changed during the run; select a fresh RESULTS_OUT")
                    observed_models.update(models)
                except Exception as exc:
                    records[key] = {"status": "error", "ticket": ticket, "error": str(exc),
                                    "_provenance": stamps[key], "partial_result": result}
                    try:
                        json.dumps(result, allow_nan=False)
                    except (TypeError, ValueError):
                        records[key]["partial_result"] = None
                        records[key]["invalid_result_repr"] = repr(result)
                    document.pop("summary", None)
                    save_json(path, document)
                    raise
                records[key] = {**result, "ticket": ticket, "status": "ok",
                                "ontology_version": batch["version"],
                                "ontology_sha256": fingerprint(batch["ontology"]),
                                "_provenance": stamps[key]}
                document.pop("summary", None)
                save_json(path, document)
            grouped[name].append(records[key])
    return grouped, document


def save_summary(document, summary):
    document["summary"] = summary
    save_json(document.path, document)
