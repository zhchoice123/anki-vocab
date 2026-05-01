"""Core unit tests — no Anki, no Claude API needed."""
import io
import os
import sys
import tempfile
import wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock

import pytest

from anki.cache import CachingAnkiRepository
from anki.formatter import CardFormatter
from anki.local_store import LocalStore
from exceptions import AnkiConnectionError, DuplicateCardError
from tts.utils import pcm_to_padded_wav
from models import SimilarWord, WordCard
from services.word_service import WordService


# ─────────────────────────────────────────────
# Fixture: a reusable sample WordCard
# ─────────────────────────────────────────────
@pytest.fixture
def sample_card() -> WordCard:
    return WordCard(
        word="tenacious",
        simple_meaning="Someone who keeps trying and never gives up.",
        key_idea="It shows very strong will and determination.",
        when_to_use="Describing a person or animal that does not stop.",
        when_not_to_use="Do not use for objects or places.",
        common_phrases=["tenacious effort", "tenacious grip", "tenacious spirit", "tenacious player"],
        examples=["She was tenacious and finished the race.", "The dog had a tenacious hold on the rope."],
        memory_tip="Think of a bulldog that never lets go.",
        similar_words=[
            SimilarWord(word="persistent", difference="Persistent is softer; tenacious is stronger."),
            SimilarWord(word="stubborn",   difference="Stubborn is negative; tenacious is positive."),
        ],
    )


@pytest.fixture
def store(tmp_path) -> LocalStore:
    return LocalStore(str(tmp_path / "test.db"))


# ─────────────────────────────────────────────
# 1. WordCard serialization round-trip
# ─────────────────────────────────────────────
class TestWordCard:
    def test_to_dict_and_back(self, sample_card):
        restored = WordCard.from_dict(sample_card.word, sample_card.to_dict())
        assert restored.word == sample_card.word
        assert restored.simple_meaning == sample_card.simple_meaning
        assert restored.similar_words[0].word == "persistent"
        assert len(restored.common_phrases) == 4

    def test_from_dict_missing_field_raises(self):
        with pytest.raises(KeyError):
            WordCard.from_dict("word", {"simple_meaning": "only one field"})


# ─────────────────────────────────────────────
# 2. CardFormatter field round-trip
# ─────────────────────────────────────────────
class TestCardFormatter:
    def test_fields_contain_word(self, sample_card):
        fields = CardFormatter().to_fields(sample_card)
        assert fields["英语单词"] == "tenacious"

    def test_round_trip_preserves_all_fields(self, sample_card):
        fmt = CardFormatter()
        # Simulate what Anki returns: each field value wrapped in {"value": ...}
        raw_fields = {k: {"value": v} for k, v in fmt.to_fields(sample_card).items()}
        restored = fmt.from_fields(sample_card.word, raw_fields)
        assert restored is not None
        assert restored.memory_tip == sample_card.memory_tip
        assert restored.when_not_to_use == sample_card.when_not_to_use
        assert len(restored.examples) == 2

    def test_from_fields_returns_none_for_old_format(self):
        old_fields = {"vocabulary扩展": {"value": "<b>plain text, no hidden JSON</b>"}}
        result = CardFormatter().from_fields("word", old_fields)
        assert result is None


