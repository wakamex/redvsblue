from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rb.sources.congress_legislators import fetch_executive_json
from rb.sources.wikidata import fetch_presidents_terms
from rb.util import write_text_atomic

DEMOCRATIC_QID = "Q29552"
REPUBLICAN_QID = "Q29468"


@dataclass(frozen=True)
class PresidentTerm:
    term_id: str
    person_qid: str
    president: str
    party_qid: str
    party: str
    party_abbrev: str
    term_start: date
    term_end: date
    term_number_for_person: int


def _qid(uri: str) -> str:
    # Example: http://www.wikidata.org/entity/Q76
    return uri.rstrip("/").split("/")[-1]


def _parse_date(s: str) -> date:
    # Wikidata returns xsd:dateTime; other sources use ISO date; keep date component.
    return date.fromisoformat(s[:10])


def _party_abbrev(party_qid: str) -> str:
    if party_qid == DEMOCRATIC_QID:
        return "D"
    if party_qid == REPUBLICAN_QID:
        return "R"
    return "Other"


def _choose_party(group_rows: list[dict]) -> tuple[str, str]:
    """Pick a party for a (person,start,end) group."""
    parties = [(r.get("party_qid", ""), r.get("party", "")) for r in group_rows if r.get("party_qid")]
    if not parties:
        return "", ""

    qids = {qid for qid, _ in parties}
    if DEMOCRATIC_QID in qids:
        return DEMOCRATIC_QID, next(lbl for qid, lbl in parties if qid == DEMOCRATIC_QID)
    if REPUBLICAN_QID in qids:
        return REPUBLICAN_QID, next(lbl for qid, lbl in parties if qid == REPUBLICAN_QID)

    return parties[0]


def _number_terms(terms: list[PresidentTerm]) -> list[PresidentTerm]:
    per_person_counts: dict[str, int] = {}
    numbered: list[PresidentTerm] = []
    for t in sorted(terms, key=lambda x: (x.person_qid, x.term_start)):
        per_person_counts[t.person_qid] = per_person_counts.get(t.person_qid, 0) + 1
        numbered.append(
            PresidentTerm(
                **{**t.__dict__, "term_number_for_person": per_person_counts[t.person_qid]},  # type: ignore[arg-type]
            )
        )
    return numbered


def _merge_consecutive_tenures(terms: list[PresidentTerm]) -> list[PresidentTerm]:
    """Merge consecutive presidential terms for the same person into a single tenure.

    We merge when:
    - same person_qid
    - same party_abbrev (and party_qid when available)
    - previous.term_end == next.term_start
    """
    merged: list[PresidentTerm] = []
    by_person: dict[str, list[PresidentTerm]] = {}
    for t in terms:
        by_person.setdefault(t.person_qid, []).append(t)

    for person_qid, pts in by_person.items():
        pts_sorted = sorted(pts, key=lambda x: x.term_start)
        cur = None
        for t in pts_sorted:
            if cur is None:
                cur = t
                continue
            same_party = (cur.party_abbrev == t.party_abbrev) and ((not cur.party_qid and not t.party_qid) or cur.party_qid == t.party_qid)
            if same_party and cur.term_end == t.term_start:
                cur = PresidentTerm(
                    term_id=f"{person_qid}_{cur.term_start.isoformat()}",
                    person_qid=person_qid,
                    president=cur.president,
                    party_qid=cur.party_qid,
                    party=cur.party,
                    party_abbrev=cur.party_abbrev,
                    term_start=cur.term_start,
                    term_end=t.term_end,
                    term_number_for_person=0,
                )
            else:
                merged.append(
                    PresidentTerm(
                        **{**cur.__dict__, "term_number_for_person": 0},  # type: ignore[arg-type]
                    )
                )
                cur = t
        if cur is not None:
            merged.append(
                PresidentTerm(
                    **{**cur.__dict__, "term_number_for_person": 0},  # type: ignore[arg-type]
                )
            )

    # Re-number within person after merging.
    return _number_terms(merged)


def _write_presidents_csv(out_path: Path, terms: list[PresidentTerm]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "term_id",
        "person_qid",
        "president",
        "party_qid",
        "party",
        "party_abbrev",
        "term_number_for_person",
        "term_start",
        "term_end",
    ]
    lines = [",".join(header)]
    for t in sorted(terms, key=lambda x: x.term_start):
        vals = [
            t.term_id,
            t.person_qid,
            t.president.replace(",", " "),
            t.party_qid,
            t.party.replace(",", " "),
            t.party_abbrev,
            str(t.term_number_for_person),
            t.term_start.isoformat(),
            t.term_end.isoformat(),
        ]
        lines.append(",".join(vals))
    write_text_atomic(out_path, "\n".join(lines) + "\n")


