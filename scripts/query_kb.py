#!/usr/bin/env python3
"""
Test the query service locally (no voice, no LiveKit required).

Usage:
    python scripts/query_kb.py "What are the deposit rates at Ameriabank?"
    python scripts/query_kb.py "Ո՞ր մասնաճյուղն է ամենամոտ Կենտրոնին"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from arm_bank_voice_agent.agent.query_service import KBQueryService


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/query_kb.py '<your question>'")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    print(f"\nQuery: {query}\n")

    service = KBQueryService()
    result = service.answer_query(query)

    print(f"In scope:       {result.in_scope}")
    print(f"Detected topic: {result.detected_topic}")
    print(f"\nAnswer:\n{result.answer_text}")

    if result.sources:
        print(f"\nSources ({len(result.sources)}):")
        for s in result.sources[:5]:
            print(f"  [{s.bank}] {s.topic} — {s.page_title}")
            print(f"    {s.source_url}")


if __name__ == "__main__":
    main()
