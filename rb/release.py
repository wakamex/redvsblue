"""Build a website from fresh inputs and identify the deployed release."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from rb.env import load_dotenv
from rb.util import redact_url, write_json_atomic

REPOSITORY = "https://github.com/wakamex/redvsblue"


def git(*args: str, root: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(root: Path, tag: str | None = None) -> dict:
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    commit = git("rev-parse", "HEAD", root=root)
    if tag is not None:
        if tag != "v" + version or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
            raise ValueError("Release tag must match the project version")
        if git("cat-file", "-t", "refs/tags/" + tag, root=root) != "tag":
            raise ValueError("Release tag must be annotated")
        if git("rev-parse", "refs/tags/" + tag + "^{commit}", root=root) != commit:
            raise ValueError("Checkout differs from the release tag")
        notes = root / "release-notes" / (tag + ".md")
        if notes.is_symlink() or not notes.is_file() or not notes.read_text().strip():
            raise ValueError("Release notes must be committed and nonempty")
    if git("status", "--porcelain", "--untracked-files=no", root=root):
        raise ValueError("Build requires an unchanged tracked tree")
    return {"version": version, "tag": tag, "commit": commit,
            "release_url": f"{REPOSITORY}/releases/tag/{tag}" if tag else None}


def verify_deployed(manifest: dict, root: Path) -> dict:
    tag, commit = manifest.get("tag", ""), manifest.get("commit", "")
    if not isinstance(tag, str) or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("Production has no valid release tag")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Production has no valid code commit")
    if manifest.get("version") != tag[1:] or manifest.get("release_url") != f"{REPOSITORY}/releases/tag/{tag}":
        raise ValueError("Production release identity is inconsistent")
    ref = "refs/tags/" + tag
    if git("cat-file", "-t", ref, root=root) != "tag" or git("rev-parse", ref + "^{commit}", root=root) != commit:
        raise ValueError("Production commit does not match the annotated tag")
    version = tomllib.loads(git("show", ref + ":pyproject.toml", root=root))["project"]["version"]
    if version != tag[1:]:
        raise ValueError("Production tag differs from the tagged project version")
    return manifest


def input_manifest(work: Path) -> list[dict]:
    inputs = []
    for meta_path in sorted((work / "data/raw").rglob("*.meta.json")):
        raw = meta_path.with_name(meta_path.name.removesuffix(".meta.json"))
        meta = json.loads(meta_path.read_text())
        sha = digest(raw)
        if raw.name.split("__sha256_")[-1].split(".")[0] != sha:
            raise ValueError(f"Cached content hash differs: {raw.name}")
        retrieved = datetime.strptime(raw.name.split("__")[0], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        item = {"path": str(raw.relative_to(work)), "url": redact_url(meta["url"]),
                "retrieved_at": retrieved.isoformat(), "sha256": sha}
        headers = {k.lower(): v for k, v in meta.get("headers", {}).items()}
        if headers.get("last-modified"):
            item["source_last_modified"] = headers["last-modified"]
        inputs.append(item)
    if not inputs:
        raise ValueError("No source inputs recorded")
    return inputs


def build(root: Path, output: Path, tag: str | None) -> None:
    release = identity(root, tag)
    if output.exists():
        raise ValueError("Output must be a new directory")
    load_dotenv(root / ".env")
    with tempfile.TemporaryDirectory(prefix="rb-build-") as temp:
        work = Path(temp)
        shutil.copytree(root / "spec", work / "spec")
        for args in [("ingest", "--refresh"), ("presidents", "--refresh"), ("compute",),
                     ("validate",), ("randomization", "--permutations", "10000", "--bootstrap-samples", "2000",
                                     "--seed", "42", "--term-block-years", "0", "--q-threshold", "0.05",
                                     "--min-term-n-obs", "12"), ("export-json",)]:
            subprocess.run([sys.executable, "-m", "rb", *args], cwd=work, check=True)
        data = json.loads((work / "site/data.json").read_text())
        if not data.get("metrics"):
            raise ValueError("Generated site has no metrics")
        provenance = {"generated_at": data["updated"], "generator": release,
                      "inputs": input_manifest(work),
                      "files": {str(p.relative_to(work)): digest(p)
                                for folder in ("spec", "data/derived", "reports")
                                for p in sorted((work / folder).rglob("*")) if p.is_file()},
                      "data_sha256": digest(work / "site/data.json"),
                      "inference": {"permutations": 10000, "bootstrap_samples": 2000,
                                    "seed": 42, "term_block_years": 0, "q_threshold": 0.05,
                                    "min_term_n_obs": 12}}
        shutil.copytree(root / "site", output,
                        ignore=shutil.ignore_patterns("data.json", "version.json", "provenance.json"))
        shutil.copyfile(work / "site/data.json", output / "data.json")
        write_json_atomic(output / "version.json", release)
        write_json_atomic(output / "provenance.json", provenance)
    print(f"Built {len(data['metrics'])} metrics at {output}")



def verify_artifact(site: Path, run: dict, root: Path) -> None:
    release = verify_deployed(json.loads((site / "version.json").read_text()), root)
    if run.get("head_sha") != release["commit"]:
        raise ValueError("Artifact does not match the selected workflow commit")
    provenance = json.loads((site / "provenance.json").read_text())
    if provenance.get("generator") != release or provenance.get("data_sha256") != digest(site / "data.json"):
        raise ValueError("Artifact data provenance differs from the release")
    for path in site.rglob("*"):
        if path.is_symlink():
            raise ValueError("Site artifact contains a symbolic link")
        if not path.is_file() or path.name in {"data.json", "version.json", "provenance.json"}:
            continue
        relative = path.relative_to(site).as_posix()
        expected = subprocess.check_output(["git", "show", release["commit"] + ":site/" + relative], cwd=root)
        if path.read_bytes() != expected:
            raise ValueError("Artifact static files differ from the released code")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("build", help="Regenerate the site in isolation using fresh source inputs.")
    make.add_argument("--output", type=Path, required=True)
    make.add_argument("--tag", help="Annotated release tag; omitted for a development build.")
    resolve = sub.add_parser("resolve", help="Verify production identity against the local release tags.")
    resolve.add_argument("--url", default="https://redvsblue.fyi/version.json")
    verify = sub.add_parser("verify-artifact", help="Check an artifact against its released commit and data hashes.")
    verify.add_argument("--site", type=Path, required=True)
    verify.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd()
    if args.command == "build":
        build(root, args.output.resolve(), args.tag)
    elif args.command == "verify-artifact":
        verify_artifact(args.site, json.loads(args.run.read_text()), root)
    else:
        request = Request(args.url, headers={"User-Agent": "redvsblue-release/1.0", "Cache-Control": "no-cache"})
        with urlopen(request, timeout=30) as response:
            manifest = verify_deployed(json.load(response), root)
        print("tag=" + manifest["tag"])
        print("commit=" + manifest["commit"])


if __name__ == "__main__":
    main()
