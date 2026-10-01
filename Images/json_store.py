"""Atomic JSON storage with optimistic concurrency for read/modify/write files."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


class WriteConflict(RuntimeError):
    """The file changed since it was read; reload before applying the edit."""


class JsonDocument(dict):
    def __init__(self, data, path, revision):
        super().__init__(data)
        self.path = Path(path).resolve()
        self.revision = revision


def fingerprint(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def _revision(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def load_json(path, *, missing_ok=False):
    path = Path(path).resolve()
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        if not missing_ok:
            raise
        return JsonDocument({}, path, None)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path.name}")
    return JsonDocument(data, path, hashlib.sha256(raw).hexdigest())


@contextmanager
def file_lock(path, timeout=10):
    """Lock a stable sidecar; OS releases the lock if the process exits."""
    lock_path = Path(str(Path(path).resolve()) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise WriteConflict(f"File is busy: {Path(path).name}") from exc
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def save_json(path, data, *, indent=2):
    """Replace atomically; documents loaded here also reject stale writes."""
    path = Path(path).resolve()
    raw = json.dumps(data, indent=indent, ensure_ascii=False,
                     allow_nan=False).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path):
        if isinstance(data, JsonDocument):
            if data.path != path or data.revision != _revision(path):
                raise WriteConflict(f"{path.name} changed on disk; reload before saving")
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp",
                                   dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        if isinstance(data, JsonDocument):
            data.revision = hashlib.sha256(raw).hexdigest()
