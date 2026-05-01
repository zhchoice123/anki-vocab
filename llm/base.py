from abc import ABC, abstractmethod

from models import WordCard


class LLMProvider(ABC):
    """Strategy interface — any LLM that can explain a word."""

    @abstractmethod
    def fetch(self, word: str) -> WordCard:
        ...
