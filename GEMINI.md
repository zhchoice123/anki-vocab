# Gemini Context: anki-vocab

This project is a CLI tool designed to streamline the process of adding high-quality English vocabulary flashcards to Anki. It leverages the Claude API (Anthropic) for generating detailed, context-aware explanations and the OpenAI TTS API for high-quality pronunciation audio.

## Project Overview

- **Core Functionality:** Takes an English word/phrase, fetches a structured explanation from Claude, generates TTS audio via OpenAI, and saves it to a specific Anki note model via AnkiConnect.
- **Key Technologies:**
  - **Language:** Python 3.11+
  - **APIs:** Anthropic (Claude 3.5 Sonnet recommended), OpenAI (TTS-1)
  - **Integrations:** Anki (via AnkiConnect addon)
  - **CLI Rendering:** `rich` for beautiful terminal output
- **Architecture:**
  - `add_word.py`: Main entry point and CLI argument parsing.
  - `services/word_service.py`: Orchestrates the LLM and TTS fetching in parallel using `ThreadPoolExecutor`.
  - `llm/`: Contains providers for Claude (`claude.py`) and TTS (`tts.py`).
  - `anki/`: Handles communication with AnkiConnect (`repository.py`) and formatting data for the specific 10-field Anki model (`formatter.py`).
  - `models.py`: Defines the `WordCard` dataclass used throughout the application.
  - `config.py`: Environment-based configuration using `python-dotenv`.

## Building and Running

### Prerequisites
- Anki desktop application must be running.
- **AnkiConnect** addon must be installed (Code: `2055492159`).
- A specific note model named `英语单词模板(vocab配色)` is required with 10 fields (see README for details).

### Installation
```bash
# Clone the repository and enter it
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Configuration
Create a `.env` file from the example:
```bash
cp .env.example .env
```
Required variables:
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

### Usage
```bash
# Basic usage
anki-vocab tenacity

# Phrases (quoted)
anki-vocab "break a leg"

# Override deck or speed
anki-vocab --deck "New Deck" --speed 0.9 serenity
```

### Testing and Quality
```bash
# Run unit tests
pytest

# Linting
ruff check .
```

## Development Conventions

- **Type Hinting:** Strictly use Python type hints for all function signatures and variable declarations.
- **Error Handling:** Use custom exceptions defined in `exceptions.py` (e.g., `AnkiConnectionError`, `LLMError`) to maintain a clean error flow.
- **Concurrency:** Use `concurrent.futures` for I/O-bound tasks (like calling multiple APIs) to keep the CLI responsive.
- **Field Mapping:** The `CardFormatter` class in `anki/formatter.py` is the source of truth for how `WordCard` data maps to Anki fields. It also embeds a hidden JSON string in the Anki note to allow rebuilding the `WordCard` object from existing notes.
- **Prompt Engineering:** The Claude prompt is managed in `llm/claude.py`. It enforces a strict JSON output format for reliable parsing.
- **Linting:** Follow the `ruff` configuration (line length 120, specific lint rules).
