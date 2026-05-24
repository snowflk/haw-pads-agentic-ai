from __future__ import annotations

import argparse
import re
from collections import deque
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.haw-hamburg.de/hibs/"
ALLOWED_HOST = "www.haw-hamburg.de"
ALLOWED_PREFIX = "/hibs/"


def crawl_hibs(output_dir: Path, max_pages: int = 300) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)

    queue = deque([BASE_URL])
    seen: set[str] = set()
    saved = 0

    while queue and saved < max_pages:
        url = normalize_url(queue.popleft())
        if url in seen:
            continue
        seen.add(url)
        if not is_allowed_url(url):
            continue

        html = fetch_page(url)
        if html is None:
            continue

        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.text or "").strip() if soup.title else ""
        markdown = html_to_markdown(soup, url=url, title=title)
        if markdown.strip():
            file_path = output_dir / f"{slug_from_url(url)}.md"
            file_path.write_text(markdown, encoding="utf-8")
            saved += 1

        for link in extract_links(soup, base_url=url):
            if link not in seen and is_allowed_url(link):
                queue.append(link)

    return saved


def fetch_page(url: str) -> str | None:
    try:
        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "library-agent-crawler/1.0 (+https://www.haw-hamburg.de/hibs/)",
            },
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return None
    return response.text


def extract_links(soup: BeautifulSoup, base_url: str) -> Iterable[str]:
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if not href:
            continue
        absolute = normalize_url(urljoin(base_url, href))
        if absolute:
            yield absolute


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme:
        parsed = parsed._replace(scheme="https")
    cleaned = parsed._replace(fragment="", params="", query="")
    normalized = urlunparse(cleaned)
    if normalized.endswith("/index.html"):
        normalized = normalized[: -len("index.html")]
    return normalized


def is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc != ALLOWED_HOST:
        return False
    if not parsed.path.startswith(ALLOWED_PREFIX):
        return False
    blocked_suffixes = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".doc", ".docx")
    if parsed.path.lower().endswith(blocked_suffixes):
        return False
    return True


def slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.strip("/").replace("/", "__")
    if not slug:
        slug = "root"
    slug = re.sub(r"[^a-zA-Z0-9_\\-]", "_", slug)
    return slug


def html_to_markdown(soup: BeautifulSoup, url: str, title: str) -> str:
    # Remove globally irrelevant elements first.
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    lines: list[str] = []
    clean_title = title.strip() or "HAW HIBS Page"
    lines.append(f"# {clean_title}")
    lines.append("")
    lines.append(f"Source: {url}")
    lines.append("")

    content_root = soup.select_one("#main") or soup.select_one('[role="main"]') or soup.find("main") or soup.body or soup

    # Remove noisy sections inside the content area.
    for selector in [
        "nav",
        "header",
        "footer",
        "aside",
        ".breadcrumb",
        ".news",
        ".news_list",
        ".social-media",
        ".sidebar",
        ".back-link",
        ".navbar",
        "form",
    ]:
        for node in content_root.select(selector):
            node.decompose()

    # Traverse common content tags in DOM order, including table rows for opening-hours grids.
    for tag in content_root.find_all(["h1", "h2", "h3", "h4", "p", "li", "tr"], recursive=True):
        if tag.name == "p" and tag.find_parent("table"):
            # Table paragraph text is captured via row extraction.
            continue

        if tag.name == "tr":
            cells = tag.find_all(["th", "td"])
            if not cells:
                continue
            parts = [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            parts = [p for p in parts if p and not _is_noise_line(p)]
            if not parts:
                continue
            text = " | ".join(parts)
        else:
            text = _clean_text(tag.get_text(" ", strip=True))

        if not text:
            continue
        if _is_noise_line(text):
            continue

        if tag.name == "h1":
            lines.append(f"# {text}")
        elif tag.name == "h2":
            lines.append(f"## {text}")
        elif tag.name == "h3":
            lines.append(f"### {text}")
        elif tag.name == "h4":
            lines.append(f"#### {text}")
        elif tag.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)
        lines.append("")

    # Lightweight de-dup to reduce repeated lines.
    deduped: list[str] = []
    prev = None
    for line in lines:
        if line == prev and line.strip():
            continue
        deduped.append(line)
        prev = line

    return "\n".join(deduped).strip() + "\n"


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def _is_noise_line(text: str) -> bool:
    # Ignore visual separator rows composed mostly of punctuation.
    if not text:
        return True
    punct = sum(1 for ch in text if ch in ".-_–—|")
    return punct / max(len(text), 1) > 0.6


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl HAW HIBS pages and store markdown corpus.")
    parser.add_argument("--output-dir", default="data/corpus", help="Directory for markdown files.")
    parser.add_argument("--max-pages", type=int, default=300, help="Maximum pages to crawl.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    count = crawl_hibs(output_dir=output_dir, max_pages=args.max_pages)
    print(f"Crawled and saved {count} HIBS pages into {output_dir}")


if __name__ == "__main__":
    main()
