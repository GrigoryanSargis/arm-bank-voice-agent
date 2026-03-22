from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

from arm_bank_voice_agent.config.banks import SeedPage
from arm_bank_voice_agent.models.schema import BankDocument, StructuredData
from arm_bank_voice_agent.scraping.cleaner import clean_html, extract_tables, extract_visible_text

PHONE_RE = re.compile(r"(?:\+?374\s*\(?\d+\)?[\d\s-]{5,}|\b0\d[\d\s-]{6,}\b)")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\b")


@dataclass(frozen=True)
class ExtractedPage:
    title: str
    visible_text: str
    tables: list[str]
    meta_description: str | None
    branch_records: list[str]
    address_candidates: list[str]
    phone_candidates: list[str]
    working_hours_candidates: list[str]


class HtmlPageExtractor:
    def parse(self, html: str) -> ExtractedPage:
        # IMPORTANT: keep raw soup for script extraction
        raw_soup = BeautifulSoup(html, "html.parser")
        branch_records = _extract_branch_records_from_scripts(raw_soup)

        # cleaned soup is only for visible DOM extraction
        soup = clean_html(html)

        title = _extract_title(soup)
        meta_description = _extract_meta_description(raw_soup) or _extract_meta_description(soup)

        visible_text = extract_visible_text(soup)
        if not visible_text.strip():
            visible_text = _fallback_extract_text(soup)

        visible_text = _filter_noise_text(visible_text)
        tables = _filter_noise_tables(extract_tables(soup))

        if _looks_weak_text(visible_text) and meta_description:
            visible_text = _merge_text_blocks(meta_description, visible_text)

        if not visible_text.strip() and tables:
            visible_text = "\n\n".join(tables)

        visible_text = _normalize_text(visible_text)

        lines = [line.strip() for line in visible_text.splitlines() if line.strip()]
        address_candidates = [line for line in lines if _looks_like_address(line)]
        phone_candidates = PHONE_RE.findall(visible_text)
        working_hours_candidates = TIME_RE.findall(visible_text)

        return ExtractedPage(
            title=title,
            visible_text=visible_text,
            tables=tables,
            meta_description=meta_description,
            branch_records=branch_records,
            address_candidates=address_candidates,
            phone_candidates=phone_candidates,
            working_hours_candidates=working_hours_candidates,
        )

    def to_document(self, *, bank_name: str, seed: SeedPage, html: str) -> BankDocument:
        page = self.parse(html)

        # ── Priority: try to extract structured financial data first ──────────
        financial_data = _extract_financial_tables(html)

        blocks: list[str] = []

        if page.meta_description and page.meta_description not in page.visible_text:
            blocks.append(page.meta_description)

        # Add structured financial data before general text — it's more valuable
        if financial_data:
            blocks.append(financial_data)

        if page.branch_records:
            blocks.append("\n".join(page.branch_records))

        if page.visible_text.strip():
            blocks.append(page.visible_text)

        if page.tables and not financial_data:
            blocks.extend(page.tables[:3])

        content = " ".join(" ".join(b.split()) for b in blocks if b.strip())

        if not content.strip():
            raise ValueError(f"No content extracted from {seed.url}")

        return BankDocument(
            bank=bank_name,
            topic=seed.topic,
            subtopic=seed.subtopic,
            language=seed.language,
            page_title=page.title or seed.url,
            source_url=seed.url,
            content=content,
            section_path=seed.section_path,
        )


def _extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)

    for tag in ["h1", "h2"]:
        node = soup.find(tag)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text

    return "untitled"


def _extract_meta_description(soup: BeautifulSoup) -> str | None:
    selectors = [
        ("meta", {"name": "description"}),
        ("meta", {"property": "og:description"}),
        ("meta", {"name": "twitter:description"}),
    ]
    for tag, attrs in selectors:
        node = soup.find(tag, attrs=attrs)
        if node and node.get("content"):
            value = " ".join(node.get("content", "").split()).strip()
            if value and not _is_noise_line(value):
                return value
    return None


