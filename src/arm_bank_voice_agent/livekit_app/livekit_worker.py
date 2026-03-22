from __future__ import annotations

"""
livekit_worker.py
=================
LiveKit open-source voice agent — Armenian bank customer support.

Free voice pipeline
───────────────────────────────────────────────────────────────────
  User mic
    │
    ▼
  Silero VAD
    │
    ▼
  Groq Whisper STT ─────────── whisper-large-v3, language hint "hy"
    │
    ▼
  on_user_turn_completed hook
    ├─ Scope guard
    └─ KBQueryService ───────── calls Groq Llama with full KB
         │
         ▼
  edge-tts TTS ─────────────── en-US-AriaNeural
    │
    ▼
  LiveKit room
───────────────────────────────────────────────────────────────────
"""

import logging
import os
import re
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
)
from livekit.plugins import groq as lk_groq
from livekit.plugins import silero

from arm_bank_voice_agent.config.settings import get_settings
# from arm_bank_voice_agent.livekit_app.edge_tts_adapter import EdgeTTS

from arm_bank_voice_agent.livekit_app.edge_tts_plugin import EdgeTTS
from arm_bank_voice_agent.agent.query_service import KBQueryService
from arm_bank_voice_agent.agent.guardrails import QueryGuard, out_of_scope_message

_guard = QueryGuard()
import asyncio
from typing import AsyncIterable
from livekit import rtc
from livekit.agents import ModelSettings, StopResponse


load_dotenv()

logger = logging.getLogger("arm-bank-livekit-worker")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)

GREETING = "Բարև ձեզ։ Ինչպե՞ս կարող եմ օգնել։"

MINIMAL_INSTRUCTIONS = (
    "Դու հայկական բանկի ձայնային օգնական ես։ "
    "Պատասխանիր հայերեն, եթե օգտատերը խոսում է հայերեն, և անգլերեն, եթե օգտատերը խոսում է անգլերեն։ "
    "Պատասխանիր միայն վարկերի, ավանդների և մասնաճյուղերի մասին հարցերին։ "
    "Պահիր պատասխանները կարճ և հստակ։"
)



def prewarm(proc: JobProcess) -> None:
    settings = get_settings()
    logger.info("Prewarm: loading VAD...")
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("Prewarm: loading knowledge base...")
    proc.userdata["query_service"] = KBQueryService(settings.bank_chunks_path)
    logger.info("Prewarm complete.")


class ArmenianBankAgent(Agent):
    def __init__(self, query_service: KBQueryService) -> None:
        super().__init__(instructions=MINIMAL_INSTRUCTIONS)
        self._query_service = query_service

    async def on_enter(self) -> None:
        await self.session.say(GREETING)

    async def tts_node(
        self,
        text: AsyncIterable[str],
        model_settings: ModelSettings,
    ) -> AsyncIterable[rtc.AudioFrame]:
        # Force the same non-streamed synth path that worked in your standalone test
        buf = []
        async for chunk in text:
            if chunk:
                buf.append(chunk)

        full_text = "".join(buf).strip()
        if not full_text:
            return

        tts_engine = self.session.tts
        if tts_engine is None:
            return

        async for ev in tts_engine.synthesize(full_text):
            yield ev.frame

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        user_text = (getattr(new_message, "text_content", None) or "").strip()
        if not user_text:
            raise StopResponse()

        logger.info("User said: %r", user_text)

        decision = _guard.classify(user_text)
        if decision.should_refuse:
            await self.session.say(out_of_scope_message(user_text))
            raise StopResponse()

        try:
            result = await asyncio.to_thread(self._query_service.answer_query, user_text)
            answer = (result.answer_text or "").strip()

            if not answer:
                answer = "Ներողություն, հստակ պատասխան չգտա։ Խնդրում եմ վերաձևակերպել հարցը։"

            if len(answer) > 400:
                cut = answer[:400]
                for sep in ("։", ".", "!", "?", ":"):
                    idx = cut.rfind(sep)
                    if idx > 150:
                        cut = cut[: idx + 1]
                        break
                answer = cut

            await self.session.say(answer)
            raise StopResponse()            

        except Exception:
            logger.exception("KB/LLM error while answering user turn")
            await self.session.say("Ներողություն, տեխնիկական խնդիր առաջացավ։ Խնդրում եմ կրկնել հարցը։")

        raise StopResponse()


async def entrypoint(ctx: JobContext) -> None:
    logger.info("Session starting - room: %s", ctx.room.name)

    settings = get_settings()
    query_service: KBQueryService = ctx.proc.userdata["query_service"]
    vad = ctx.proc.userdata["vad"]

    session = AgentSession(
    stt=lk_groq.STT(
        model=settings.groq_stt_model,
        language=settings.groq_stt_language,
    ),
    tts=EdgeTTS(
        model="eleven_turbo_v2_5",
        language="hy",
    ),
    vad=vad,
)

    await session.start(
        room=ctx.room,
        agent=ArmenianBankAgent(query_service),
        room_input_options=RoomInputOptions(),
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )