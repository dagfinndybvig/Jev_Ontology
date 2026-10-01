"""Guard the replication corpus's published sealing boundary."""
from json_store import fingerprint


class SealedManifestError(ValueError):
    pass


def require_unsealed(manifest):
    if "_sealing" in manifest:
        raise SealedManifestError("Manifest is sealed; use a separate new corpus manifest")


def require_sealed(manifest):
    if not isinstance(manifest.get("_sealing"), dict):
        raise SealedManifestError("Replication requires a sealed manifest")
    records = {k: v for k, v in manifest.items()
               if isinstance(v, dict) and "category" in v}
    if not records or any(v.get("verified") is not True and v.get("verified") is not False
                          for v in records.values() if v.get("status") == "ok"):
        raise SealedManifestError("Sealed manifest contains unverified images")
    return fingerprint(manifest)
