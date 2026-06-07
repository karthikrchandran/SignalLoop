"""Website crawling helpers for knowledge ingestion."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse

import httpx


@dataclass(frozen=True)
class CrawledPage:
    """One crawled page."""

    url: str
    title: str
    text: str


def _parse_html(url: str, html: str) -> tuple[str, str, list[str]]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        clean = " ".join(html.replace("<", " <").replace(">", "> ").split())
        return url, clean, []

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    text = " ".join(soup.get_text(" ").split())
    links = [link.get("href") for link in soup.find_all("a", href=True)]
    return title, text, [href for href in links if href]


def _same_origin(base_url: str, candidate: str) -> bool:
    base = urlparse(base_url)
    other = urlparse(candidate)
    return base.scheme == other.scheme and base.netloc == other.netloc


async def crawl_website(url: str, *, depth: int = 1, max_pages: int = 10) -> list[CrawledPage]:
    """Crawl a small same-origin website graph."""
    if depth < 1 or depth > 5:
        raise ValueError("crawl depth must be between 1 and 5")
    if max_pages < 1 or max_pages > 50:
        raise ValueError("max pages must be between 1 and 50")

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(url, 1)])
    pages: list[CrawledPage] = []

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        while queue and len(pages) < max_pages:
            current_url, current_depth = queue.popleft()
            current_url = urldefrag(current_url).url
            if current_url in visited:
                continue
            visited.add(current_url)
            response = await client.get(current_url)
            response.raise_for_status()
            title, text, links = _parse_html(current_url, response.text)
            pages.append(CrawledPage(url=current_url, title=title, text=text))
            if current_depth >= depth:
                continue
            for href in links:
                next_url = urldefrag(urljoin(current_url, href)).url
                if next_url not in visited and _same_origin(url, next_url):
                    queue.append((next_url, current_depth + 1))

    return pages
