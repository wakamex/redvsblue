from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import lxml.html

from rb.sources.congress_control import fetch_house_party_divisions_html, fetch_senate_party_divisions_html
from rb.util import write_text_atomic


@dataclass(frozen=True)
class CongressControl:
    congress: int
    start_date: date
    end_date: date
    house_majority: str
    senate_majority: str
    house_dem: int | None = None
    house_rep: int | None = None
    house_other: int | None = None
    senate_majority_seats: int | None = None


_CONGRESS_RE = re.compile(r"(?P<num>\d+)\s*(?:st|nd|rd|th)\s+Congress\s*\(\s*(?P<y0>\d{4}).*?(?P<y1>\d{4})\s*\)", re.I)
_CONGRESS_RE_LOOSE = re.compile(r"(?P<num>\d+)\s*(?:st|nd|rd|th)\s*\(\s*(?P<y0>\d{4}).*?(?P<y1>\d{4})\s*\)", re.I)


def _party_abbrev(label: str, *, year: int | None = None) -> str:
    s = " ".join((label or "").strip().lower().split())

    # Avoid mislabeling pre-GOP-era "Republicans" (Democratic-Republicans, etc.) as modern GOP.
    if year is not None and year < 1854:
        if s in {"democrats", "democrat"}:
            return "D"
        return "Other"

    if s in {"democrats", "democrat"}:
        return "D"
    if s in {"republicans", "republican"}:
        return "R"
    return "Other"


def _congress_start_date(congress: int, start_year: int) -> date:
    # Congress start date moved from Mar 4 to Jan 3 starting with the 74th Congress (20th Amendment).
    if congress >= 74:
        return date(start_year, 1, 3)
    return date(start_year, 3, 4)


def _congress_end_date(congress: int, end_year: int) -> date:
    if congress >= 74:
        return date(end_year, 1, 3)
    return date(end_year, 3, 4)


def _parse_int(s: str) -> int | None:
    txt = (s or "").strip()
    if not txt:
        return None
    txt = re.sub(r"[,\u00a0\s]+", "", txt)
    if not txt.isdigit():
        return None
    return int(txt)


def _parse_house() -> dict[int, CongressControl]:
    raw_path = Path("data/derived/congress_control/house_party_divisions.html")
    html = raw_path.read_text(encoding="utf-8", errors="replace")
    doc = lxml.html.fromstring(html)

    # Find the table that contains the party division by Congress.
    best = None
    for tbl in doc.xpath("//table"):
        hdr = " ".join(" ".join(tbl.xpath(".//th//text()")).split()).lower()
        if "congress" in hdr and "democrats" in hdr and "republicans" in hdr:
            best = tbl
            break
    if best is None:
        raise ValueError("Could not find House party division table in HTML")

    out: dict[int, CongressControl] = {}

    # This page uses one big table with multiple header rows. We only interpret D/R majority when the
    # current header row contains explicit "Democrats" and "Republicans" columns; earlier periods use
    # different faction labels and are not comparable to modern D/R.
    idx_dem: int | None = None
    idx_rep: int | None = None
    idx_other: int | None = None

    for tr in best.xpath(".//tr"):
        ths = tr.xpath("./th")
        if ths:
            labels = [" ".join(th.text_content().split()).strip() for th in ths]
            lowered = [s.lower() for s in labels]
            idx_dem = next((i for i, s in enumerate(lowered) if s == "democrats"), None)
            idx_rep = next((i for i, s in enumerate(lowered) if s == "republicans"), None)
            idx_other = next((i for i, s in enumerate(lowered) if s == "other"), None)
            continue

        tds = tr.xpath("./td")
        if len(tds) < 2:
            continue
        c0 = " ".join(tds[0].text_content().split())
        if not c0:
            continue

        m = _CONGRESS_RE_LOOSE.search(c0)
        if not m:
            continue
        congress = int(m.group("num"))
        y0 = int(m.group("y0"))
        y1 = int(m.group("y1"))

        dem: int | None = None
        rep: int | None = None
        other: int | None = None
        house_majority = "Other"

        if idx_dem is not None and idx_rep is not None and idx_dem < len(tds) and idx_rep < len(tds):
            dem = _parse_int(tds[idx_dem].text_content())
            rep = _parse_int(tds[idx_rep].text_content())
            if idx_other is not None and idx_other < len(tds):
                other_txt = " ".join(tds[idx_other].text_content().split())
                if other_txt.strip() == "0":
                    other = 0
                elif other_txt.strip() == "":
                    other = None
                else:
                    other = sum(int(x) for x in re.findall(r"\((\d+)\)", other_txt))

            if dem is not None and rep is not None:
                if dem > rep:
                    house_majority = "D"
                elif rep > dem:
                    house_majority = "R"
                else:
                    house_majority = "Tie"

        out[congress] = CongressControl(
            congress=congress,
            start_date=_congress_start_date(congress, y0),
            end_date=_congress_end_date(congress, y1),
            house_majority=house_majority,
            senate_majority="",
            house_dem=dem,
            house_rep=rep,
            house_other=other,
        )

    if not out:
        raise ValueError("Parsed 0 House congress rows")
    return out


