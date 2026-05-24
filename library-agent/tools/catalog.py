from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any

import requests

from shared.schemas import AvailabilityInfo, BookRecord

SRU_BASE_URL = "https://sru.k10plus.de/opac-de-18-302"
AVAILABILITY_URL = "https://kataloge.hh.gbv.de/LBS_WS/availability/titleinfo"

SRU_NS = {"zs": "http://www.loc.gov/zing/srw/", "p": "info:srw/schema/5/picaXML-v1.0"}


class CatalogError(RuntimeError):
    pass


def search_haw_books(query: str, limit: int = 5, enrich_availability: bool = True) -> list[BookRecord]:
    return search_haw_books_advanced(
        query=query,
        title=None,
        author=None,
        limit=limit,
        enrich_availability=enrich_availability,
    )


def search_haw_books_advanced(
    query: str | None,
    title: str | None,
    author: str | None,
    limit: int = 5,
    enrich_availability: bool = True,
) -> list[BookRecord]:
    limit = max(1, min(limit, 20))
    candidates = _build_query_candidates(query=query, title=title, author=author)

    # Query multiple strategies and merge unique results.
    merged: dict[str, BookRecord] = {}
    for cql in candidates:
        for book in _search_once(cql, per_query_limit=max(limit * 3, 10)):
            merged.setdefault(book.ppn, book)
        if len(merged) >= limit * 3:
            break

    books = list(merged.values())
    query_text = " ".join(part for part in [query or "", title or "", author or ""] if part).strip()
    books.sort(key=lambda b: _score_book_against_query(b, query_text), reverse=True)
    books = books[:limit]

    if enrich_availability:
        for book in books:
            if book.ppn:
                book.availability = get_availability_by_ppn(book.ppn)
    return books


def _search_once(cql_query: str, per_query_limit: int) -> list[BookRecord]:
    params = {
        "version": "1.1",
        "operation": "searchRetrieve",
        "query": cql_query,
        "maximumRecords": str(per_query_limit),
        "recordSchema": "picaxml",
    }
    response = requests.get(SRU_BASE_URL, params=params, timeout=20)
    response.raise_for_status()

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise CatalogError(f"Failed to parse SRU response: {exc}") from exc

    records = [_parse_picaxml_record(node) for node in root.findall(".//zs:recordData/p:record", SRU_NS)]
    return [r for r in records if r is not None]


def _build_query_candidates(query: str | None, title: str | None, author: str | None) -> list[str]:
    query = " ".join((query or "").split()).strip()
    title = " ".join((title or "").split()).strip()
    author = " ".join((author or "").split()).strip()

    candidates: list[str] = []

    if title and author:
        candidates.append(f'pica.tit="{title}" and pica.per="{author}"')
    if title:
        candidates.extend([f'pica.tit="{title}"', f'pica.all="{title}"'])
    if author:
        candidates.extend([f'pica.per="{author}"', f'pica.all="{author}"'])
    if query:
        candidates.extend([f'pica.all="{query}"', f'pica.tit="{query}"', f"pica.all={query}"])
    if not candidates:
        return []

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for item in candidates:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _score_book_against_query(book: BookRecord, query: str) -> int:
    query_tokens = _tokenize(query)
    title_tokens = _tokenize(f"{book.title} {book.subtitle or ''}")
    author_tokens = _tokenize(" ".join(book.authors) + " " + (book.responsibility or ""))

    overlap_title = len(query_tokens.intersection(title_tokens))
    overlap_author = len(query_tokens.intersection(author_tokens))
    score = overlap_title * 5 + overlap_author * 3

    return score


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(t) > 1}


