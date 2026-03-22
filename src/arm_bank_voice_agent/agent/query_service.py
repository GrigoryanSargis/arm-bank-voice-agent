from __future__ import annotations

"""
query_service.py - Scope gate + Groq LLM full-context pipeline.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from arm_bank_voice_agent.agent.context_builder import (
    build_system_prompt,
    load_chunks_from_json,
)
from arm_bank_voice_agent.config.settings import get_settings
from arm_bank_voice_agent.llm.groq_client import GroqLLMClient
from arm_bank_voice_agent.models.chunk import DocumentChunk
from arm_bank_voice_agent.agent.guardrails import QueryGuard, out_of_scope_message
import re
_guard = QueryGuard()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceRef:
    bank: str
    topic: str
    page_title: str
    source_url: str


@dataclass(frozen=True)
class AnswerResult:
    answer_text: str
    sources: list[SourceRef]
    in_scope: bool
    detected_topic: str | None


class KBQueryService:
    def __init__(self, chunks_path=None):
        settings = get_settings()
        path = Path(chunks_path) if chunks_path else settings.bank_chunks_path
        self._chunks = load_chunks_from_json(path)
        self._llm = GroqLLMClient()

        # Pre-build one focused prompt per topic at startup — not per query
        self._prompts: dict[str, str] = {}
        for topic in ("credit", "deposit", "branch"):
            topic_chunks = [c for c in self._chunks if c.topic == topic]
            self._prompts[topic] = build_system_prompt(
                topic_chunks, max_chars=get_settings().kb_max_chars
            )
        # Fallback prompt with all chunks
        self._prompts["unknown_armenian"] = build_system_prompt(
            self._chunks, max_chars=get_settings().kb_max_chars
        )
        logger.info(
            "KBQueryService ready — %d chunks, model=%s",
            len(self._chunks), self._llm.model,
        )

    def answer_query(self, query: str, language: str | None = None) -> AnswerResult:
        decision = _guard.classify(query)

        if decision.should_refuse:
            logger.info("Guardrail blocked: %r", query)
            return AnswerResult(
                answer_text=out_of_scope_message(query),
                sources=[],
                in_scope=False,
                detected_topic=None,
            )

        logger.info("In-scope (topic=%s bank=%s): %r",
                    decision.topic, decision.bank, query)

        # Use pre-built focused prompt — zero rebuild cost per query
        system_prompt = self._prompts.get(decision.topic, self._prompts["unknown_armenian"])

        answer_text = self._llm.complete(
            system_prompt=system_prompt,
            user_prompt=query,
        )

        return AnswerResult(
            answer_text=answer_text.strip(),
            sources=_collect_sources(self._chunks, decision.topic),
            in_scope=True,
            detected_topic=decision.topic,
        )


# ── Scope detection ───────────────────────────────────────────────────────────

def _has_armenian(text: str) -> bool:
    return any("\u0531" <= ch <= "\u058F" for ch in text)

_CREDIT_EN  = {"credit","loan","loans","consumer","borrow","mortgage","overdraft","lending","installment"}
_DEPOSIT_EN = {"deposit","deposits","saving","savings"}
_BRANCH_EN  = {"branch","branches","atm","atms","address","addresses","location","locations","map","office","offices","network"}

# Armenian keywords as raw literals (Python 3 source is UTF-8)

_CREDIT_HY  = ['վարկ', 'վարկեր']
_DEPOSIT_HY = ['ավանդ', 'ավանդներ']
_BRANCH_HY  = ['մասնաճյուգ', 'բանկոմատ', 'հասցե']

COMMON_TYPOS = {
    "luan": "loan",
    "lon": "loan", 
    "depost": "deposit",
    "branh": "branch",
}


# Greeting (English — edge-tts handles it correctly)
GREETING_HY = 'Hello. I am your Armenian bank support assistant. I can answer questions about loans, deposits, and branch or ATM locations. How can I help you?'

# Refusal message in Armenian
REFUSAL_HY ="Ներողություն, կարող եմ պատասխանել միայն վարկերի, ավանդների և մասնաճյուղերի վերաբերյալ հարցերին:"


def detect_supported_topic(query: str) -> str | None:
    q_lower = query.lower()
    words = set(re.sub(r"[^\w\s]", "", q_lower).split())
    for w in words:
        if w in _CREDIT_EN:  return "credit"
        if w in _DEPOSIT_EN: return "deposit"
        if w in _BRANCH_EN:  return "branch"
    if "consumer loan" in q_lower or "personal loan" in q_lower: return "credit"
    if "term deposit" in q_lower or "time deposit" in q_lower:   return "deposit"
    if "service network" in q_lower or "near me" in q_lower:     return "branch"
    for kw in _CREDIT_HY:
        if kw in query: return "credit"
    for kw in _DEPOSIT_HY:
        if kw in query: return "deposit"
    for kw in _BRANCH_HY:
        if kw in query: return "branch"
    if _has_armenian(query) and len(query.strip()) >= 5:
        return "unknown_armenian"
    return None


def out_of_scope_message(query: str) -> str:
    if _has_armenian(query):
        return REFUSAL_HY
    return (
        "I'm sorry, I can only help with questions about loans, deposits, "
        "and branch or ATM locations based on official bank sources."
    )


def _collect_sources(chunks: list[DocumentChunk], topic: str) -> list[SourceRef]:
    seen: set[str] = set()
    sources: list[SourceRef] = []
    for chunk in chunks:
        if topic not in ("unknown_armenian",) and chunk.topic != topic:
            continue
        key = f"{chunk.bank}|{chunk.topic}|{chunk.source_url}"
        if key in seen:
            continue
        seen.add(key)
        sources.append(SourceRef(
            bank=chunk.bank,
            topic=chunk.topic,
            page_title=chunk.page_title,
            source_url=str(chunk.source_url),
        ))
    return sources
