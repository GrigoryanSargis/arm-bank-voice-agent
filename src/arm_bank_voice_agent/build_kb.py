#!/usr/bin/env python3
"""
build_kb.py — Build the knowledge base from raw scraped documents.

This module:
  1. Loads raw documents from data/raw/bank_documents.json
  2. Chunks each document into smaller pieces
  3. Saves DocumentChunk objects to data/processed/bank_chunks.json

The output is the file that the LiveKit agent loads at startup and
injects into the LLM system prompt on every request.

Usage:
    python -m arm_bank_voice_agent.build_kb
    # or
    python scripts/build_kb.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from arm_bank_voice_agent.models.schema import BankDocument
from arm_bank_voice_agent.processing.chunker import DocumentChunker
from arm_bank_voice_agent.retrieval.store import ChunkStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

RAW_PATH = Path("data/raw/bank_documents.json")
PROCESSED_PATH = Path("data/processed/bank_chunks.json")


def build_kb(
    raw_path: Path = RAW_PATH,
    processed_path: Path = PROCESSED_PATH,
) -> int:
    logger.info("Loading raw documents from %s", raw_path)
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    documents = [BankDocument.model_validate(item) for item in raw]
    logger.info("Loaded %d raw documents", len(documents))

    chunker = DocumentChunker()
    all_chunks = []
    for doc in documents:
        # FIX: correct method name is chunk_document (not chunk)
        chunks = chunker.chunk_document(doc)
        all_chunks.extend(chunks)
        logger.info("  %s | %s | %d chunks", doc.bank, doc.topic, len(chunks))

    store = ChunkStore()
    store.save(all_chunks, processed_path)
    logger.info("Saved %d chunks → %s", len(all_chunks), processed_path)
    return len(all_chunks)


if __name__ == "__main__":
    n = build_kb()
    print(f"\nKnowledge base ready: {n} chunks saved to {PROCESSED_PATH}")
    sys.exit(0)
