import json
import os
import sqlite3
from datetime import datetime, timezone

from models import WordCard

_DDL_PENDING = """
CREATE TABLE IF NOT EXISTS pending_words (
    word           TEXT PRIMARY KEY,
    card_json      TEXT NOT NULL,
    audio_filename TEXT NOT NULL DEFAULT '',
    audio_b64      TEXT NOT NULL DEFAULT '',
    synced         INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    synced_at      TEXT
)
"""

_DDL_ERRORS = """
CREATE TABLE IF NOT EXISTS word_errors (
    word         TEXT PRIMARY KEY,
    error_count  INTEGER NOT NULL DEFAULT 0,
    last_error   TEXT NOT NULL
)
"""


class LocalStore:
    """SQLite-backed store for WordCards pending Anki sync."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db_path = db_path
        with self._connect() as conn:
            conn.execute(_DDL_PENDING)
            conn.execute(_DDL_ERRORS)

    # ─────────────────────────────────────────────────────────────── public

    def save_pending(self, card: WordCard, audio_filename: str = "", audio_b64: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pending_words
                    (word, card_json, audio_filename, audio_b64, synced, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                ON CONFLICT(word) DO UPDATE SET
                    card_json      = excluded.card_json,
                    audio_filename = excluded.audio_filename,
                    audio_b64      = excluded.audio_b64,
                    synced         = 0,
                    synced_at      = NULL
                """,
                (
                    card.word,
                    json.dumps(card.to_dict(), ensure_ascii=False),
                    audio_filename,
                    audio_b64,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def find(self, word: str) -> WordCard | None:
        """Return the cached card for word (synced or pending), or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT card_json FROM pending_words WHERE word = ?",
                (word,),
            ).fetchone()
        if not row:
            return None
        return WordCard.from_dict(word, json.loads(row[0]))

    def pending(self) -> list[tuple[WordCard, str, str]]:
        """Return all unsynced rows as (card, audio_filename, audio_b64)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT word, card_json, audio_filename, audio_b64"
                " FROM pending_words WHERE synced = 0 ORDER BY created_at"
            ).fetchall()
        result = []
        for word, card_json, filename, b64 in rows:
            result.append((WordCard.from_dict(word, json.loads(card_json)), filename, b64))
        return result

    def recent_words(self, count: int = 8) -> list[WordCard]:
        """Return the most recent N words from the cache (synced or pending)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT word, card_json FROM pending_words"
                " ORDER BY created_at DESC LIMIT ?",
                (count,),
            ).fetchall()
        return [WordCard.from_dict(word, json.loads(card_json)) for word, card_json in rows]

    def get_recent_words_excluding(self, exclude: set[str], limit: int) -> list[WordCard]:
        """Return recent words not in the *exclude* set."""
        placeholders = ",".join("?" * len(exclude)) if exclude else "''"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT word, card_json FROM pending_words"
                f" WHERE word NOT IN ({placeholders})"
                f" ORDER BY created_at DESC LIMIT ?",
                (*exclude, limit),
            ).fetchall()
        return [WordCard.from_dict(word, json.loads(card_json)) for word, card_json in rows]

    # ── error tracking ───────────────────────────────────────────────

    def record_error(self, word: str) -> None:
        """Increment error count for a word (or create row if first time)."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO word_errors (word, error_count, last_error)
                VALUES (?, 1, ?)
                ON CONFLICT(word) DO UPDATE SET
                    error_count = error_count + 1,
                    last_error = excluded.last_error
                """,
                (word, now),
            )

    def get_error_words(self, limit: int = 10) -> list[str]:
        """Return words with the most errors, ordered by count DESC then recency."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT word FROM word_errors"
                " ORDER BY error_count DESC, last_error DESC"
                " LIMIT ?",
                (limit,),
            ).fetchall()
        return [row[0] for row in rows]

    def mark_synced(self, word: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE pending_words SET synced = 1, synced_at = ? WHERE word = ?",
                (datetime.now(timezone.utc).isoformat(), word),
            )

    # ─────────────────────────────────────────────────────────────── private

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)