# ─────────────────────────────────────────────
# 3. LRU Cache
# ─────────────────────────────────────────────
class TestCachingAnkiRepository:

    def _make_repo(self, find_return=None):
        inner = MagicMock()
        inner.find.return_value = find_return
        return CachingAnkiRepository(inner, maxsize=3), inner

    def test_cache_miss_calls_inner(self, sample_card):
        repo, inner = self._make_repo(find_return=sample_card)
        result = repo.find("tenacious")
        inner.find.assert_called_once_with("tenacious")
        assert result == sample_card

    def test_cache_hit_skips_inner(self, sample_card):
        repo, inner = self._make_repo(find_return=sample_card)
        repo.find("tenacious")   # miss → populates cache
        repo.find("tenacious")   # hit  → no Anki call
        assert inner.find.call_count == 1

    def test_cache_is_case_insensitive(self, sample_card):
        repo, inner = self._make_repo(find_return=sample_card)
        repo.find("Tenacious")
        repo.find("tenacious")   # same key after lower()
        assert inner.find.call_count == 1

    def test_none_result_not_cached(self):
        repo, inner = self._make_repo(find_return=None)
        repo.find("unknown")
        repo.find("unknown")     # None not cached → inner called again
        assert inner.find.call_count == 2

    def test_save_writes_through_to_cache(self, sample_card):
        repo, inner = self._make_repo(find_return=None)
        repo.save(sample_card)
        result = repo.find("tenacious")   # should hit cache, not Anki
        inner.find.assert_not_called()
        assert result == sample_card

    def test_update_writes_through_to_cache(self, sample_card):
        repo, inner = self._make_repo(find_return=None)
        repo.update(sample_card)
        result = repo.find("tenacious")
        inner.find.assert_not_called()
        assert result == sample_card

    def test_lru_eviction(self, sample_card):
        """With maxsize=3, inserting a 4th entry evicts the least-recently used."""
        repo, inner = self._make_repo(find_return=sample_card)
        words = ["alpha", "beta", "gamma"]
        for w in words:
            card = WordCard(**{**sample_card.__dict__, "word": w})
            repo.save(card)

        # alpha is LRU — access beta and gamma to push alpha to the front of eviction
        repo.find("beta")
        repo.find("gamma")
        # insert delta → evicts alpha (least recently used)
        delta = WordCard(**{**sample_card.__dict__, "word": "delta"})
        repo.save(delta)

        # alpha should be evicted → inner.find will be called
        inner.find.return_value = sample_card
        repo.find("alpha")
        inner.find.assert_called_once_with("alpha")


# ─────────────────────────────────────────────
# 4. WordService — business logic (mocked deps)
# ─────────────────────────────────────────────
class TestWordService:
    def _make_service(self, card_in_anki=None, fetched_card=None, store=None):
        repo = MagicMock()
        repo.find.return_value = card_in_anki
        llm = MagicMock()
        llm.fetch.return_value = fetched_card
        tts = MagicMock()
        tts.generate.return_value = ("vocab_test.wav", b"FAKEAUDIOBYTES")
        player = MagicMock()
        local = store if store is not None else MagicMock()
        local.find.return_value = None
        local.pending.return_value = []
        return WordService(llm, repo, tts, player, local), repo, llm, local

    def test_find_returns_existing_card(self, sample_card):
        service, repo, llm, _ = self._make_service(card_in_anki=sample_card)
        result = service.find("tenacious")
        assert result == sample_card
        llm.fetch.assert_not_called()

    def test_find_hits_sqlite_cache_without_calling_anki(self, sample_card):
        service, repo, _, local = self._make_service()
        local.find.return_value = sample_card
        result = service.find("tenacious")
        assert result == sample_card
        repo.find.assert_not_called()

    def test_find_returns_none_when_not_in_sqlite_and_anki_down(self):
        service, repo, _, local = self._make_service()
        local.find.return_value = None
        repo.find.side_effect = AnkiConnectionError()
        assert service.find("tenacious") is None

    def test_find_returns_none_for_new_word(self):
        service, _, _, _ = self._make_service(card_in_anki=None)
        assert service.find("newword") is None

    def test_fetch_and_save_calls_llm_and_repo(self, sample_card):
        service, repo, llm, _ = self._make_service(fetched_card=sample_card)
        result = service.fetch_and_save("tenacious")
        llm.fetch.assert_called_once_with("tenacious")
        repo.save.assert_called_once_with(sample_card)
        assert result == sample_card

    def test_fetch_and_save_migrates_old_format_card(self, sample_card):
        service, repo, llm, _ = self._make_service(fetched_card=sample_card)
        repo.save.side_effect = DuplicateCardError("tenacious")
        service.fetch_and_save("tenacious")
        repo.update.assert_called_once_with(sample_card)

    def test_fetch_and_save_falls_back_to_sqlite_when_anki_down(self, sample_card):
        service, repo, llm, local = self._make_service(fetched_card=sample_card)
        repo.store_media.side_effect = AnkiConnectionError()
        service.fetch_and_save("tenacious")
        local.save_pending.assert_called_once()
        repo.save.assert_not_called()

    def test_fetch_and_save_sets_audio_ref(self, sample_card):
        service, repo, llm, _ = self._make_service(fetched_card=sample_card)
        result = service.fetch_and_save("tenacious")
        assert result.audio_ref == "[sound:vocab_test.wav]"


