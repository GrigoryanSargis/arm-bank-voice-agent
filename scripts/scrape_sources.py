#!/usr/bin/env python3
"""
scrape_sources.py — Scrape Armenian bank websites for credits, deposits, branch data.

Usage:
    python scripts/scrape_sources.py                    # all 4 banks
    python scripts/scrape_sources.py --bank mellat_bank # single bank
    python scripts/scrape_sources.py --output data/raw/bank_documents.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arm_bank_voice_agent.scraping.pipeline import ScrapePipeline, export_documents

VALID_BANKS = ["all", "evocabank", "ardshinbank", "inecobank", "mellat_bank"]


def main() -> None:
    p = argparse.ArgumentParser(description="Scrape Armenian bank websites")
    p.add_argument("--bank", default="all", choices=VALID_BANKS)
    p.add_argument("--output", default="data/raw/bank_documents.json")
    args = p.parse_args()

    pipeline = ScrapePipeline()
    docs = pipeline.scrape_all() if args.bank == "all" else pipeline.scrape_bank(args.bank)
    path = export_documents(docs, Path(args.output))
    print(f"\n✓ Scraped {len(docs)} documents → {path}")


if __name__ == "__main__":
    main()
