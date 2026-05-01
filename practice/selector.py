import logging
from typing import Protocol

from anki.local_store import LocalStore
from exceptions import AnkiConnectionError
from models import WordCard

logger = logging.getLogger(__name__)


class _RepoLike(Protocol):
    def find(self, word: str) -> WordCard | None: ...
    def recent_words(self, limit: int = 10, exclude: set[str] | None = None) -> list[WordCard]: ...


class WordSelector:
    """Pick vocabulary words for reading practice.

    Strategy:
    1. Prioritise words with recorded errors (weak words first).
    2. Fill remaining slots with the newest words from the cache.
    """

    def __init__(self, local: LocalStore, repo: _RepoLike | None = None):
        self._local = local
        self._repo = repo

    def select(self, count: int = 10) -> list[WordCard]:
        """Return up to *count* words, prioritising error-prone ones."""
        selected: list[WordCard] = []
        selected_words: set[str] = set()

        # 1. Error-prone words first
        error_words = self._local.get_error_words(limit=count)
        for w in error_words:
            card = self._local.find(w)
            if card and card.word not in selected_words:
                selected.append(card)
                selected_words.add(card.word)

        logger.info("Selected %d error-prone word(s)", len(selected))

        # 2. Fill with newest non-error words
        needed = count - len(selected)
        if needed > 0:
            fresh = self._local.get_recent_words_excluding(
                exclude=selected_words, limit=needed
            )
            for card in fresh:
                if card.word not in selected_words:
                    selected.append(card)
                    selected_words.add(card.word)
            logger.info("Filled %d fresh word(s)", len(fresh))

        # 3. Best-effort Anki fallback (if still short and Anki is up)
        if len(selected) < count and self._repo is not None:
            extra = self._fetch_from_anki(count - len(selected), selected_words)
            selected.extend(extra)
            logger.info("Pulled %d extra word(s) from Anki", len(extra))

        return selected

    def _fetch_from_anki(self, needed: int, exclude: set[str]) -> list[WordCard]:
        """Fetch recent words from Anki deck (best-effort)."""
        try:
            return self._repo.recent_words(limit=needed, exclude=exclude) if self._repo else []
        except AnkiConnectionError:
            logger.warning("Anki unreachable — using only SQLite words")
            return []
