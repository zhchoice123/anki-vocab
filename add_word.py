#!/usr/bin/env python3
"""CLI entry point — parse args and wire up the application."""

import argparse
import logging
import sys
import threading
from importlib.metadata import PackageNotFoundError, version

from anki.cache import CachingAnkiRepository
from anki.local_store import LocalStore
from anki.repository import AnkiRepository
from config import Config, setup_logging
from display.renderer import CardRenderer
from exceptions import LLMError
from llm.claude import ClaudeProvider
from tts.openai_tts import OpenAITTS
from tts.player import AudioPlayer
from services.word_service import WordService

_KNOWN_COMMANDS = {"add", "practice"}


def _get_version() -> str:
    try:
        return version("anki-vocab")
    except PackageNotFoundError:
        return "dev"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="anki-vocab",
        description="Look up a word, generate a flashcard with Claude, and save it to Anki.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_get_version()}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show debug output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-error output")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── add (default) ───────────────────────────────────────────────
    add_parser = subparsers.add_parser("add", help="Add a word to Anki")
    add_parser.add_argument("word", nargs="*", help="Word or phrase to look up")
    add_parser.add_argument("--deck", metavar="NAME", help="Anki deck name (overrides ANKI_DECK)")
    add_parser.add_argument("--model", metavar="NAME", help="Anki note model name (overrides ANKI_MODEL)")
    add_parser.add_argument(
        "--speed",
        metavar="N",
        type=float,
        help="TTS playback speed 0.25–4.0 (overrides TTS_SPEED)",
    )

    # ── practice ────────────────────────────────────────────────────
    practice_parser = subparsers.add_parser(
        "practice", help="Generate a reading comprehension exercise"
    )
    practice_parser.add_argument(
        "-n", "--count", type=int, default=10,
        help="Number of words to include in the passage (default: 10)"
    )
    practice_parser.add_argument(
        "--port", type=int, default=8766,
        help="Port for the practice web server (default: 8766)"
    )
    practice_parser.add_argument(
        "--no-browser", action="store_true",
        help="Do not automatically open the browser"
    )

    # Backward compatibility: if first positional arg is not a known command,
    # prepend "add" so `./word hello` still works.
    args = sys.argv[1:]
    if args and not args[0].startswith("-") and args[0] not in _KNOWN_COMMANDS:
        sys.argv.insert(1, "add")

    return parser.parse_args()


def _build_service(args: argparse.Namespace) -> tuple[WordService, CardRenderer, AudioPlayer, Config]:
    Config.validate()
    config = Config.from_env()
    if hasattr(args, "deck") and args.deck:
        config.anki_deck = args.deck
    if hasattr(args, "model") and args.model:
        config.anki_model = args.model
    if hasattr(args, "speed") and args.speed is not None:
        config.tts_speed = args.speed

    renderer = CardRenderer()
    repo = CachingAnkiRepository(AnkiRepository(config), maxsize=config.cache_size)
    local = LocalStore(config.local_db)
    llm = ClaudeProvider(config)
    tts = OpenAITTS(voice="cedar", speed=config.tts_speed)
    player = AudioPlayer()
    service = WordService(llm, repo, tts, player, local)
    return service, renderer, player, config


def _cmd_add(args: argparse.Namespace) -> None:
    service, renderer, player, _config = _build_service(args)

    word = " ".join(args.word).strip() if args.word else input("Enter word: ").strip()
    if not word:
        logging.error("No word provided.")
        sys.exit(1)

    # Background sync
    _sync_count: list[int] = [0]

    def _do_sync() -> None:
        _sync_count[0] = service.sync_pending()

    sync_thread = threading.Thread(target=_do_sync, daemon=True)
    sync_thread.start()

    try:
        renderer.status(f"\nChecking '{word}'...")
        card = service.find(word)
        if card:
            player.play_from_ref(card.audio_ref)
            renderer.render(card, is_new=False)
        else:
            renderer.status("  Asking Claude...")
            card = service.fetch_and_save(word)
            renderer.render(card, is_new=True)

    except LLMError as e:
        renderer.error(f"Claude API error: {e}")
        sys.exit(1)
    except Exception as e:
        renderer.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        sync_thread.join(timeout=5.0)
        if _sync_count[0] > 0:
            renderer.status(f"  [sync] synced {_sync_count[0]} pending word(s) to Anki")


def _cmd_practice(args: argparse.Namespace) -> None:
    from practice.selector import WordSelector
    from practice.generator import ReadingGenerator
    from practice.server import create_app, run_server

    service, _renderer, _player, config = _build_service(args)
    selector = WordSelector(service._local, service._repo)
    words = selector.select(args.count)
    if not words:
        logging.error(
            "No words found in your vocabulary cache. "
            "Add some words first with: ./word <word>"
        )
        sys.exit(1)

    logging.info("Using words: %s", ", ".join(w.word for w in words))
    generator = ReadingGenerator(service._llm)
    material = generator.generate(words)
    app = create_app(material, service._local)
    run_server(app, port=args.port, open_browser=not args.no_browser)


def main() -> None:
    args = _parse_args()
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    command = args.command or "add"
    if command == "add":
        _cmd_add(args)
    elif command == "practice":
        _cmd_practice(args)
    else:
        logging.error("Unknown command: %s", command)
        sys.exit(1)


if __name__ == "__main__":
    main()
