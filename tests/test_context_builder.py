"""
tests/test_context_builder.py
==============================
Tests for context_builder.py — no external API calls required.
"""
from __future__ import annotations

import pytest

from arm_bank_voice_agent.agent.context_builder import (
    _format_knowledge_base,
    build_system_prompt,
)
from arm_bank_voice_agent.models.chunk import DocumentChunk


def _make_chunk(bank: str, topic: str, text: str, idx: int = 0) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=f"{bank}-{topic}-{idx}",
        bank=bank,
        topic=topic,  # type: ignore[arg-type]
        language="hy",
        source_url=f"https://example.com/{bank}/{topic}",  # type: ignore[arg-type]
        page_title=f"{bank} {topic} page",
        chunk_index=idx,
        text=text,
    )


class TestFormatKnowledgeBase:
    def test_all_banks_present(self):
        chunks = [
            _make_chunk("Ameriabank", "credit", "Consumer loans info"),
            _make_chunk("Ardshinbank", "deposit", "Deposit rates info"),
            _make_chunk("Mellat Bank", "branch", "Branch addresses"),
        ]
        kb = _format_knowledge_base(chunks, max_chars=100_000)
        assert "Ameriabank" in kb
        assert "Ardshinbank" in kb
        assert "Mellat Bank" in kb

    def test_all_topics_labelled(self):
        chunks = [
            _make_chunk("Ameriabank", "credit", "credit text"),
            _make_chunk("Ameriabank", "deposit", "deposit text"),
            _make_chunk("Ameriabank", "branch", "branch text"),
        ]
        kb = _format_knowledge_base(chunks, max_chars=100_000)
        assert "Loans" in kb or "Credit" in kb
        assert "Deposit" in kb
        assert "Branch" in kb or "ATM" in kb

    def test_truncation_applied(self):
        # Create a chunk with very long text
        long_text = "A" * 50_000
        chunks = [_make_chunk("Ameriabank", "credit", long_text)]
        kb = _format_knowledge_base(chunks, max_chars=1_000)
        assert len(kb) <= 1_200  # some slack for truncation suffix
        assert "truncated" in kb.lower()

    def test_empty_chunks_returns_something(self):
        kb = _format_knowledge_base([], max_chars=100_000)
        assert isinstance(kb, str)

    def test_page_title_in_output(self):
        chunk = _make_chunk("Inecobank", "credit", "Rate is 12%")
        chunk_with_title = DocumentChunk(
            chunk_id="x",
            bank="Inecobank",
            topic="credit",
            language="en",
            source_url="https://inecobank.am/loans",  # type: ignore[arg-type]
            page_title="Consumer Loans at Inecobank",
            chunk_index=0,
            text="Rate is 12%",
        )
        kb = _format_knowledge_base([chunk_with_title], max_chars=100_000)
        assert "Consumer Loans at Inecobank" in kb


class TestBuildSystemPrompt:
    def test_system_prompt_contains_scope_rules(self):
        chunks = [_make_chunk("Ameriabank", "credit", "some text")]
        prompt = build_system_prompt(chunks)
        # Scope rules must be present
        assert "SCOPE" in prompt or "scope" in prompt or "ONLY" in prompt

    def test_system_prompt_contains_kb_data(self):
        chunks = [_make_chunk("Mellat Bank", "deposit", "Special deposit terms here")]
        prompt = build_system_prompt(chunks)
        assert "Mellat Bank" in prompt
        assert "Special deposit terms here" in prompt

    def test_system_prompt_is_non_empty(self):
        prompt = build_system_prompt([])
        assert len(prompt) > 200
