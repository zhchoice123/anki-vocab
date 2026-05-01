import io
import wave

_LEADING_SILENCE_MS = 120
_TRAILING_SILENCE_MS = 300
_PCM_SAMPLE_RATE = 24_000
_PCM_CHANNELS = 1
_PCM_SAMPLE_WIDTH = 2


def pcm_to_padded_wav(
    pcm_bytes: bytes,
    *,
    leading_ms: int = _LEADING_SILENCE_MS,
    trailing_ms: int = _TRAILING_SILENCE_MS,
    sample_rate: int = _PCM_SAMPLE_RATE,
    channels: int = _PCM_CHANNELS,
    sample_width: int = _PCM_SAMPLE_WIDTH,
) -> bytes:
    """Wrap raw PCM bytes in a WAV container with leading/trailing silence."""
    frame_width = channels * sample_width
    leading_frames = int(sample_rate * leading_ms / 1000)
    trailing_frames = int(sample_rate * trailing_ms / 1000)
    leading_silence = b"\0" * leading_frames * frame_width
    trailing_silence = b"\0" * trailing_frames * frame_width

    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(sample_width)
        target.setframerate(sample_rate)
        target.writeframes(leading_silence)
        target.writeframes(pcm_bytes)
        target.writeframes(trailing_silence)
    return output.getvalue()
