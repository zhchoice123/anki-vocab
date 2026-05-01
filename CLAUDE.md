# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the tool
./word <word>                        # via shell wrapper (activates venv)
python add_word.py <word>            # direct

# Tests (no Anki or API keys needed)
venv/bin/pytest tests/               # full suite
venv/bin/pytest tests/test_core.py::TestWordCard::test_to_dict_and_back  # single test

# Install dependencies
pip install -r requirements.txt
```

## Environment variables

`ANTHROPIC_API_KEY` and `OPENAI_API_KEY` must be set. Optional overrides (see `config.py`): `ANKI_URL`, `ANKI_DECK`, `ANKI_MODEL`, `LLM_MODEL`, `CACHE_SIZE`, `TTS_SPEED`.

## Architecture

The entry point (`add_word.py`) wires up all dependencies and delegates to `WordService`:

1. **`services/word_service.py`** — orchestration layer. `fetch_and_save()` runs the LLM call and TTS generation **in parallel** via `ThreadPoolExecutor`, then saves the card to Anki. On duplicate, it falls back to `update()`.

2. **`llm/`** — LLM abstraction. `LLMProvider` (ABC) → `ClaudeProvider`. The prompt lives in `llm/claude.py` and instructs Claude to return a specific JSON schema. `_extract_json()` parses the response by counting brace depth rather than relying on delimiters.

3. **`llm/tts.py`** — `OpenAITTS` calls OpenAI's `gpt-4o-mini-tts` in PCM format, wraps it in a WAV container with leading/trailing silence, plays it immediately via `afplay` (macOS only), then uploads the file to Anki's media store.

4. **`anki/`** — Anki integration via [AnkiConnect](https://ankiweb.net/shared/info/2055492159) HTTP API on `localhost:8765`.
   - `AnkiRepository` — CRUD operations.
   - `CachingAnkiRepository` — Decorator pattern adding an LRU cache in front. `find()` is cache-read; `save()`/`update()` are write-through.
   - `CardFormatter` — maps `WordCard` ↔ the 10 fields of the `英语单词模板(vocab配色)` Anki model. Crucially, it serialises the full `WordCard` JSON into a hidden `<span id="raw">` element inside the `vocabulary扩展` field so cards can be round-tripped back to `WordCard` objects without re-querying Claude.

5. **`models.py`** — `WordCard` dataclass is the central data contract. `to_dict()`/`from_dict()` handle serialisation; `audio_ref` stores the Anki `[sound:vocab_<md5>.wav]` reference.

6. **`display/renderer.py`** — all terminal output via Rich. Stateless; receives a `WordCard` and renders it.
