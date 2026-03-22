from __future__ import annotations

from bs4 import BeautifulSoup, Tag

REMOVAL_SELECTORS = [
    "script",
    "style",
    "noscript",
    "svg",
    "form",
    "iframe",
    "header",
    "footer",
    "nav",
    ".cookie",
    ".cookies",
    ".cookie-banner",
    ".breadcrumb",
    ".breadcrumbs",
    ".menu",
    ".navbar",
    ".social",
    ".share",
    ".subscribe",
    ".newsletter",
    ".modal",
    ".popup",
]

TEXT_BLOCK_TAGS = ["h1", "h2", "h3", "h4", "p", "li", "th", "td"]


def clean_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "lxml")
    for selector in REMOVAL_SELECTORS:
        for node in soup.select(selector):
            node.decompose()
    return soup


def extract_visible_text(soup: BeautifulSoup) -> str:
    chunks: list[str] = []
    for tag_name in TEXT_BLOCK_TAGS:
        for node in soup.find_all(tag_name):
            text = _normalized_text(node)
            if text:
                chunks.append(text)
    deduped = _dedupe_preserving_order(chunks)
    return "\n".join(deduped)


def extract_tables(soup: BeautifulSoup) -> list[str]:
    tables: list[str] = []
    for table in soup.find_all("table"):
        rows: list[str] = []
        for row in table.find_all("tr"):
            cells = [_normalized_text(cell) for cell in row.find_all(["th", "td"])]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            tables.append("\n".join(rows))
    return tables


def _normalized_text(node: Tag) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output