from __future__ import annotations

"""
groq_client.py
==============
Thin wrapper around the Groq Python SDK for LLM completions.

Used by KBQueryService to answer in-scope queries with the full bank
knowledge base injected into the system prompt (full-context strategy —
no vector DB, no embeddings).

Model: llama-3.3-70b-versatile
  - Free on Groq's tier (rate limit: 6000 RPM / 200k TPM per model)
  - 128k token context window — fits entire scraped bank KB comfortably
  - Strong multilingual support including Armenian (Unicode aware)
  - Much faster than self-hosted alternatives on CPU hardware
"""

import logging

from groq import Groq

from arm_bank_voice_agent.config.settings import get_settings

logger = logging.getLogger(__name__)


class GroqLLMClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.groq_llm_model
        self.temperature = settings.groq_llm_temperature
        self._client = Groq(api_key=settings.groq_api_key)

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> str:
        """
        Call the Groq LLM with the bank knowledge base in the system prompt.
        The full-context approach means every call carries the entire KB —
        no retrieval step, maximum context availability for the model.
        """
        t = temperature if temperature is not None else self.temperature
        logger.debug(
            "LLM call: model=%s, system_len=%d, user_len=%d",
            self.model, len(system_prompt), len(user_prompt),
        )
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=t,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""
