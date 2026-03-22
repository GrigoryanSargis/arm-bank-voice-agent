from __future__ import annotations

import json
from pathlib import Path

import httpx

from arm_bank_voice_agent.config.banks import BANKS, BankConfig
from arm_bank_voice_agent.models.schema import BankDocument
from arm_bank_voice_agent.scraping.browser_client import fetch_with_browser
from arm_bank_voice_agent.scraping.extractor import HtmlPageExtractor
from arm_bank_voice_agent.scraping.http_client import build_http_client


class ScrapePipeline:
    def __init__(self) -> None:
        self.extractor = HtmlPageExtractor()

    def scrape_bank(self, bank_key: str) -> list[BankDocument]:
        if bank_key not in BANKS:
            raise KeyError(f"unknown bank key: {bank_key}")
        config = BANKS[bank_key]
        return self._scrape_config(config)

    def scrape_all(self) -> list[BankDocument]:
        documents: list[BankDocument] = []
        for bank_key in BANKS:
            documents.extend(self.scrape_bank(bank_key))
        return documents

    def _scrape_config(self, config: BankConfig) -> list[BankDocument]:
        documents: list[BankDocument] = []

        with build_http_client() as client:
            for seed in config.seed_pages:
                print(f"[INFO] Fetching: {config.name} | {seed.topic} | {seed.url}")

                html = None
                used_browser = False

                try:
                    response = client.get(seed.url)
                    response.raise_for_status()
                    html = response.text
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status == 403:
                        print(f"[INFO] HTTP 403, retrying in browser mode: {seed.url}")
                        try:
                            html = fetch_with_browser(
                                seed.url,
                                wait_for_selector=getattr(seed, "wait_for_selector", None),
                            )
                            used_browser = True
                        except Exception as browser_exc:
                            print(f"[WARN] Browser fallback failed: {seed.url}")
                            print(f"[WARN] Reason: {browser_exc}")
                            continue
                    else:
                        print(f"[WARN] Skipping: {config.name} | {seed.topic} | {seed.url}")
                        print(f"[WARN] Reason: {exc}")
                        continue
                except Exception as exc:
                    print(f"[WARN] Skipping: {config.name} | {seed.topic} | {seed.url}")
                    print(f"[WARN] Reason: {exc}")
                    continue

                try:
                    document = self.extractor.to_document(
                        bank_name=config.name,
                        seed=seed,
                        html=html,
                    )

                    if _document_looks_weak(document):
                        raise ValueError("Weak extraction result, retrying browser mode")

                    documents.append(document)
                    mode = "browser" if used_browser else "http"
                    print(f"[OK] Extracted ({mode}): {config.name} | {seed.topic} | {seed.url}")
                    continue

                except Exception as exc:
                    if used_browser:
                        print(f"[WARN] Skipping: {config.name} | {seed.topic} | {seed.url}")
                        print(f"[WARN] Reason: {exc}")
                        continue

                    print(f"[INFO] Extraction failed in initial mode, retrying browser mode: {seed.url}")
                    print(f"[INFO] First extraction reason: {exc}")

                try:
                    browser_html = fetch_with_browser(seed.url)
                    document = self.extractor.to_document(
                        bank_name=config.name,
                        seed=seed,
                        html=browser_html,
                    )
                    documents.append(document)
                    print(f"[OK] Extracted (browser): {config.name} | {seed.topic} | {seed.url}")
                    continue
                except Exception as browser_exc:
                    print(f"[WARN] Skipping: {config.name} | {seed.topic} | {seed.url}")
                    print(f"[WARN] Reason: {browser_exc}")
                    continue

        return documents


def export_documents(documents: list[BankDocument], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [doc.model_dump(mode="json") for doc in documents]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _document_looks_weak(document: BankDocument) -> bool:
    content = " ".join(document.content.split())
    title = " ".join(document.page_title.split())

    if len(content) < 120:
        return True

    if content == title:
        return True

    if content.startswith(title) and len(content) < len(title) + 40:
        return True

    return False
