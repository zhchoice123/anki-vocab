import logging

from llm.base import LLMProvider
from models import ReadingMaterial, WordCard

logger = logging.getLogger(__name__)


class ReadingGenerator:
    """Orchestrates LLM call to produce a reading exercise."""

    def __init__(self, llm: LLMProvider):
        self._llm = llm

    def generate(self, words: list[WordCard]) -> ReadingMaterial:
        if not words:
            raise ValueError("Need at least one word to generate a reading passage")
        logger.info("Generating reading passage for %d word(s)", len(words))
        return self._llm.generate_reading(words)
