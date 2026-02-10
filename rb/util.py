from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def utc_now_compact() -> str:
    # Example: 20260210T123456Z
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_text_atomic(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    tmp.replace(path)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def write_json_atomic(path: Path, obj: object) -> None:
    text = json.dumps(obj, sort_keys=True, indent=2)
    write_text_atomic(path, text + "\n")


def redact_url(url: str) -> str:
    """Redact common secret parameters from a URL (e.g., api_key)."""
    parts = urlsplit(url)
    if not parts.query:
        return url

    q = []
    for k, v in parse_qsl(parts.query, keep_blank_values=True):
        if k.lower() in {"api_key", "apikey", "key", "token"}:
            q.append((k, "REDACTED"))
        else:
            q.append((k, v))

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))

