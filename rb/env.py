from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path, *, override: bool = False) -> dict[str, str]:
    """Load KEY=VALUE lines from a .env-style file into os.environ.

    This intentionally keeps parsing simple and avoids adding a dependency.
    """
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if not override and key in os.environ:
            continue
        os.environ[key] = value
        loaded[key] = value

    return loaded