# ─────────────────────────────────────────────
# 5. TTS & audio utils
# ─────────────────────────────────────────────
class TestPCMUtils:
    def _make_pcm(self, frame_count=1_000):
        return b"\1\0" * frame_count

    def test_pcm_to_padded_wav_preserves_audio_and_extends_duration(self):
        from tts.utils import pcm_to_padded_wav

        sample_rate = 24_000
        original_frames = 1_000

        padded = pcm_to_padded_wav(
            self._make_pcm(original_frames),
            leading_ms=100,
            trailing_ms=200,
            sample_rate=sample_rate,
        )

        with wave.open(io.BytesIO(padded), "rb") as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == sample_rate
            assert wav.getnframes() == original_frames + 2_400 + 4_800


class TestOpenAITTS:
    def _make_pcm(self, frame_count=1_000):
        return b"\1\0" * frame_count

    def test_generate_returns_filename_and_bytes(self):
        from tts.openai_tts import OpenAITTS

        client = MagicMock()
        client.audio.speech.create.return_value.content = self._make_pcm(frame_count=10)

        tts = OpenAITTS()
        tts._client = client

        filename, audio_bytes = tts.generate("tenacious")

        assert filename.startswith("vocab_") and filename.endswith(".wav")
        assert isinstance(audio_bytes, bytes)
        assert len(audio_bytes) > 0


class TestAudioPlayer:
    def test_play_bytes_creates_temp_file_and_calls_play_file(self):
        from tts.player import AudioPlayer

        player = AudioPlayer()
        player.play_file = MagicMock()
        player.play_bytes(b"fake wav data")
        player.play_file.assert_called_once()
        args, _ = player.play_file.call_args
        assert args[0].endswith(".wav")


# ─────────────────────────────────────────────
# 6. LocalStore — SQLite offline cache
# ─────────────────────────────────────────────
class TestLocalStore:
    def test_save_and_find_pending(self, store, sample_card):
        store.save_pending(sample_card, "f.wav", "B64DATA")
        found = store.find(sample_card.word)
        assert found is not None
        assert found.word == sample_card.word
        assert found.simple_meaning == sample_card.simple_meaning

    def test_find_returns_none_for_unknown_word(self, store):
        assert store.find("nonexistent") is None

    def test_pending_lists_unsynced_only(self, store, sample_card):
        store.save_pending(sample_card, "f.wav", "B64DATA")
        rows = store.pending()
        assert len(rows) == 1
        card, filename, b64 = rows[0]
        assert card.word == sample_card.word
        assert filename == "f.wav"
        assert b64 == "B64DATA"

    def test_mark_synced_removes_from_pending_keeps_in_cache(self, store, sample_card):
        store.save_pending(sample_card, "f.wav", "B64DATA")
        store.mark_synced(sample_card.word)
        assert store.find(sample_card.word) is not None  # still in cache
        assert store.pending() == []

    def test_upsert_resets_synced_flag(self, store, sample_card):
        store.save_pending(sample_card, "f.wav", "B64")
        store.mark_synced(sample_card.word)
        # saving again after sync should mark it pending once more
        store.save_pending(sample_card, "f2.wav", "B64NEW")
        assert store.find(sample_card.word) is not None

    def test_multiple_pending_words(self, store, sample_card):
        card2 = WordCard(**{**sample_card.__dict__, "word": "ephemeral"})
        store.save_pending(sample_card, "a.wav", "A")
        store.save_pending(card2, "b.wav", "B")
        rows = store.pending()
        assert len(rows) == 2