def _presidents_from_wikidata(*, refresh: bool) -> list[PresidentTerm]:
    raw_path = fetch_presidents_terms(refresh=refresh)
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    bindings = payload.get("results", {}).get("bindings", [])

    rows: list[dict] = []
    for b in bindings:
        person_uri = (b.get("person") or {}).get("value", "")
        if not person_uri:
            continue
        start = (b.get("start") or {}).get("value", "")
        if not start:
            continue
        end = (b.get("end") or {}).get("value", "")
        party_uri = (b.get("party") or {}).get("value", "")
        rows.append(
            {
                "person_qid": _qid(person_uri),
                "president": (b.get("personLabel") or {}).get("value", ""),
                "party_qid": _qid(party_uri) if party_uri else "",
                "party": (b.get("partyLabel") or {}).get("value", "") if party_uri else "",
                "term_start": _parse_date(start),
                "term_end": _parse_date(end) if end else date(9999, 12, 31),
            }
        )

    # Group rows by (person,start,end) to de-dup party cartesian effects.
    grouped: dict[tuple[str, date, date], list[dict]] = {}
    for r in rows:
        k = (r["person_qid"], r["term_start"], r["term_end"])
        grouped.setdefault(k, []).append(r)

    terms: list[PresidentTerm] = []
    # Stable ordering by start date, then person qid.
    for (person_qid, start, end) in sorted(grouped.keys(), key=lambda t: (t[1], t[0])):
        group = grouped[(person_qid, start, end)]
        president = group[0].get("president", "")
        party_qid, party = _choose_party(group)
        party_abbrev = _party_abbrev(party_qid) if party_qid else "Other"
        term_id = f"{person_qid}_{start.isoformat()}"
        terms.append(
            PresidentTerm(
                term_id=term_id,
                person_qid=person_qid,
                president=president,
                party_qid=party_qid,
                party=party,
                party_abbrev=party_abbrev,
                term_start=start,
                term_end=end,
                term_number_for_person=0,  # fill below
            )
        )
    return _number_terms(terms)


def _party_from_name(party: str) -> tuple[str, str, str]:
    p = (party or "").strip()
    p_low = p.lower()
    if p_low in {"democrat", "democratic", "democratic party"}:
        return DEMOCRATIC_QID, "Democratic Party", "D"
    if p_low in {"republican", "republican party"}:
        return REPUBLICAN_QID, "Republican Party", "R"
    return "", p, "Other"


def _presidents_from_congress_legislators(*, refresh: bool) -> list[PresidentTerm]:
    raw_path = fetch_executive_json(refresh=refresh)
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("congress-legislators executive.json: expected list")

    terms: list[PresidentTerm] = []
    for person in payload:
        if not isinstance(person, dict):
            continue
        ids = person.get("id") or {}
        person_qid = str(ids.get("wikidata") or "").strip()
        if not person_qid:
            # Fall back to govtrack id for stability.
            gt = ids.get("govtrack")
            person_qid = f"govtrack:{gt}" if gt is not None else ""
        name = person.get("name") or {}
        official = str(name.get("official_full") or "").strip()
        if official:
            president = official
        else:
            first = str(name.get("first") or "").strip()
            last = str(name.get("last") or "").strip()
            president = f"{first} {last}".strip()

        for term in person.get("terms") or []:
            if not isinstance(term, dict):
                continue
            if str(term.get("type") or "") != "prez":
                continue
            start = str(term.get("start") or "").strip()
            if not start:
                continue
            end = str(term.get("end") or "").strip()
            party = str(term.get("party") or "").strip()
            party_qid, party_name, party_abbrev = _party_from_name(party)
            term_start = _parse_date(start)
            term_end = _parse_date(end) if end else date(9999, 12, 31)
            term_id = f"{person_qid}_{term_start.isoformat()}" if person_qid else f"{president}_{term_start.isoformat()}"
            terms.append(
                PresidentTerm(
                    term_id=term_id,
                    person_qid=person_qid,
                    president=president,
                    party_qid=party_qid,
                    party=party_name,
                    party_abbrev=party_abbrev,
                    term_start=term_start,
                    term_end=term_end,
                    term_number_for_person=0,  # fill below
                )
            )

    return _number_terms(terms)


def ensure_presidents(
    *,
    refresh: bool,
    source: str = "congress_legislators",
    output_csv: Path = Path("data/derived/presidents.csv"),
    granularity: str = "tenure",
) -> Path:
    if source == "wikidata":
        terms = _presidents_from_wikidata(refresh=refresh)
    elif source == "congress_legislators":
        terms = _presidents_from_congress_legislators(refresh=refresh)
    else:
        raise ValueError(f"Unsupported presidents source: {source!r}")

    if granularity == "tenure":
        terms = _merge_consecutive_tenures(terms)
    elif granularity == "term":
        pass
    else:
        raise ValueError(f"Unsupported presidents granularity: {granularity!r}")

    _write_presidents_csv(output_csv, terms)
    return output_csv


def load_presidents_csv(path: Path) -> list[PresidentTerm]:
    terms: list[PresidentTerm] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            terms.append(
                PresidentTerm(
                    term_id=row["term_id"],
                    person_qid=row["person_qid"],
                    president=row["president"],
                    party_qid=row.get("party_qid", ""),
                    party=row.get("party", ""),
                    party_abbrev=row.get("party_abbrev", "Other"),
                    term_start=_parse_date(row["term_start"]),
                    term_end=_parse_date(row["term_end"]),
                    term_number_for_person=int(row.get("term_number_for_person", "0") or 0),
                )
            )
    return sorted(terms, key=lambda t: t.term_start)