def _parse_senate() -> dict[int, list[tuple[date, date, str, int | None, int, int]]]:
    # Returns congress -> list of (start_date, end_date, majority_party_abbrev, majority_seats, start_year, end_year).
    raw_path = Path("data/derived/congress_control/senate_party_divisions.html")
    html = raw_path.read_text(encoding="utf-8", errors="replace")
    doc = lxml.html.fromstring(html)

    month_map = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }

    def _parse_date_piece(piece: str, *, default_year: int | None, default_month: int | None) -> tuple[int | None, int | None, int | None]:
        p = " ".join(piece.replace("\u00a0", " ").split()).strip().strip(",")
        if not p:
            return None, None, None
        m = re.match(r"^(?P<mon>[A-Za-z]+)\s+(?P<day>\d{1,2})(?:,\s*(?P<year>\d{4}))?$", p)
        if m:
            mon = month_map.get(m.group("mon").lower())
            day = int(m.group("day"))
            year = int(m.group("year")) if m.group("year") else default_year
            return year, mon, day
        m = re.match(r"^(?P<day>\d{1,2})(?:,\s*(?P<year>\d{4}))?$", p)
        if m:
            day = int(m.group("day"))
            year = int(m.group("year")) if m.group("year") else default_year
            return year, default_month, day
        return None, None, None

    def _parse_range(range_txt: str, *, congress_start_year: int) -> tuple[date, date] | None:
        # Examples:
        # - "Jan 3–20, 2001"
        # - "Jan 20–June 6, 2001"
        # - "June 6, 2001–November 12, 2002"
        # - "November 12, 2002–January 3, 2003"
        parts = re.split(r"\s*[\u2013\-]\s*", range_txt.strip())
        if len(parts) != 2:
            return None
        a_raw, b_raw = parts[0].strip(), parts[1].strip()

        # Parse start; it may omit the year.
        a_year, a_mon, a_day = _parse_date_piece(a_raw, default_year=None, default_month=None)

        # Parse end; it often includes a year but may omit month (e.g. "Jan 3–20, 2001").
        b_year, b_mon, b_day = _parse_date_piece(b_raw, default_year=congress_start_year, default_month=a_mon)
        if b_year is None or b_mon is None or b_day is None:
            return None

        if a_mon is None:
            # If start omitted month, inherit from end.
            a_year2, a_mon2, a_day2 = _parse_date_piece(a_raw, default_year=None, default_month=b_mon)
            a_year, a_mon, a_day = a_year2, a_mon2, a_day2
        if a_year is None:
            # Infer year from end year; if the range crosses year boundary, subtract 1.
            a_year = b_year - 1 if (a_mon is not None and a_mon > b_mon) else b_year
        if a_mon is None or a_day is None:
            return None

        return date(a_year, a_mon, a_day), date(b_year, b_mon, b_day)

    out: dict[int, list[tuple[date, date, str, int | None, int, int]]] = {}
    maj_re = re.compile(
        r"Majority Party(?:\s*\((?P<range>[^\)]*)\))?:\s*(?P<party>[^\(]+)\((?P<seats>\d+)(?:\s+seats?)?\)",
        re.I,
    )
    # The page uses <b>... Congress (YYYY–YYYY)</b>.
    for b in doc.xpath("//b"):
        txt = " ".join(b.text_content().split())
        m = _CONGRESS_RE.search(txt)
        if not m:
            continue
        congress = int(m.group("num"))
        y0 = int(m.group("y0"))
        y1 = int(m.group("y1"))

        congress_start = _congress_start_date(congress, y0)
        congress_end = _congress_end_date(congress, y1)

        matches: list[tuple[str | None, str, int | None]] = []

        # On this page, the <b> is wrapped in a <p>, so look at subsequent siblings of that parent <p>.
        parent = b.getparent()
        start_node = parent if parent is not None else b
        node = start_node
        while node is not None:
            # Stop once we reach the next Congress heading.
            if node is not start_node and node.xpath(".//b"):
                maybe_hdr = " ".join(node.text_content().split())
                if _CONGRESS_RE.search(maybe_hdr):
                    break
            if node.tag == "p":
                ptxt = " ".join(node.text_content().split())
                for mm in maj_re.finditer(ptxt):
                    party = _party_abbrev(mm.group("party"), year=y0)
                    seats = int(mm.group("seats")) if mm.group("seats") else None
                    rtxt = mm.group("range")
                    matches.append((rtxt, party, seats))
            node = node.getnext()

        if not matches:
            continue

        periods: list[tuple[date, date, str, int | None, int, int]] = []
        ranged = [m for m in matches if m[0]]
        if ranged:
            for rtxt, party, seats in ranged:
                assert rtxt is not None
                rr = _parse_range(rtxt, congress_start_year=y0)
                if not rr:
                    continue
                s, e = rr
                # Clamp to Congress bounds; treat parsed ranges as half-open [s,e).
                if e <= s:
                    continue
                s2 = max(s, congress_start)
                e2 = min(e, congress_end)
                if e2 <= s2:
                    continue
                periods.append((s2, e2, party, seats, y0, y1))
            if not periods:
                # Fallback to the first match over the whole Congress.
                rtxt, party, seats = matches[0]
                periods.append((congress_start, congress_end, party, seats, y0, y1))
        else:
            # Single majority party for the whole Congress.
            rtxt, party, seats = matches[0]
            periods.append((congress_start, congress_end, party, seats, y0, y1))

        out[congress] = sorted(periods, key=lambda t: t[0])

    if not out:
        raise ValueError("Parsed 0 Senate congress rows")
    return out


