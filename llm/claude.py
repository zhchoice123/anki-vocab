import json
import logging
import re

import anthropic

from config import Config
from exceptions import LLMError
from llm.base import LLMProvider
from models import ReadingMaterial, ReadingQuestion, WordCard

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a professional English dictionary editor.
Explain the given word for a Chinese learner at B1–B2 level.

Rules:
- Simple English only (B1–B2), short sentences (max 15 words each)
- Do not repeat the word too many times
- Chinese must be natural, fluent Mandarin

Reply ONLY with this exact JSON (no extra text, no markdown):
{
  "simple_meaning": "<one short English sentence>",
  "key_idea": "<what makes this word special, one sentence>",
  "when_to_use": "<practical English situations>",
  "when_not_to_use": "<common wrong situations>",
  "common_phrases": ["<phrase 1>", "<phrase 2>", "<phrase 3>", "<phrase 4>"],
  "examples": ["<English example 1>", "<English example 2>", "<English example 3>"],
  "memory_tip": "<simple mental image to remember the word>",
  "similar_words": [
    {"word": "<similar>", "difference": "<one-line difference>"},
    {"word": "<similar>", "difference": "<one-line difference>"}
  ],

  "chinese_definition": "<a class='pos_X'>X.</a>中文释义1；中文释义2",
  "chinese_examples": ["<中文翻译1>", "<中文翻译2>", "<中文翻译3>"],

  "collins_stars": <integer 1-5, based on word frequency: 5=very common, 1=rare>,
  "collins_label": "<e.g. VERB 动词 | NOUN 名词 | ADJ 形容词 | ADV 副词>",
  "collins_definition_en": "<one clear English definition sentence in Collins style>",
  "collins_chinese": "<对应的中文释义>",
  "collins_example_en": "<one natural English example sentence>",
  "collins_example_zh": "<该例句的中文翻译>"
}

