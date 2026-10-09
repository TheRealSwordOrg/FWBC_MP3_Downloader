#!/usr/bin/env python3
"""Download Faithful Word Baptist sermon MP3s by month or year.

The script accepts either:
    112006  -> November 2006
    2006    -> the entire year 2006

The script reads the sermon archive at page5.html, finds every sermon in the
requested period, downloads the MP3, and saves it using the same naming
convention as the FWB sermon renamer:

    20061101 - Matthew 28.mp3

For guest preachers:
    20260802 - The Severity of Charity - Bro. Chris Segura.mp3

Pastor Anderson is omitted from the filename because he is the default speaker.

Standard-library only: works on Windows and Linux with Python 3.10+.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import List
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

DEFAULT_URL = "https://www.faithfulwordbaptist.org/page5.html"

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')
MULTISPACE = re.compile(r"\s+")
DATE_RE = re.compile(
    r"\b(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{2}),?\s+"
    r"(?P<weekday>[A-Za-z]{3})\s+(?P<session>AM|PM)\b",
    re.IGNORECASE,
)


@dataclass
class Cell:
    text_parts: List[str]
    hrefs: List[str]

    @property
    def text(self) -> str:
        return " ".join(p.strip() for p in self.text_parts if p.strip()).strip()


@dataclass(frozen=True)
class Sermon:
    month: int
    day: int
    year: int
    session: str
    title: str
    mp3_url: str | None
    speaker: str

    @property
    def key(self) -> tuple[int, int, int, str]:
        return (self.year, self.month, self.day, self.session)

    @property
    def date_str(self) -> str:
        return f"{self.year:04d}{self.month:02d}{self.day:02d}"


class SermonCellParser(HTMLParser):
    """Extract table cells in document order, independent of row structure."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cells: list[Cell] = []
        self._in_cell = False
        self._current_cell: Cell | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attrs_dict = dict(attrs)

        if tag in ("td", "th"):
            self._in_cell = True
            self._current_cell = Cell(text_parts=[], hrefs=[])
            self.cells.append(self._current_cell)
        elif tag == "a" and self._in_cell and self._current_cell is not None:
            href = attrs_dict.get("href")
            if href:
                self._current_cell.hrefs.append(html.unescape(href.strip()))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in ("td", "th"):
            self._in_cell = False
            self._current_cell = None

    def handle_data(self, data: str) -> None:
        if self._in_cell and self._current_cell is not None:
            self._current_cell.text_parts.append(data)


