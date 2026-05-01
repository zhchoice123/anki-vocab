class AnkiConnectionError(Exception):
    """Anki is not running or AnkiConnect is not installed."""

class AnkiError(Exception):
    """AnkiConnect returned an error response."""

class DuplicateCardError(AnkiError):
    """The note already exists in the deck (old format, no raw JSON)."""
    def __init__(self, word: str):
        self.word = word
        super().__init__(f"Duplicate card: {word}")

class LLMError(Exception):
    """LLM provider failed to return a valid response."""
