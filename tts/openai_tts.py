import hashlib

import openai

from tts.base import TTSProvider
from tts.utils import pcm_to_padded_wav


class OpenAITTS(TTSProvider):
    """Generate pronunciation audio via OpenAI TTS (gpt-4o-mini-tts)."""

    def __init__(self, voice: str = "cedar", speed: float = 1.0):
        self._voice = voice
        self._speed = speed
        self._client: openai.OpenAI | None = None

    @property
    def _api(self) -> openai.OpenAI:
        if self._client is None:
            self._client = openai.OpenAI(max_retries=3)
        return self._client

    def generate(self, word: str) -> tuple[str, bytes]:
        filename = f"vocab_{hashlib.md5(word.lower().encode()).hexdigest()}.wav"
        response = self._api.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=self._voice,
            input=word,
            instructions="Pronounce this vocabulary word clearly and naturally, with careful articulation.",
            response_format="pcm",
            speed=self._speed,
        )
        audio_bytes = pcm_to_padded_wav(response.content)
        return filename, audio_bytes