def fetch_page(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (sermon-downloader; +https://www.faithfulwordbaptist.org/)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=30) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def looks_like_mp3(url: str) -> bool:
    try:
        return urlparse(url).path.lower().endswith(".mp3")
    except ValueError:
        return False


def extract_sermons(page_html: str, base_url: str) -> list[Sermon]:
    """Extract sermons by following the archive's date/title/links/speaker cell sequence.

    This intentionally does not depend on <tr> boundaries. The older portions of
    page5.html contain inconsistent table markup, while the four logical cells
    remain in the same order. Using cell order lets 2006-2026 be parsed together.
    """
    parser = SermonCellParser()
    parser.feed(page_html)
    cells = [cell for cell in parser.cells if cell.text or cell.hrefs]

    sermons: list[Sermon] = []

    for idx, cell in enumerate(cells):
        match = DATE_RE.search(cell.text)
        if not match:
            continue

        # Expected logical sequence is:
        #   date | title | links | speaker
        if idx + 1 >= len(cells):
            continue

        month = int(match.group("month"))
        day = int(match.group("day"))
        year = 2000 + int(match.group("year"))
        session = match.group("session").upper()

        try:
            date(year, month, day)
        except ValueError:
            continue

        title = cells[idx + 1].text.strip()
        if not title:
            continue

        links_cell = cells[idx + 2] if idx + 2 < len(cells) else Cell([], [])
        speaker_cell = cells[idx + 3] if idx + 3 < len(cells) else Cell([], [])
        speaker = speaker_cell.text.strip()

        # If the next cell is obviously not a speaker, leave speaker blank.
        # This handles occasional special/series rows in the old archive.
        if speaker and DATE_RE.search(speaker):
            speaker = ""

        mp3_links: list[str] = []
        all_links: list[str] = []
        for href in links_cell.hrefs:
            absolute = urljoin(base_url, href)
            all_links.append(absolute)
            if looks_like_mp3(absolute):
                mp3_links.append(absolute)

        mp3_url = mp3_links[0] if mp3_links else None
        if mp3_url is None:
            for link in all_links:
                lower = link.lower()
                if any(ext in lower for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".html", ".htm")):
                    continue
                if "rumble" in lower or "twitter" in lower or "x.com" in lower:
                    continue
                mp3_url = link
                break

        sermons.append(
            Sermon(
                month=month,
                day=day,
                year=year,
                session=session,
                title=title,
                mp3_url=mp3_url,
                speaker=speaker,
            )
        )

    # De-duplicate any accidental repeated rows while preserving the first URL.
    unique: dict[tuple[int, int, int, str, str], Sermon] = {}
    for sermon in sermons:
        key = (sermon.year, sermon.month, sermon.day, sermon.session, sermon.title)
        if key not in unique or (not unique[key].mp3_url and sermon.mp3_url):
            unique[key] = sermon

    return list(unique.values())


def sanitize_component(value: str) -> str:
    value = html.unescape(value)
    value = INVALID_FILENAME_CHARS.sub("", value)
    value = MULTISPACE.sub(" ", value).strip()
    return value.rstrip(" .")


def build_filename(sermon: Sermon) -> str:
    title = sanitize_component(sermon.title) or "Untitled Sermon"
    speaker = sanitize_component(sermon.speaker)
    if speaker and speaker.casefold() != "pastor anderson":
        return f"{sermon.date_str} - {title} - {speaker}.mp3"
    return f"{sermon.date_str} - {title}.mp3"


def parse_period_input(value: str) -> tuple[str, int, int | None]:
    """Return (period_type, year, month). month is None for a whole year."""
    cleaned = value.strip().replace("/", "").replace("-", "").replace(" ", "")

    if re.fullmatch(r"\d{4}", cleaned):
        year = int(cleaned)
        if not 2000 <= year <= 2099:
            raise ValueError("The year must be between 2000 and 2099.")
        return "year", year, None

    if re.fullmatch(r"\d{6}", cleaned):
        month = int(cleaned[:2])
        year = int(cleaned[2:])
        if not 1 <= month <= 12:
            raise ValueError("The first two digits must be a month from 01 to 12.")
        if not 2000 <= year <= 2099:
            raise ValueError("The year must be between 2000 and 2099.")
        return "month", year, month

    raise ValueError("Enter MMYYYY for a month (such as 112006), or YYYY for a whole year (such as 2006).")


def month_label(year: int, month: int) -> str:
    from calendar import month_name
    return f"{month_name[month]} {year}"


def period_label(period_type: str, year: int, month: int | None) -> str:
    if period_type == "month" and month is not None:
        return month_label(year, month)
    return str(year)


def download_file(url: str, target: Path, page_url: str) -> None:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (sermon-downloader; +https://www.faithfulwordbaptist.org/)",
            "Referer": page_url,
            "Accept": "audio/mpeg,audio/*;q=0.9,*/*;q=0.1",
        },
    )

    with urlopen(request, timeout=60) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        total = response.headers.get("Content-Length")
        total_bytes = int(total) if total and total.isdigit() else None

        first_chunk = response.read(64 * 1024)
        if not first_chunk:
            raise RuntimeError("server returned an empty file")

        # Don't silently save an HTML error page as an MP3.
        probe = first_chunk.lstrip().lower()
        if "text/html" in content_type or probe.startswith(b"<!doctype html") or probe.startswith(b"<html"):
            raise RuntimeError("server returned HTML instead of an MP3")

        written = len(first_chunk)
        with target.open("wb") as output:
            output.write(first_chunk)
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                written += len(chunk)

                if total_bytes:
                    percent = written * 100 / total_bytes
                    print(f"\r       {percent:5.1f}% ({written / 1048576:.1f} MiB)", end="", flush=True)
                else:
                    print(f"\r       {written / 1048576:.1f} MiB", end="", flush=True)

        if total_bytes:
            print(f"\r       100.0% ({written / 1048576:.1f} MiB)")
        else:
            print(f"\r       {written / 1048576:.1f} MiB")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download Faithful Word Baptist sermon MP3s for a chosen month or year."
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=Path.cwd(),
        help="Destination folder (default: current directory).",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Sermon archive URL (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the final confirmation prompt.",
    )
    args = parser.parse_args()

    folder = args.folder.expanduser()
    folder.mkdir(parents=True, exist_ok=True)

    print("Faithful Word Baptist Sermon Downloader")
    print("=" * 39)
    print()

    while True:
        raw_period = input(
            "Enter month/year (MMYYYY, e.g. 112006) or a whole year (YYYY, e.g. 2006): "
        ).strip()
        try:
            period_type, year, month = parse_period_input(raw_period)
            break
        except ValueError as exc:
            print(f"ERROR: {exc}\n")

    try:
        print(f"\nReading sermon list: {args.url}")
        page_html = fetch_page(args.url)
        sermons = extract_sermons(page_html, args.url)
        if sermons:
            years = sorted({s.year for s in sermons})
            print(f"Parsed {len(sermons)} sermon entries ({years[0]}-{years[-1]}).")
        else:
            print("Parsed 0 sermon entries from the page.")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        print(f"ERROR: could not retrieve the sermon page: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: could not parse the sermon page: {exc}", file=sys.stderr)
        return 1

    period_sermons = sorted(
        [
            s
            for s in sermons
            if s.year == year and (period_type == "year" or s.month == month)
        ],
        key=lambda s: (s.month, s.day, 0 if s.session == "AM" else 1, s.title.casefold()),
    )

    if not period_sermons:
        print(f"No sermons were found for {period_label(period_type, year, month)}.")
        return 0

    downloadable = [s for s in period_sermons if s.mp3_url]
    missing_links = [s for s in period_sermons if not s.mp3_url]

    print(f"\n{period_label(period_type, year, month)}: {len(period_sermons)} sermon(s) listed")
    print(f"MP3 links found: {len(downloadable)}")
    if missing_links:
        print(f"No MP3 link found: {len(missing_links)}")
    print()

    for sermon in period_sermons:
        filename = build_filename(sermon)
        status = "READY" if sermon.mp3_url else "NO MP3"
        print(f"{status:<7} {filename}")

    if not downloadable:
        return 0

    if not args.yes:
        print()
        answer = input(f"Download {len(downloadable)} MP3(s) to {folder.resolve()}? [Y/n]: ").strip().lower()
        if answer not in ("", "y", "yes"):
            print("Cancelled. Nothing was downloaded.")
            return 0

    print()
    downloaded = 0
    skipped = 0
    failed = 0

    for sermon in downloadable:
        filename = build_filename(sermon)
        target = folder / filename

        if target.exists():
            print(f"EXISTS  {filename}")
            skipped += 1
            continue

        print(f"DOWNLOAD {filename}")
        try:
            download_file(sermon.mp3_url or "", target, args.url)
            downloaded += 1
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            failed += 1
            print(f"       ERROR: {exc}")
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass

    print()
    print(f"Finished. Downloaded: {downloaded}, skipped: {skipped}, failed: {failed}.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
