import logging
import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

_REQUIRED_KEYS = {
    "ANTHROPIC_API_KEY": "Claude LLM (https://console.anthropic.com/keys)",
    "OPENAI_API_KEY": "OpenAI TTS (https://platform.openai.com/api-keys)",
}

_DEFAULT_LOCAL_DB = os.path.expanduser("~/.anki-vocab/pending.db")


def setup_logging(*, verbose: bool = False, quiet: bool = False) -> None:
    """Configure root logger for the CLI.

    Args:
        verbose: Show DEBUG and above (most detail).
        quiet:   Show only WARNING and above (least detail).

    Default (no flags): INFO and above.
    """
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s %(message)s",
        stream=sys.stderr,
    )
    logging.debug("verbose logging enabled")


@dataclass
class Config:
    anki_url: str = "http://localhost:8765"
    anki_deck: str = "English Vocabulary"
    anki_model: str = "英语单词模板(vocab配色)"
    llm_model: str = "claude-sonnet-4-6"
    cache_size: int = 200
    tts_speed: float = 1.0       # 0.25–4.0, lower = slower & clearer
    local_db: str = field(default_factory=lambda: _DEFAULT_LOCAL_DB)

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            anki_url=os.getenv("ANKI_URL", "http://localhost:8765"),
            anki_deck=os.getenv("ANKI_DECK", "English Vocabulary"),
            anki_model=os.getenv("ANKI_MODEL", "英语单词模板(vocab配色)"),
            llm_model=os.getenv("LLM_MODEL", "claude-sonnet-4-6"),
            cache_size=int(os.getenv("CACHE_SIZE", "200")),
            tts_speed=float(os.getenv("TTS_SPEED", "1.0")),
            local_db=os.getenv("LOCAL_DB", _DEFAULT_LOCAL_DB),
        )

    @staticmethod
    def validate(required_keys: list[str] | tuple[str, ...] | None = None) -> None:
        keys = required_keys or tuple(_REQUIRED_KEYS)
        missing = [k for k in keys if not os.getenv(k)]
        if not missing:
            return
        lines = ["Missing required API keys:"]
        for k in missing:
            lines.append(f"  {k}  — needed for {_REQUIRED_KEYS[k]}")
        lines.append("\nSet them in your shell or copy .env.example → .env and fill in the values.")
        logging.error("\n".join(lines))
        sys.exit(1)
