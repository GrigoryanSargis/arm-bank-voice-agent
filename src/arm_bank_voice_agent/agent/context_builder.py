from __future__ import annotations

"""
context_builder.py
==================
Loads the scraped bank knowledge base and formats it as a single structured
plain-text string that is injected directly into the LLM system prompt on
every request.

Architectural Decision — Full-Context Retrieval
------------------------------------------------
This project deliberately does NOT use a vector database or embeddings.
Instead, the entire KB (~30–50k tokens) is placed in the system prompt on
every call.  This approach was chosen because:

  1. It is simpler to debug and iterate on (no indexing pipeline to maintain).
  2. Llama-3.3-70b-versatile / Groq has a 128k token context window — the
     full KB fits comfortably.
  3. The LLM can reason across all banks simultaneously, enabling natural
     comparison questions ("Which bank has the lowest loan rate?").
  4. No additional API cost for embedding/retrieval — everything runs free.
"""

import json
import logging
from pathlib import Path

from arm_bank_voice_agent.models.chunk import DocumentChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a voice-based customer support assistant for Armenian banks.
You are a voice-based customer support assistant grounded exclusively in
official Armenian bank data.

══════════════════════════════════════════════════════
STRICT SCOPE — ABSOLUTE RULES YOU MUST NEVER VIOLATE
══════════════════════════════════════════════════════
1. You answer ONLY questions about three topics:
     • Loans & Credits     (Armenian: վարկ, վարկեր, ապառիկ)
     • Deposits & Savings  (Armenian: ավանդ, ավանդներ)
     • Branch & ATM locations (Armenian: masnahjugh, bankomat, hastsye)

2. For ANY question outside these three topics, you MUST refuse with the
   exact phrase below and nothing else:
     — Armenian: «Ներողություն, կարող եմ պատասխանել միայն վարկերի, ավանդների և մասնաճյուղերի վերաբերյալ հարցերին:»
     — English: "I'm sorry, I can only help with loans, deposits, and
       branch or ATM locations."

3. Base EVERY answer SOLELY on the BANK KNOWLEDGE BASE section below.
   NEVER invent, estimate, or extrapolate interest rates, loan terms,
   deposit terms, addresses, phone numbers, or working hours.
   If the data is not in the knowledge base, say so honestly.

4. ALWAYS respond in Armenian regardless of what language the user speaks.
   The voice system only supports Armenian. Understand Armenian input but
   always reply in Armenian.

5. Voice-friendly format: Maximum 2-3 short sentences. No bullet points, 
   no tables, no abbreviations. Speak naturally as if talking to someone.
   NEVER exceed 3 sentences in your response.


6. Always name the bank when citing information so the user knows the source.

══════════════════════════════════════════════════════
BANK KNOWLEDGE BASE
══════════════════════════════════════════════════════
{bank_knowledge_base}
══════════════════════════════════════════════════════
END OF KNOWLEDGE BASE — Do not use any knowledge beyond this section.
══════════════════════════════════════════════════════
"""


def build_system_prompt(chunks: list[DocumentChunk], max_chars: int = 200_000) -> str:
    """Build the complete system prompt with the full KB embedded."""
    kb_text = _format_knowledge_base(chunks, max_chars=max_chars)
    prompt = _SYSTEM_PROMPT.format(bank_knowledge_base=kb_text)
    logger.info(
        "System prompt built: %d chunks → %d KB chars → %d total prompt chars",
        len(chunks),
        len(kb_text),
        len(prompt),
    )
    return prompt


def load_chunks_from_json(path: str | Path) -> list[DocumentChunk]:
    """Load the processed chunk JSON produced by build_kb.py."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Knowledge base not found at: {p}\n"
            "Build it first:  python -m arm_bank_voice_agent.build_kb"
        )
    raw = json.loads(p.read_text(encoding="utf-8"))
    chunks = [DocumentChunk.model_validate(item) for item in raw]
    logger.info("Loaded %d chunks from %s", len(chunks), p)
    return chunks


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_knowledge_base(chunks: list[DocumentChunk], max_chars: int) -> str:
    """
    Group chunks by bank → topic and render as a readable plain-text document.
    The structure helps the LLM locate information quickly without any
    retrieval step.
    """
    # Group: bank_name → topic → [chunks]
    grouped: dict[str, dict[str, list[DocumentChunk]]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.bank, {}).setdefault(chunk.topic, []).append(chunk)

    sections: list[str] = []

    for bank_name in sorted(grouped):
        bank_parts: list[str] = []

        for topic in ("credit", "deposit", "branch"):
            topic_chunks = grouped[bank_name].get(topic, [])
            if not topic_chunks:
                continue

            label = _topic_label(topic)
            entries: list[str] = []

            # ── KEY CHANGE: cap at 3 chunks per bank per topic, 400 chars each ──
            for c in topic_chunks[:3]:
                text = c.text.strip()[:400]   # trim each chunk
                if not text or len(text) < 40:
                    continue
                entry = f"[{c.page_title}]\n{text}"
                entries.append(entry)

            if entries:
                bank_parts.append(f"### {label}\n\n" + "\n\n".join(entries))

        if bank_parts:
            sections.append(f"## {bank_name}\n\n" + "\n\n".join(bank_parts))

    full_text = "\n\n" + "\n\n".join(sections) + "\n\n"

    if len(full_text) > max_chars:
        logger.warning(
            "KB text %d chars exceeds max_chars=%d — truncating.",
            len(full_text),
            max_chars,
        )
        full_text = full_text[:max_chars] + "\n\n[… content truncated for context limit …]"

    return full_text


def _topic_label(topic: str) -> str:
    return {
        "credit":  "Loans & Credits (Varker / վarкер)",
        "deposit": "Deposits & Savings (Avander / Avandner)",
        "branch":  "Branches & ATMs (Masnahjugher / Bankomater)",
    }.get(topic, topic.title())
