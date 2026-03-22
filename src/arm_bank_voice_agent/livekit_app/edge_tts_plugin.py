import os
from livekit.plugins import elevenlabs


def EdgeTTS(
    *,
    voice_id: str = "Xb7hH8MSUJpSbSDYk0k2",  # example voice ID
    model: str = "eleven_turbo_v2_5",
    language: str | None = None,
    http_session=None,
    **kwargs,
):
    api_key = os.getenv("ELEVEN_API_KEY",'b31ed6d5eb20c9711272ff61ddcd31c36ae398d55d39dfb17bfac1635077f822')
    if not api_key:
        raise RuntimeError("Set ELEVEN_API_KEY")

    params = {
        "api_key": api_key,
        "voice_id": voice_id,
        "model": model,
        "http_session": http_session,
        **kwargs,
    }

    if language is not None:
        params["language"] = language

    return elevenlabs.TTS(**params)