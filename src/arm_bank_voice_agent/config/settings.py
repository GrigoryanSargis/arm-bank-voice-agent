from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # ── LiveKit (self-hosted, open-source) ────────────────────────────────────
    livekit_url: str = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    livekit_api_key: str = os.getenv("LIVEKIT_API_KEY", "devkey")
    livekit_api_secret: str = os.getenv("LIVEKIT_API_SECRET", "devsecret")

    # ── Groq API (free tier) — STT + LLM ─────────────────────────────────────
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")

    # Groq Whisper — best Armenian STT available for free
    groq_stt_model: str = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
    groq_stt_language: str = os.getenv("GROQ_STT_LANGUAGE", "hy")  # Armenian

    # Groq LLM — Llama 3.3 70B handles Armenian well and has 128k context
    groq_llm_model: str = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
    groq_llm_temperature: float = float(os.getenv("GROQ_LLM_TEMPERATURE", "0.1"))

    # ── TTS — Microsoft Edge Neural TTS via edge-tts (100% free) ─────────────
    # hy-AM-AnahitNeural = native Armenian female voice
    edge_tts_voice: str = os.getenv("EDGE_TTS_VOICE", "hy-AM-AnahitNeural")
    edge_tts_rate: str = os.getenv("EDGE_TTS_RATE", "+0%")

    # ── Knowledge base ────────────────────────────────────────────────────────
    bank_chunks_path: Path = Path(
        os.getenv("BANK_CHUNKS_PATH", "data/processed/bank_chunks.json")
    )
    # Maximum characters of KB text to embed in the system prompt.
    # Llama-3.3-70b has 128k token context; 200k chars ≈ 50k tokens — safe.
    kb_max_chars: int = int(os.getenv("KB_MAX_CHARS", "200000"))

    log_level: str = os.getenv("LOG_LEVEL", "INFO")


def get_settings() -> Settings:
    return Settings()