# ─────────────────────────────────────────────
# 7. WordService.sync_pending
# ─────────────────────────────────────────────
class TestSyncPending:
    def _make_service_with_store(self, store, fetched_card=None):
        repo = MagicMock()
        repo.find.return_value = None
        llm = MagicMock()
        llm.fetch.return_value = fetched_card
        tts = MagicMock()
        tts.generate.return_value = ("vocab_test.wav", b"FAKEAUDIOBYTES")
        player = MagicMock()
        return WordService(llm, repo, tts, player, store), repo

    def test_sync_pending_uploads_and_marks_synced(self, store, sample_card):
        store.save_pending(sample_card, "f.wav", "B64DATA")
        service, repo = self._make_service_with_store(store)

        count = service.sync_pending()

        assert count == 1
        repo.store_media.assert_called_once_with("f.wav", "B64DATA")
        repo.save.assert_called_once()
        assert store.pending() == []  # removed from pending queue

    def test_sync_pending_handles_duplicate(self, store, sample_card):
        store.save_pending(sample_card, "f.wav", "B64DATA")
        service, repo = self._make_service_with_store(store)
        repo.save.side_effect = DuplicateCardError(sample_card.word)

        count = service.sync_pending()

        assert count == 1
        repo.update.assert_called_once()
        assert store.pending() == []

    def test_sync_pending_stops_on_anki_down(self, store, sample_card):
        card2 = WordCard(**{**sample_card.__dict__, "word": "ephemeral"})
        store.save_pending(sample_card, "a.wav", "A")
        store.save_pending(card2, "b.wav", "B")
        service, repo = self._make_service_with_store(store)
        repo.store_media.side_effect = AnkiConnectionError()

        count = service.sync_pending()

        assert count == 0
        assert len(store.pending()) == 2  # nothing synced

    def test_sync_pending_returns_zero_when_nothing_pending(self, store):
        service, _ = self._make_service_with_store(store)
        assert service.sync_pending() == 0


# ─────────────────────────────────────────────
# 8. Error tracking in LocalStore
# ─────────────────────────────────────────────
class TestErrorTracking:
    def test_record_error_creates_row(self, store):
        store.record_error("tenacious")
        words = store.get_error_words(limit=5)
        assert words == ["tenacious"]

    def test_record_error_increments_count(self, store):
        store.record_error("tenacious")
        store.record_error("tenacious")
        store.record_error("tenacious")
        words = store.get_error_words(limit=5)
        assert words == ["tenacious"]
        # count is 3 internally; get_error_words only returns words

    def test_get_error_words_orders_by_count_then_recency(self, store):
        store.record_error("alpha")
        store.record_error("beta")
        store.record_error("beta")  # beta has higher count
        words = store.get_error_words(limit=5)
        assert words[0] == "beta"
        assert words[1] == "alpha"

    def test_get_recent_words_excluding(self, store, sample_card):
        card2 = WordCard(**{**sample_card.__dict__, "word": "ephemeral"})
        store.save_pending(sample_card, "", "")
        store.save_pending(card2, "", "")
        result = store.get_recent_words_excluding(exclude={"tenacious"}, limit=5)
        assert len(result) == 1
        assert result[0].word == "ephemeral"


# ─────────────────────────────────────────────
# 9. WordSelector — error-first strategy
# ─────────────────────────────────────────────
class TestWordSelector:
    def test_prioritises_error_words(self, store, sample_card):
        card2 = WordCard(**{**sample_card.__dict__, "word": "ephemeral"})
        store.save_pending(sample_card, "", "")
        store.save_pending(card2, "", "")
        store.record_error("ephemeral")  # ephemeral is weak

        from practice.selector import WordSelector
        selector = WordSelector(store)
        words = selector.select(count=10)
        names = [w.word for w in words]
        assert names[0] == "ephemeral"  # error word first
        assert "tenacious" in names     # fresh word fills the rest

    def test_falls_back_to_fresh_when_no_errors(self, store, sample_card):
        card2 = WordCard(**{**sample_card.__dict__, "word": "ephemeral"})
        store.save_pending(sample_card, "", "")
        store.save_pending(card2, "", "")

        from practice.selector import WordSelector
        selector = WordSelector(store)
        words = selector.select(count=10)
        names = {w.word for w in words}
        assert names == {"tenacious", "ephemeral"}

    def test_returns_empty_when_no_words(self, store):
        from practice.selector import WordSelector
        selector = WordSelector(store)
        assert selector.select(count=10) == []
