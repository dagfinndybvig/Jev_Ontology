"""Fail-closed identity checks for resumable, incrementally saved runs."""
import hashlib
import ast
from pathlib import Path

if __package__:
    from .json_store import fingerprint
else:
    from json_store import fingerprint


def file_digest(path):
    with open(path, "rb") as handle:
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_digest(path):
    return fingerprint(ast.dump(ast.parse(Path(path).read_text(encoding="utf-8"))))


def prepare_run(results, config, inputs, *implementation):
    """Validate all existing records before any API call or write."""
    config_id = fingerprint({
        "config": config,
        "implementation": {Path(p).name: source_digest(p) for p in implementation},
    })
    stamps = {name: {"schema": 1, "config_sha256": config_id,
                     "input_sha256": fingerprint(value)}
              for name, value in inputs.items()}
    if not inputs:
        raise ValueError("No inputs selected for this run")
    if set(results) - set(inputs):
        raise ValueError("Results contain inputs outside this corpus; select a fresh RESULTS_OUT")
    for name, rec in results.items():
        if rec.get("_provenance") != stamps[name]:
            raise ValueError(
                "Resume identity is missing or changed (configuration/input). "
                "Preserve the existing results and select a fresh RESULTS_OUT; "
                "legacy runs are read-only, never automatically relabeled.")
    return stamps


def require_complete(results):
    errors = sum(rec.get("status") != "ok" for rec in results.values())
    if errors:
        raise SystemExit(f"{errors} records incomplete; saved progress can be resumed")
