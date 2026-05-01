# anki-vocab

CLI tool that looks up an English word, generates a rich flashcard explanation via Claude, records a pronunciation via OpenAI TTS, and saves everything into an Anki deck — in one command.

It also includes a **reading comprehension practice mode** that generates考研英语-style passages from your learned vocabulary.

## Prerequisites

- **Anki** desktop app running (optional — offline mode works too)
- **AnkiConnect** addon installed (code: `2055492159`)
- A note model named `英语单词模板(vocab配色)` with these 10 fields in order:
  `英语单词`, `英美音标`, `中文释义`, `英语例句`, `中文例句`, `vocabulary简明`, `vocabulary扩展`, `柯林斯星级`, `柯林斯解释`, `英语发音`
- Python 3.11+

## Installation

```bash
git clone <repo>
cd anki-vocab
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and OPENAI_API_KEY
```

Required keys:

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `OPENAI_API_KEY` | OpenAI API key (TTS) |

Optional overrides:

| Variable | Default | Description |
|---|---|---|
| `ANKI_URL` | `http://localhost:8765` | AnkiConnect endpoint |
| `ANKI_DECK` | `English Vocabulary` | Target deck name |
| `ANKI_MODEL` | `英语单词模板(vocab配色)` | Note model name |
| `LLM_MODEL` | `claude-sonnet-4-6` | Claude model identifier |
| `CACHE_SIZE` | `200` | In-memory LRU cache size |
| `TTS_SPEED` | `1.0` | TTS playback speed (0.25–4.0) |
| `LOCAL_DB` | `~/.anki-vocab/pending.db` | SQLite cache path |

## Usage

### Add a word

```bash
# Short form (backward compatible)
./word tenacious
./word "give up"                     # phrases work too
./word --deck "My Deck" serenity     # override deck per-call
./word --speed 0.8 verbose           # slower, clearer TTS
./word --help

# Explicit subcommand form
./word add tenacious
./word add --deck "My Deck" serenity
```

If the word is already in your deck it plays the saved audio and displays the existing card. Otherwise it calls Claude + TTS in parallel, plays the audio, and saves the new card.

### Global flags

```bash
./word -v tenacious      # verbose (debug logging)
./word -q tenacious      # quiet (warnings only)
```

### Reading comprehension practice

```bash
./word practice                    # use last 10 words (default)
./word practice -n 8               # use 8 words
./word practice --port 8767        # custom server port
./word practice --no-browser       # don't auto-open browser
```

Generates a考研英语-style reading passage (400–500 words, 4–6 paragraphs, 5 MCQs) using your vocabulary. Features:

- **Hover tooltips** — mouse over highlighted words to see their English simple meaning
- **5 question types** — main idea, detail, inference, vocabulary-in-context, author attitude
- **Error tracking** — wrong answers are recorded in SQLite; weak words are prioritised in future sessions
- **Offline** — works even when Anki is closed; cards are queued for sync

## Offline Mode

If Anki is not running when you add a word, the tool silently falls back to a local SQLite cache (`~/.anki-vocab/pending.db`). The full card + audio are saved locally. The next time you run `./word` with Anki open, all pending cards are automatically synced in the background.

## Architecture

```
anki-vocab/
├── add_word.py              # CLI entry point
├── config.py                # Env-based configuration
├── models.py                # WordCard, ReadingMaterial, etc.
├── anki/                    # AnkiConnect integration
│   ├── repository.py        # HTTP API client
│   ├── cache.py             # LRU cache decorator
│   ├── formatter.py         # WordCard ↔ Anki fields
│   └── local_store.py       # SQLite offline cache + error tracking
├── llm/                     # LLM abstraction
│   ├── base.py              # ABC
│   └── claude.py            # Claude provider
├── tts/                     # TTS abstraction (pluggable)
│   ├── base.py              # ABC
│   ├── openai_tts.py        # OpenAI TTS provider
│   ├── player.py            # Cross-platform audio playback
│   └── utils.py             # PCM → WAV utilities
├── services/
│   └── word_service.py      # Orchestration layer
├── practice/                # Reading comprehension mode
│   ├── selector.py          # Smart word selection (errors first)
│   ├── generator.py         # LLM reading generator
│   ├── server.py            # Flask web server
│   ├── templates/
│   │   └── practice.html    # Dark-theme reading UI
│   └── static/
│       └── style.css
├── display/
│   └── renderer.py          # Rich terminal output
└── tests/
    └── test_core.py
```

## Extending TTS

To add a new TTS provider (e.g. ElevenLabs), implement `tts/base.py::TTSProvider` and swap it in `add_word.py`:

```python
from tts.elevenlabs_tts import ElevenLabsTTS
tts = ElevenLabsTTS(voice_id="...")
```

## Development

```bash
./scripts/test                 # full suite
./scripts/test tests/test_core.py -v   # verbose
```

No API keys or Anki are needed for unit tests.