def _fallback_extract_text(soup: BeautifulSoup) -> str:
    candidate_selectors = [
        "main", "article", "[role='main']", ".content", ".page-content",
        ".main-content", ".container", ".wrapper", ".inner",
        ".product-page", ".product-detail", ".service-page", "section", "body",
    ]
    candidates: list[str] = []
    for selector in candidate_selectors:
        for node in soup.select(selector):
            text = " ".join(node.get_text(" ", strip=True).split())
            if len(text) >= 40:
                candidates.append(text)
        if candidates:
            break
    if not candidates:
        return " ".join(soup.get_text(" ", strip=True).split())
    return max(candidates, key=len)


def _extract_branch_records_from_scripts(soup: BeautifulSoup) -> list[str]:
    records: list[str] = []
    seen: set[str] = set()

    for script in soup.find_all("script"):
        raw = script.string or script.get_text(" ", strip=False) or ""
        if not raw or len(raw) < 40:
            continue

        lowered = raw.lower()
        candidate_payloads: list[str] = []

        if "window.params" in raw:
            candidate_payloads.extend(_extract_json_candidates(raw))

        if any(token in lowered for token in [
            "branch", "atm", "address", "location",
            "հասցե", "մասնաճյուղ", "բանկոմատ",
            "latitude", "longitude", "branchcategories"
        ]):
            candidate_payloads.extend(_extract_json_candidates(raw))

        for payload in candidate_payloads:
            parsed = _safe_json_loads(payload)
            if parsed is None:
                continue

            extracted = _walk_for_branch_records(parsed)
            for item in extracted:
                line = _render_branch_record(item)
                key = " ".join(line.lower().split())
                if line and key not in seen:
                    seen.add(key)
                    records.append(line)

    return records[:200]


def _extract_json_candidates(raw: str) -> list[str]:
    candidates: list[str] = []
    stripped = raw.strip()

    if stripped.startswith("{") or stripped.startswith("["):
        candidates.append(stripped)

    patterns = [
        r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;",
        r"__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;",
        r"__NEXT_DATA__\s*=\s*(\{.*?\})\s*;",
        r"__NUXT__\s*=\s*(\{.*?\})\s*;",
        r"window\.params\s*=\s*(\{.*?\})\s*;\s*(?:window\.API_URI|$)",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, raw, flags=re.DOTALL):
            candidates.append(match.group(1))

    return candidates


def _safe_json_loads(payload: str) -> Any | None:
    try:
        return json.loads(payload)
    except Exception:
        return None


