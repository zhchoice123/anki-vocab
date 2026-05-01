from dataclasses import dataclass, field


@dataclass
class ReadingQuestion:
    question: str
    options: list[str]
    answer: str
    explanation: str
    target_word: str = ""      # which vocab word this question tests
    question_type: str = ""    # main_idea | detail | inference | vocabulary | attitude


@dataclass
class ReadingMaterial:
    title: str
    article_html: str
    questions: list[ReadingQuestion]
    words: list[str]


@dataclass
class SimilarWord:
    word: str
    difference: str


@dataclass
class WordCard:
    # ── core (Claude-generated, B1-B2 English) ──────────────────────────────
    word: str
    simple_meaning: str
    key_idea: str
    when_to_use: str
    when_not_to_use: str
    common_phrases: list[str]
    examples: list[str]
    memory_tip: str
    similar_words: list[SimilarWord]

    # ── Chinese content ──────────────────────────────────────────────────────
    chinese_definition: str = ""        # <a class='pos_v'>v.</a>遵守；忍受
    chinese_examples: list[str] = field(default_factory=list)

    # ── Collins-style content ────────────────────────────────────────────────
    collins_stars: int = 0              # 1-5, rendered as ★★☆☆☆
    collins_label: str = ""             # e.g. "VERB 动词"
    collins_definition_en: str = ""     # English Collins definition
    collins_chinese: str = ""           # Chinese Collins definition
    collins_example_en: str = ""        # Collins example sentence (EN)
    collins_example_zh: str = ""        # Collins example sentence (ZH)

    # ── audio ────────────────────────────────────────────────────────────────
    audio_ref: str = ""                 # [sound:vocab_xxxx.mp3]

    # ── serialization ────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "simple_meaning": self.simple_meaning,
            "key_idea": self.key_idea,
            "when_to_use": self.when_to_use,
            "when_not_to_use": self.when_not_to_use,
            "common_phrases": self.common_phrases,
            "examples": self.examples,
            "memory_tip": self.memory_tip,
            "similar_words": [{"word": sw.word, "difference": sw.difference} for sw in self.similar_words],
            "chinese_definition": self.chinese_definition,
            "chinese_examples": self.chinese_examples,
            "collins_stars": self.collins_stars,
            "collins_label": self.collins_label,
            "collins_definition_en": self.collins_definition_en,
            "collins_chinese": self.collins_chinese,
            "collins_example_en": self.collins_example_en,
            "collins_example_zh": self.collins_example_zh,
            "audio_ref": self.audio_ref,
        }

    @classmethod
    def from_dict(cls, word: str, data: dict) -> "WordCard":
        return cls(
            word=word,
            simple_meaning=data["simple_meaning"],
            key_idea=data["key_idea"],
            when_to_use=data["when_to_use"],
            when_not_to_use=data["when_not_to_use"],
            common_phrases=data["common_phrases"],
            examples=data["examples"],
            memory_tip=data["memory_tip"],
            similar_words=[SimilarWord(**sw) for sw in data["similar_words"]],
            chinese_definition=data.get("chinese_definition", ""),
            chinese_examples=data.get("chinese_examples", []),
            collins_stars=data.get("collins_stars", 0),
            collins_label=data.get("collins_label", ""),
            collins_definition_en=data.get("collins_definition_en", ""),
            collins_chinese=data.get("collins_chinese", ""),
            collins_example_en=data.get("collins_example_en", ""),
            collins_example_zh=data.get("collins_example_zh", ""),
            audio_ref=data.get("audio_ref", ""),
        )