def ensure_congress_control(*, refresh: bool) -> Path:
    fetch_house_party_divisions_html(refresh=refresh)
    fetch_senate_party_divisions_html(refresh=refresh)

    house = _parse_house()
    senate = _parse_senate()

    # Merge on congress number.
    merged: list[CongressControl] = []
    for congress, h in sorted(house.items()):
        periods = senate.get(congress)
        if not periods:
            merged.append(h)
            continue

        for s0, s1, sen_party, sen_seats, y0, y1 in periods:
            # Prefer Senate-provided period bounds when present; clamp to House Congress bounds.
            start = max(h.start_date, s0)
            end = min(h.end_date, s1)
            if end <= start:
                continue
            merged.append(
                CongressControl(
                    congress=congress,
                    start_date=start,
                    end_date=end,
                    house_majority=h.house_majority,
                    senate_majority=sen_party,
                    house_dem=h.house_dem,
                    house_rep=h.house_rep,
                    house_other=h.house_other,
                    senate_majority_seats=sen_seats,
                )
            )

    derived_dir = Path("data/derived/congress_control")
    derived_dir.mkdir(parents=True, exist_ok=True)
    out_path = derived_dir / "congress_control.csv"

    header = [
        "congress",
        "start_date",
        "end_date",
        "house_majority",
        "senate_majority",
        "house_dem",
        "house_rep",
        "house_other",
        "senate_majority_seats",
    ]
    lines = [",".join(header)]
    for r in merged:
        lines.append(
            ",".join(
                [
                    str(r.congress),
                    r.start_date.isoformat(),
                    r.end_date.isoformat(),
                    r.house_majority,
                    r.senate_majority,
                    "" if r.house_dem is None else str(r.house_dem),
                    "" if r.house_rep is None else str(r.house_rep),
                    "" if r.house_other is None else str(r.house_other),
                    "" if r.senate_majority_seats is None else str(r.senate_majority_seats),
                ]
            )
        )
    write_text_atomic(out_path, "\n".join(lines) + "\n")
    return out_path


def load_congress_control_csv(path: Path) -> list[CongressControl]:
    out: list[CongressControl] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            congress = int(row["congress"])
            out.append(
                CongressControl(
                    congress=congress,
                    start_date=date.fromisoformat(row["start_date"]),
                    end_date=date.fromisoformat(row["end_date"]),
                    house_majority=row.get("house_majority", ""),
                    senate_majority=row.get("senate_majority", ""),
                    house_dem=int(row["house_dem"]) if (row.get("house_dem") or "").strip() else None,
                    house_rep=int(row["house_rep"]) if (row.get("house_rep") or "").strip() else None,
                    house_other=int(row["house_other"]) if (row.get("house_other") or "").strip() else None,
                    senate_majority_seats=int(row["senate_majority_seats"]) if (row.get("senate_majority_seats") or "").strip() else None,
                )
            )
    return sorted(out, key=lambda x: x.start_date)
