#!/usr/bin/env python
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import ssl
import sys
import urllib.request
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
LITERATURE_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = LITERATURE_DIR / "_templates"
VENDOR_DIR = SCRIPT_DIR / "_vendor"

if VENDOR_DIR.exists():
    # Local vendoring keeps installs inside the repo (works in sandboxed environments).
    sys.path.insert(0, str(VENDOR_DIR))


def now_utc_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def download(url: str, dst: Path, *, timeout_s: int = 60) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "rb-literature-fetch/1.0 (+https://example.invalid)",
            "Accept": "*/*",
        },
    )
    # Use certifi if available to avoid brittle system CA stores (common in sandboxed environments).
    context = None
    try:  # pragma: no cover
        import certifi  # type: ignore

        context = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        context = ssl.create_default_context()

    with urllib.request.urlopen(req, timeout=timeout_s, context=context) as r:  # nosec - intended
        tmp.write_bytes(r.read())
    tmp.replace(dst)


def normalize_text(s: str) -> str:
    # Collapse whitespace but keep paragraph-ish separation.
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.split("\n")]
    out: list[str] = []
    blank = False
    for ln in lines:
        if not ln:
            if not blank:
                out.append("")
            blank = True
            continue
        blank = False
        out.append(ln)
    return "\n".join(out).strip() + "\n"


def extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pdfminer.six not available. Install into literature/_scripts/_vendor, e.g.\n"
            "  python -m pip install --target literature/_scripts/_vendor -r literature/_scripts/requirements.txt"
        ) from e

    return extract_text(str(pdf_path))


def extract_text_from_html(html_bytes: bytes) -> tuple[str, str | None]:
    # Returns (text, title)
    try:
        import lxml.html  # type: ignore
    except Exception:  # pragma: no cover
        # Fallback: extremely naive stripping.
        html = html_bytes.decode("utf-8", errors="replace")
        html = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\\1>", "", html)
        html = re.sub(r"(?is)<[^>]+>", " ", html)
        return normalize_text(html), None

    doc = lxml.html.fromstring(html_bytes)
    title = None
    try:
        title_el = doc.xpath("//title")
        if title_el:
            title = title_el[0].text_content().strip() or None
    except Exception:
        title = None

    # Remove always-noisy elements that never contain meaningful article content.
    for bad in doc.xpath("//script|//style|//noscript|//svg|//iframe"):
        try:
            bad.drop_tree()
        except Exception:
            pass

    # Prefer main content containers.
    node = None
    # `article` is often used for "related items" in sidebars; prefer `main` when present.
    for xp in ("//main", "//article", "//body"):
        els = doc.xpath(xp)
        if els:
            node = els[0]
            break
    if node is None:
        node = doc

    # Trim boilerplate *within* the selected node. We intentionally avoid dropping
    # top-level structural tags globally because some pages have malformed markup
    # that nests main content under a `<header>` element.
    for bad in node.xpath(".//form|.//nav|.//footer|.//header|.//aside"):
        try:
            bad.drop_tree()
        except Exception:
            pass

    text = node.text_content()
    return normalize_text(text), title


def extract_text_from_plain_bytes(b: bytes) -> str:
    # For JSON/CSV/TXT sources that are already text.
    return b.decode("utf-8", errors="replace")


def first_nonempty_line(s: str, *, max_len: int = 160) -> str | None:
    for ln in s.splitlines():
        ln = ln.strip()
        if ln:
            return ln[:max_len]
    return None


def ensure_notes(notes_path: Path, *, title: str | None, url: str) -> None:
    if notes_path.exists():
        return
    tmpl = (TEMPLATES_DIR / "NOTES_TEMPLATE.md").read_text(encoding="utf-8")
    rendered = tmpl
    rendered = rendered.replace("<title>", title or "TBD")
    rendered = rendered.replace("<url>", url)
    rendered = rendered.replace("<authors>", "TBD")
    rendered = rendered.replace("<date>", "TBD")
    rendered = rendered.replace("<yyyy-mm-dd>", _dt.date.today().isoformat())
    rendered = rendered.replace("<slug>", notes_path.parent.name)
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(rendered, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Download literature sources and extract raw text.")
    ap.add_argument("--manifest", default=str(LITERATURE_DIR / "manifest.json"))
    ap.add_argument("--force", action="store_true", help="Redownload and re-extract even if files exist")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    m = read_json(manifest_path)
    changed = False

    failures: list[tuple[str, str]] = []

    for src in m.get("sources", []):
        slug = src["slug"]
        url = src["url"]
        typ = (src.get("type") or "html").lower()

        base_dir = LITERATURE_DIR / slug
        base_dir.mkdir(parents=True, exist_ok=True)

        files = src.get("files", {})
        source_path = Path(files.get("source", str(base_dir / "source.bin")))
        text_path = Path(files.get("text", str(base_dir / "source.txt")))
        notes_path = Path(files.get("notes", str(base_dir / "notes.md")))

        try:
            # Download
            if args.force or not source_path.exists():
                print(f"[fetch] {slug}: {url}")
                download(url, source_path)
                src["retrieved_at"] = now_utc_iso()
                changed = True

            # Extract
            if args.force or not text_path.exists():
                print(f"[extract] {slug}: {typ}")
                title = src.get("title")
                if typ == "pdf" or source_path.suffix.lower() == ".pdf":
                    extracted = extract_text_from_pdf(source_path)
                    extracted_norm = normalize_text(extracted)
                    text_path.write_text(extracted_norm, encoding="utf-8")
                    if not title:
                        maybe_title = first_nonempty_line(extracted_norm)
                        if maybe_title:
                            src["title"] = maybe_title
                            title = maybe_title
                            changed = True
                elif typ in {"text", "json", "csv"}:
                    extracted = extract_text_from_plain_bytes(source_path.read_bytes())
                    extracted_norm = normalize_text(extracted)
                    text_path.write_text(extracted_norm, encoding="utf-8")
                    if not title:
                        maybe_title = first_nonempty_line(extracted_norm)
                        if maybe_title:
                            src["title"] = maybe_title
                            title = maybe_title
                            changed = True
                else:
                    html_bytes = source_path.read_bytes()
                    extracted, parsed_title = extract_text_from_html(html_bytes)
                    text_path.write_text(extracted, encoding="utf-8")
                    if not title and parsed_title:
                        src["title"] = parsed_title
                        title = parsed_title
                        changed = True

                ensure_notes(notes_path, title=src.get("title"), url=url)

            # Clear error markers on success.
            if src.get("last_error") is not None:
                src["last_error"] = None
                src["last_error_at"] = None
                changed = True
        except Exception as e:  # pragma: no cover
            msg = f"{type(e).__name__}: {e}"
            failures.append((slug, msg))
            src["last_error"] = msg[:500]
            src["last_error_at"] = now_utc_iso()
            changed = True
            print(f"[error] {slug}: {msg}", file=sys.stderr)
            continue

    if changed:
        write_json(manifest_path, m)
    if failures:
        print("\nFailures:", file=sys.stderr)
        for slug, msg in failures:
            print(f" - {slug}: {msg}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
