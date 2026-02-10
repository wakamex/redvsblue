from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rb.util import sha256_hex, utc_now_compact, write_bytes_atomic, write_json_atomic


@dataclass(frozen=True)
class CachedArtifact:
    path: Path
    meta_path: Path
    sha256: str


class ArtifactCache:
    def __init__(self, raw_root: Path = Path("data/raw")) -> None:
        self.raw_root = raw_root

    def artifact_dir(self, *parts: str) -> Path:
        d = self.raw_root.joinpath(*parts)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def latest(self, artifact_dir: Path, *, suffix: str) -> CachedArtifact | None:
        candidates = sorted(
            p
            for p in artifact_dir.glob(f"*.{suffix}")
            # Meta files intentionally end with ".meta.json" which would match
            # suffix="json" globs; exclude them.
            if ".meta.json" not in p.name
        )
        if not candidates:
            return None
        # Filenames are prefixed with an ISO-ish timestamp, so lexicographic sort works.
        path = candidates[-1]
        meta = path.with_suffix(path.suffix + ".meta.json")
        sha = path.name.split("__sha256_")[-1].split(".")[0] if "__sha256_" in path.name else ""
        return CachedArtifact(path=path, meta_path=meta, sha256=sha)

    def write(
        self,
        artifact_dir: Path,
        *,
        data: bytes,
        suffix: str,
        meta: dict,
    ) -> CachedArtifact:
        sha = sha256_hex(data)
        ts = utc_now_compact()
        path = artifact_dir / f"{ts}__sha256_{sha}.{suffix}"
        meta_path = artifact_dir / f"{ts}__sha256_{sha}.{suffix}.meta.json"
        write_bytes_atomic(path, data)
        write_json_atomic(meta_path, meta)
        return CachedArtifact(path=path, meta_path=meta_path, sha256=sha)