def _walk_for_branch_records(obj: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            keys = {str(k).lower() for k in node.keys()}

            looks_like_branch = (
                "address" in keys and
                ("latitude" in keys or "lat" in keys) and
                ("longitude" in keys or "lng" in keys) and
                ("name" in keys or "code" in keys or "id" in keys)
            )

            if looks_like_branch:
                dedupe_key = str(node.get("id") or node.get("identifier") or node.get("code") or id(node))
                if dedupe_key not in seen_ids:
                    seen_ids.add(dedupe_key)
                    results.append(node)

            for value in node.values():
                visit(value)

        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(obj)
    return results


def _render_branch_record(record: dict[str, Any]) -> str:
    def pick(*names: str) -> str | None:
        lowered = {str(k).lower(): v for k, v in record.items()}
        for name in names:
            if name.lower() in lowered and lowered[name.lower()] not in (None, "", [], {}):
                value = lowered[name.lower()]
                if isinstance(value, (dict, list)):
                    continue
                return " ".join(str(value).split()).strip()
        return None

    name = pick("name", "title", "branch", "branchName")
    address = pick("address", "location", "fullAddress")
    phone = pick("phone", "tel", "mobile")
    hours = _extract_schedule_text(record)
    lat = pick("lat", "latitude")
    lng = pick("lng", "longitude")

    pieces: list[str] = []

    if name:
        pieces.append(f"Մասնաճյուղ: {name}")
    if address:
        pieces.append(f"Հասցե: {address}")
    if phone:
        pieces.append(f"Հեռախոս: {phone}")
    if hours:
        pieces.append(f"Ժամեր: {hours}")
    if lat and lng and not address:
        pieces.append(f"Կոորդինատներ: {lat}, {lng}")

    line = " | ".join(pieces).strip()
    if not line or _is_noise_line(line):
        return ""
    return line


def _extract_schedule_text(record: dict[str, Any]) -> str | None:
    candidate_keys = ["Branchworkschedule-Branch", "branchMarkerInformation"]

    parts: list[str] = []
    for key in candidate_keys:
        items = record.get(key)
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            weekday = str(item.get("weekday", "")).strip().lower()
            frm = _extract_hhmm(item.get("from"))
            to = _extract_hhmm(item.get("to"))
            if not (weekday and frm and to):
                continue

            weekday_map = {
                "weekdays": "Երկ-Ուրբ",
                "saturday": "Շաբաթ",
                "sunday": "Կիրակի",
            }
            label = weekday_map.get(weekday, weekday)
            parts.append(f"{label} {frm}-{to}")

    if not parts:
        return None
    return "; ".join(parts)


def _extract_hhmm(value: Any) -> str | None:
    if value is None:
        return None
    m = re.search(r"(\d{2}):(\d{2})", str(value))
    if not m:
        return None
    return f"{m.group(1)}:{m.group(2)}"


def _filter_noise_tables(tables: list[str]) -> list[str]:
    cleaned_tables: list[str] = []
    for table in tables:
        kept_rows: list[str] = []
        for row in table.splitlines():
            row = " ".join(row.split()).strip()
            if not row or _is_noise_line(row):
                continue
            kept_rows.append(row)
        if kept_rows:
            cleaned_tables.append("\n".join(kept_rows))
    return cleaned_tables


def _filter_noise_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned: list[str] = []
    for line in lines:
        if _is_noise_line(line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _is_noise_line(line: str) -> bool:
    normalized = " ".join(line.split()).strip().lower()
    if not normalized:
        return True

    noise_fragments = [
        "տեղափոխել ձախ", "տեղափոխել աջ", "տեղափոխել վերև", "տեղափոխել ներքև",
        "մեծացնել", "փոքրացնել", "սկիզբ", "ավարտ",
        "թերթել վերև", "թերթել ներքև",
        "zoom in", "zoom out", "move left", "move right", "move up", "move down",
        "keyboard shortcuts", "faq թարմացված է", "updated at",
    ]
    if any(fragment in normalized for fragment in noise_fragments):
        return True
    if len(normalized) <= 2:
        return True
    if all(ch in "<>-+←→↑↓|/\\ " for ch in line):
        return True
    return False


def _looks_like_address(line: str) -> bool:
    lowered = line.lower()
    triggers = [
        "street", "st.", "ave", "avenue", "branch", "address",
        "ք.", "փողոց", "պողոտա", "հասցե", "մասնաճյուղ",
    ]
    return any(token in lowered for token in triggers)


def _looks_weak_text(text: str) -> bool:
    normalized = " ".join(text.split())
    if len(normalized) < 120:
        return True
    if normalized.lower().endswith("do you have questions?"):
        return True
    return False


def _merge_text_blocks(primary: str, secondary: str) -> str:
    primary = primary.strip()
    secondary = secondary.strip()
    if not primary:
        return secondary
    if not secondary:
        return primary
    if secondary in primary:
        return primary
    if primary in secondary:
        return secondary
    return f"{primary}\n{secondary}"


def _normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]
    return "\n".join(lines)

def _extract_financial_tables(html: str) -> str:
    """
    Extract rate tables and financial data specifically.
    Looks for tables with % signs, numbers, and financial keywords.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results: list[str] = []

    # Target elements likely to contain rate data
    FINANCIAL_SELECTORS = [
        "table",
        "[class*='rate']",
        "[class*='tariff']",
        "[class*='interest']",
        "[class*='loan-info']",
        "[class*='deposit-info']",
        "[class*='product']",
        "[class*='terms']",
        "[class*='condition']",
        "[class*='offer']",
    ]

    seen_texts: set[str] = set()

    for selector in FINANCIAL_SELECTORS:
        for el in soup.select(selector)[:5]:
            text = el.get_text(" ", strip=True)
            # Only keep if it looks like financial data
            if (
                len(text) > 40
                and any(ch.isdigit() for ch in text)
                and (
                    "%" in text
                    or any(k in text.lower() for k in [
                        "rate", "annual", "interest", "amount", "term",
                        "month", "percent", "min", "max",
                        # Armenian
                        "տוkoс", "tarife", "goomark", "amis",
                    ])
                )
            ):
                # Deduplicate
                key = text[:60]
                if key not in seen_texts:
                    seen_texts.add(key)
                    results.append(text[:600])

    return "\n\n".join(results)