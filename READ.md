# anki-vocab

`anki-vocab` is a command-line tool for building English vocabulary cards in Anki. Given a word or phrase, it asks Claude for a structured learner-friendly explanation, generates pronunciation audio with OpenAI TTS, plays the audio locally, and saves the finished card into an Anki deck through AnkiConnect.

## Features

- Generates B1-B2 English explanations for Chinese learners.
- Includes Chinese definitions, translated examples, Collins-style metadata, memory tips, common phrases, and similar-word distinctions.
- Creates WAV pronunciation audio with `gpt-4o-mini-tts`.
- Saves cards to the `英语单词模板(vocab配色)` Anki model.
- Stores full card JSON inside a hidden Anki field so cards can be round-tripped without another LLM call.
- Keeps a local SQLite cache for offline or temporarily failed Anki saves, then syncs pending cards on later runs.

## Requirements

- Python 3.11 or newer.
- Anki desktop app running.
- AnkiConnect installed in Anki. Add-on code: `2055492159`.
- An Anki note model named `英语单词模板(vocab配色)` with these fields:

```text
英语单词
英美音标
中文释义
英语例句
中文例句
vocabulary简明
vocabulary扩展
柯林斯星级
柯林斯解释
英语发音
```

## Installation

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

Install runtime dependencies:

```bash
pip install -r requirements.txt
```

For editable installation with the `anki-vocab` console command and development tools:

```bash
pip install -e ".[dev]"
```

## Configuration

The app loads environment variables from your shell and from a local `.env` file.

Required:

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Optional:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANKI_URL` | `http://localhost:8765` | AnkiConnect endpoint |
| `ANKI_DECK` | `English Vocabulary` | Target Anki deck |
| `ANKI_MODEL` | `英语单词模板(vocab配色)` | Target Anki note model |
| `LLM_MODEL` | `claude-sonnet-4-6` | Claude model used for card text |
| `CACHE_SIZE` | `200` | In-memory Anki lookup cache size |
| `TTS_SPEED` | `1.0` | OpenAI TTS speed, from `0.25` to `4.0` |
| `LOCAL_DB` | `~/.anki-vocab/pending.db` | SQLite cache for pending or synced cards |

Example `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
ANKI_DECK=English Vocabulary
TTS_SPEED=0.9
```

## Usage

Use the project wrapper, which runs the local virtual environment Python:

```bash
./word tenacious
./word "give up"
```

Or run the entry point directly:

```bash
python add_word.py tenacious
python add_word.py --deck "My Deck" serenity
python add_word.py --speed 0.8 verbose
python add_word.py --help
```

If installed with `pip install -e ".[dev]"`, the console script is also available:

```bash
anki-vocab tenacious
```

## How It Works

The CLI entry point is `add_word.py`. It reads configuration, creates the Anki repository, local SQLite store, Claude provider, OpenAI TTS provider, audio player, and terminal renderer, then delegates the workflow to `WordService`.

On each run:

1. A background sync attempts to push previously pending SQLite cards to Anki.
2. The requested word is checked in the local SQLite store first.
3. If not found locally, Anki is queried through AnkiConnect.
4. If the card already exists, its saved audio is played and the card is rendered in the terminal.
5. If the card is new, Claude text generation and OpenAI TTS generation run in parallel.
6. The generated audio is played locally and stored as an Anki media file.
7. The card is saved to Anki. If Anki reports a duplicate, the existing card is updated.
8. If Anki is unavailable, the generated card remains in SQLite and will be retried later.

## Project Layout

| Path | Role |
| --- | --- |
| `add_word.py` | CLI parsing, dependency wiring, and background sync startup |
| `config.py` | Environment-backed runtime configuration |
| `models.py` | `WordCard` and `SimilarWord` data contracts |
| `services/word_service.py` | Main orchestration for lookup, generation, save, update, and sync |
| `llm/claude.py` | Claude prompt, API call, and JSON extraction |
| `tts/openai_tts.py` | OpenAI TTS request and WAV generation |
| `tts/player.py` | Local audio playback and Anki media lookup |
| `anki/repository.py` | AnkiConnect CRUD and media operations |
| `anki/cache.py` | LRU cache wrapper for Anki lookups |
| `anki/local_store.py` | SQLite storage for local cache and pending sync |
| `anki/formatter.py` | Mapping between `WordCard` and Anki model fields |
| `display/renderer.py` | Rich terminal output |
| `tests/test_core.py` | Unit tests for core behavior without real API or Anki calls |

## Development

Run the full test suite:

```bash
venv/bin/pytest tests/
```

Run one test:

```bash
venv/bin/pytest tests/test_core.py::TestWordCard::test_to_dict_and_back
```

Run linting if development dependencies are installed:

```bash
ruff check .
```

The tests use mocks and temporary SQLite databases, so they do not require Anki, Anthropic, OpenAI, or API keys.

## Troubleshooting

If the CLI reports missing API keys, set `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in your shell or `.env`.

If Anki saves fail, confirm Anki is open, AnkiConnect is installed, and `ANKI_URL` points to the running AnkiConnect endpoint.

If audio generation fails, the card can still be created without audio. The warning is logged and the card save continues.

If Anki is offline during generation, the card is saved in `LOCAL_DB` and retried on future runs.
