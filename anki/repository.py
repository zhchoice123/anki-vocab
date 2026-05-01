import logging

import requests

from anki.formatter import CardFormatter
from config import Config
from exceptions import AnkiConnectionError, AnkiError, DuplicateCardError
from models import WordCard

logger = logging.getLogger(__name__)


class AnkiRepository:
    """Repository Pattern — all Anki operations in one place."""

    def __init__(self, config: Config):
        self._config = config
        self._formatter = CardFormatter()

    # ─────────────────────────────────────────────────────────────── public

    def find(self, word: str) -> WordCard | None:
        # Single OR query covers both old Basic model (front field) and new model (英语单词 field)
        ids = self._request(
            "findNotes",
            query=f'deck:"{self._config.anki_deck}" (front:"{word}" OR 英语单词:"{word}")',
        )
        if not ids:
            return None
        notes = self._request("notesInfo", notes=ids)
        if not notes:
            return None
        return self._formatter.from_fields(word, notes[0]["fields"])

    def recent_words(self, limit: int = 10, exclude: set[str] | None = None) -> list[WordCard]:
        """Return recent round-trippable cards from the configured Anki deck."""
        exclude_normalized = {w.lower() for w in (exclude or set())}
        ids = self._request("findNotes", query=f'deck:"{self._config.anki_deck}"')
        if not ids:
            return []

        result: list[WordCard] = []
        for note_id in reversed(ids):
            if len(result) >= limit:
                break
            notes = self._request("notesInfo", notes=[note_id])
            if not notes:
                continue
            fields = notes[0]["fields"]
            word = fields.get("英语单词", {}).get("value") or fields.get("Front", {}).get("value", "")
            if not word or word.lower() in exclude_normalized:
                continue
            card = self._formatter.from_fields(word, fields)
            if card is not None:
                result.append(card)
                exclude_normalized.add(card.word.lower())
        return result

    def save(self, card: WordCard) -> int:
        self._ensure_deck()
        try:
            return self._request(
                "addNote",
                note={
                    "deckName": self._config.anki_deck,
                    "modelName": self._config.anki_model,
                    "fields": self._formatter.to_fields(card),
                    "options": {"allowDuplicate": False},
                    "tags": ["vocabulary"],
                },
            )
        except AnkiError as e:
            if "duplicate" in str(e).lower():
                raise DuplicateCardError(card.word) from e
            raise

    def update(self, card: WordCard) -> None:
        ids = self._request(
            "findNotes",
            query=f'deck:"{self._config.anki_deck}" (front:"{card.word}" OR 英语单词:"{card.word}")',
        )
        if not ids:
            return
        self._request("updateNoteFields", note={
            "id": ids[0],
            "fields": self._formatter.to_fields(card),
        })

    def store_media(self, filename: str, data_b64: str) -> None:
        self._request("storeMediaFile", filename=filename, data=data_b64)

    # ─────────────────────────────────────────────────────────────── private

    def _ensure_deck(self) -> None:
        decks = self._request("deckNames")
        if self._config.anki_deck not in decks:
            self._request("createDeck", deck=self._config.anki_deck)

    def _request(self, action: str, **params):
        payload = {"action": action, "version": 6, "params": params}
        try:
            resp = requests.post(self._config.anki_url, json=payload, timeout=5)
            result = resp.json()
        except requests.exceptions.ConnectionError as e:
            logger.warning("Cannot connect to Anki at %s", self._config.anki_url)
            raise AnkiConnectionError("Cannot connect to Anki") from e
        if result.get("error"):
            raise AnkiError(result["error"])
        return result["result"]