def get_availability_by_ppn(ppn: str) -> AvailabilityInfo | None:
    params = {"BES": "2", "LAN": "DU", "USR": "1034", "PPN": ppn}
    headers = {"Accept": "application/json"}
    response = requests.get(AVAILABILITY_URL, params=params, headers=headers, timeout=20)
    response.raise_for_status()

    try:
        payload = response.json()
    except Exception as exc:
        raise CatalogError(f"Failed to parse availability response as JSON: {exc}") from exc

    copy_raw: Any = payload.get("copies", {}).get("copy")
    if isinstance(copy_raw, list):
        copy_obj = copy_raw[0] if copy_raw else None
    elif isinstance(copy_raw, dict):
        copy_obj = copy_raw
    else:
        copy_obj = None

    if not isinstance(copy_obj, dict):
        return None

    volume_raw: Any = copy_obj.get("volumes", {}).get("volume", {})
    if isinstance(volume_raw, list):
        volume_obj = volume_raw[0] if volume_raw else {}
    elif isinstance(volume_raw, dict):
        volume_obj = volume_raw
    else:
        volume_obj = {}

    messages_raw: Any = copy_obj.get("messages", {}).get("message")
    if isinstance(messages_raw, list):
        messages = " | ".join(str(m) for m in messages_raw)
    elif messages_raw is None:
        messages = None
    else:
        messages = str(messages_raw)

    loan_status_raw = volume_obj.get("loanstatus")
    loan_status = str(loan_status_raw) if loan_status_raw is not None else messages

    return AvailabilityInfo(
        location=_as_str(copy_obj.get("location")),
        shelfmark=_as_str(copy_obj.get("shelfmark")),
        loan_indication=_as_str(copy_obj.get("loanindication")),
        loan_status=loan_status,
        description=_as_str(copy_obj.get("description")),
        action_description=_as_str(copy_obj.get("actionDescription")),
        action_url=_as_str(copy_obj.get("actionurl")),
    )


def _parse_picaxml_record(record_node: ET.Element) -> BookRecord | None:
    fields: dict[str, list[dict[str, str]]] = defaultdict(list)
    for df in record_node.findall("./p:datafield", SRU_NS):
        tag = df.attrib.get("tag")
        if not tag:
            continue
        subfields: dict[str, str] = {}
        for sf in df.findall("./p:subfield", SRU_NS):
            code = sf.attrib.get("code")
            if not code:
                continue
            text = (sf.text or "").strip()
            if text:
                # Keep first occurrence per code for predictable outputs.
                subfields.setdefault(code, text)
        fields[tag].append(subfields)

    ppn = _first_subfield(fields, "003@", "0")
    if not ppn:
        return None

    title = _first_subfield(fields, "021A", "a") or "Unknown Title"
    subtitle = _first_subfield(fields, "021A", "d")
    responsibility = _first_subfield(fields, "021A", "h")

    author_candidates = []
    for tag in ("028A", "028B", "028C"):
        for entry in fields.get(tag, []):
            if "a" in entry:
                author_candidates.append(entry["a"])

    isbns = []
    for entry in fields.get("004A", []):
        raw = entry.get("0")
        if raw:
            isbns.append(raw)

    year = _first_subfield(fields, "011@", "a")
    if not year:
        year = _extract_year_from_fields(fields)

    epn = _first_subfield(fields, "203@", "0")
    library_sigel = _first_subfield(fields, "209A", "f")
    local_shelfmark = _first_subfield(fields, "209A", "a")
    media_number = _first_subfield(fields, "209G", "a")

    return BookRecord(
        ppn=ppn,
        title=title,
        subtitle=subtitle,
        responsibility=responsibility,
        authors=author_candidates,
        year=year,
        isbn=isbns,
        epn=epn,
        library_sigel=library_sigel,
        local_shelfmark=local_shelfmark,
        media_number=media_number,
    )


def _first_subfield(fields: dict[str, list[dict[str, str]]], tag: str, code: str) -> str | None:
    for entry in fields.get(tag, []):
        value = entry.get(code)
        if value:
            return value
    return None


def _extract_year_from_fields(fields: dict[str, list[dict[str, str]]]) -> str | None:
    for tag in ("011@", "011A", "011B"):
        for entry in fields.get(tag, []):
            for val in entry.values():
                maybe = _find_year(val)
                if maybe:
                    return maybe
    return None


def _find_year(text: str) -> str | None:
    digits = "".join(ch if ch.isdigit() else " " for ch in text).split()
    for part in digits:
        if len(part) == 4 and part.startswith(("19", "20")):
            return part
    return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def serialize_books_for_tool(books: list[BookRecord]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for b in books:
        output.append(
            {
                "ppn": b.ppn,
                "title": b.title,
                "subtitle": b.subtitle,
                "display_title": b.display_title,
                "responsibility": b.responsibility,
                "authors": b.authors,
                "year": b.year,
                "isbn": b.isbn,
                "epn": b.epn,
                "library_sigel": b.library_sigel,
                "local_shelfmark": b.local_shelfmark,
                "media_number": b.media_number,
                "availability": (
                    None
                    if not b.availability
                    else {
                        "location": b.availability.location,
                        "shelfmark": b.availability.shelfmark,
                        "loan_indication": b.availability.loan_indication,
                        "loan_status": b.availability.loan_status,
                        "description": b.availability.description,
                        "action_description": b.availability.action_description,
                        "action_url": b.availability.action_url,
                    }
                ),
            }
        )
    return output
