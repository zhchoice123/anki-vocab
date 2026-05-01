from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """Strategy interface for text-to-speech providers."""

    @abstractmethod
    def generate(self, word: str) -> tuple[str, bytes]:
        """Generate audio for the given word/phrase.

        Args:
            word: The word or phrase to synthesise.

        Returns:
            (filename, audio_bytes): Filename for the Anki ``[sound:...]``
            reference, and raw WAV audio bytes.
        """
        ...
