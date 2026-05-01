import base64
import logging
from concurrent.futures import Future, ThreadPoolExecutor

from anki.local_store import LocalStore
from anki.repository import AnkiRepository
from exceptions import AnkiConnectionError, DuplicateCardError
from llm.base import LLMProvider
from tts.base import TTSProvider
from tts.player import AudioPlayer
from models import WordCard

logger = logging.getLogger(__name__)


class WordService:
    """Service layer — orchestrates LLM, TTS, and Anki repository."""

    def __init__(
        self,
        llm: LLMProvider,
        repo: AnkiRepository,
        tts: TTSProvider,
        player: AudioPlayer,
        local: LocalStore,
    ):
        self._llm = llm
        self._repo = repo
        self._tts = tts
        self._player = player
        self._local = local

    def find(self, word: str) -> WordCard | None:
        card = self._local.find(word)
        if card:
            logger.debug("Found '%s' in local SQLite cache", word)
            return card
        try:
            card = self._repo.find(word)
            if card:
                logger.debug("Found '%s' in Anki", word)
            return card
        except AnkiConnectionError:
            logger.warning("Anki unreachable during find('%s')", word)
            return None

    def fetch_and_save(self, word: str) -> WordCard:
        """Fetch explanation and audio in parallel, then save to SQLite cache and Anki."""
        with ThreadPoolExecutor(max_workers=2) as pool:
            future_card: Future[WordCard]         = pool.submit(self._llm.fetch, word)
            future_audio: Future[tuple[str, bytes]] = pool.submit(self._tts.generate, word)
            card = future_card.result()
            try:
                filename, audio_bytes = future_audio.result()
                self._player.play_bytes(audio_bytes)
                card.audio_ref = f"[sound:{filename}]"
                audio_b64 = base64.b64encode(audio_bytes).decode()
            except Exception as e:
                logging.warning("TTS generation failed: %s", e)
                filename, audio_b64 = "", ""

        self._local.save_pending(card, filename, audio_b64)

        try:
            if filename:
                self._repo.store_media(filename, audio_b64)
            try:
                self._repo.save(card)
            except DuplicateCardError:
                self._repo.update(card)
            self._local.mark_synced(card.word)
        except AnkiConnectionError:
            logger.info("Anki unreachable — '%s' kept in SQLite for later sync", word)

        return card

    def sync_pending(self) -> int:
        """Push any SQLite-pending words to Anki. Returns count synced. Stops on first failure."""
        pending = self._local.pending()
        if not pending:
            return 0
        logger.debug("Syncing %d pending word(s) to Anki", len(pending))
        synced = 0
        for card, filename, audio_b64 in pending:
            try:
                if filename and audio_b64:
                    self._repo.store_media(filename, audio_b64)
                try:
                    self._repo.save(card)
                except DuplicateCardError:
                    self._repo.update(card)
                self._local.mark_synced(card.word)
                synced += 1
            except AnkiConnectionError:
                logger.warning("Anki unreachable during sync — stopped at '%s'", card.word)
                break
        if synced:
            logger.info("Synced %d word(s) to Anki", synced)
        return synced