For chinese_definition use these pos tags exactly:
  noun → <a class='pos_n'>n.</a>
  verb → <a class='pos_v'>v.</a> or <a class='pos_vt'>vt.</a> or <a class='pos_vi'>vi.</a>
  adjective → <a class='pos_adj'>adj.</a>
  adverb → <a class='pos_adv'>adv.</a>"""


class ClaudeProvider(LLMProvider):

    def __init__(self, config: Config):
        self._config = config
        self._client: anthropic.Anthropic | None = None

    @property
    def _api(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(max_retries=3)
        return self._client

    def fetch(self, word: str) -> WordCard:
        try:
            message = self._api.messages.create(
                model=self._config.llm_model,
                max_tokens=1200,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{
                    "role": "user",
                    "content": [{
                        "type": "text",
                        "text": f'Explain the word "{word}".',
                        "cache_control": {"type": "ephemeral"},
                    }],
                }],
            )
            text = message.content[0].text.strip()
            data = json.loads(self._extract_json(text))
            logger.debug("Claude response parsed successfully for '%s'", word)
            return WordCard.from_dict(word, data)
        except json.JSONDecodeError as e:
            logger.error("Claude returned invalid JSON for '%s': %s", word, e)
            raise LLMError(f"Claude returned invalid JSON: {e}") from e
        except Exception as e:
            logger.error("Claude API error for '%s': %s", word, e)
            raise LLMError(f"Claude API error: {e}") from e

    def generate_reading(self, words: list[WordCard]) -> ReadingMaterial:
        """Generate a考研英语-style reading comprehension passage."""
        word_list = "\n".join(
            f'- {card.word}: {card.simple_meaning}' for card in words
        )
        prompt = (
            "You are an English reading comprehension author specialising in Chinese postgraduate "
            "entrance exam (考研英语) materials.\n\n"
            "Given these vocabulary words and their meanings:\n"
            f"{word_list}\n\n"
            "Choose ONE topic from this list and write a passage in that style:\n"
            "history, economics, politics, culture, technology, sports, environment, "
            "art, psychology, science, business, health, education, sociology.\n\n"
            "Passage requirements (考研英语标准):\n"
            "- Length: 400-500 words\n"
            "- Structure: 4-6 clearly separated paragraphs (use \\n\\n between paragraphs)\n"
            "- Style: academic / argumentative / expository, C1 level\n"
            "- Tone: analytical and objective, like real考研英语阅读真题\n"
            "- Naturally use ALL of the given words in the passage\n"
            "- If the word list is small (< 10), introduce 1-3 extra advanced (C1-C2) words\n"
            "  to enrich the text. List them in the extra_words field.\n\n"
            "Create EXACTLY 5 multiple-choice reading comprehension questions.\n"
            "Each question must have 4 options (A-D) and test passage understanding.\n"
            "The 5 questions MUST cover these 5 distinct types (one each):\n"
            "  1. main_idea     — 主旨大意题 (what is the passage mainly about?)\n"
            "  2. detail        — 细节理解题 (specific fact from the text)\n"
            "  3. inference     — 推理判断题 (what can be inferred?)\n"
            "  4. vocabulary    — 词义猜测题 (what does X mean in context?)\n"
            "  5. attitude      — 作者态度题 (what is the author's attitude?)\n\n"
            "CRITICAL: each question must include:\n"
            "  - 'target_word': the specific word from the given list this question tests\n"
            "  - 'question_type': one of [main_idea, detail, inference, vocabulary, attitude]\n\n"
            "In the article text, wrap each target word with double brackets like [[word]].\n\n"
            "Return ONLY valid JSON in this exact schema (no markdown, no extra text):\n"
            '{\n'
            '  "title": "A Catchy Title",\n'
            '  "article": "Paragraph 1...\\n\\nParagraph 2...\\n\\nParagraph 3...",\n'
            '  "questions": [\n'
            '    {\n'
            '      "question": "...",\n'
            '      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],\n'
            '      "answer": "B",\n'
            '      "explanation": "One sentence explaining why B is correct.",\n'
            '      "target_word": "ephemeral",\n'
            '      "question_type": "detail"\n'
            '    }\n'
            '  ],\n'
            '  "extra_words": ["proliferation", "hegemony"]\n'
            '}'
        )
        try:
            message = self._api.messages.create(
                model=self._config.llm_model,
                max_tokens=3000,
                system=[{
                    "type": "text",
                    "text": "You write考研英语-style reading comprehension exercises.",
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{
                    "role": "user",
                    "content": [{
                        "type": "text",
                        "text": prompt,
                        "cache_control": {"type": "ephemeral"},
                    }],
                }],
            )
            text = message.content[0].text.strip()
            data = json.loads(self._extract_json(text))
            article = data["article"]
            word_glosses = {card.word: card.simple_meaning for card in words}

            extra_words = data.get("extra_words", [])
            for ew in extra_words:
                word_glosses[ew] = ""  # extra words have no stored meaning

            # Replace paragraph breaks with <p> tags for HTML rendering
            article_html = self._highlight_words(article, word_glosses)
            article_html = article_html.replace("\n\n", "</p><p>")
            if not article_html.startswith("<p>"):
                article_html = f"<p>{article_html}</p>"
            if not article_html.endswith("</p>"):
                article_html = f"{article_html}</p>"

            questions = [
                ReadingQuestion(
                    question=q["question"],
                    options=q["options"],
                    answer=q["answer"],
                    explanation=q["explanation"],
                    target_word=q.get("target_word", ""),
                    question_type=q.get("question_type", ""),
                )
                for q in data["questions"]
            ]
            logger.info(
                "Generated reading passage '%s' with %d questions (%d extra words)",
                data["title"], len(questions), len(extra_words),
            )
            return ReadingMaterial(
                title=data["title"],
                article_html=article_html,
                questions=questions,
                words=list(word_glosses.keys()),
            )
        except json.JSONDecodeError as e:
            logger.error("Claude returned invalid JSON for reading: %s", e)
            raise LLMError(f"Invalid JSON from Claude: {e}") from e
        except Exception as e:
            logger.error("Claude API error during reading generation: %s", e)
            raise LLMError(f"Claude API error: {e}") from e

    @staticmethod
    def _highlight_words(article: str, glosses: dict[str, str]) -> str:
        """Replace [[word]] markers with highlighted HTML spans."""
        for word in sorted(glosses.keys(), key=len, reverse=True):
            meaning = glosses[word].replace('"', '&quot;')
            article = article.replace(
                f"[[{word}]]",
                f'<span class="vocab-word" data-meaning="{meaning}">{word}</span>',
            )
        return article

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract the first complete JSON object from text.

        Counts brace depth so it handles any surrounding prose or
        markdown code fences without relying on specific delimiters.
        """
        start = text.find("{")
        if start == -1:
            return text
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    raw = text[start : i + 1]
                    return re.sub(r',\s*([}\]])', r'\1', raw)
        return text[start:]
