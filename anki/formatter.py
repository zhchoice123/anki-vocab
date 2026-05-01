import json
import re

from models import WordCard


class CardFormatter:
    """Maps WordCard ↔ the 10-field 英语单词模板(vocab配色) model."""

    # ──────────────────────────────────────────────── Anki fields → WordCard

    def to_fields(self, card: WordCard) -> dict:
        return {
            "英语单词":      card.word,
            "英美音标":      "",
            "中文释义":      card.chinese_definition,
            "英语例句":      self._numbered_lines(card.examples),
            "中文例句":      self._numbered_lines(card.chinese_examples),
            "vocabulary简明": self._vocab_brief(card),
            "vocabulary扩展": self._vocab_extended(card),
            "柯林斯星级":    self._stars(card.collins_stars),
            "柯林斯解释":    self._collins_html(card),
            "英语发音":      card.audio_ref,
        }

    # ──────────────────────────────────────────────── WordCard → Anki fields

    def from_fields(self, word: str, fields: dict) -> WordCard | None:
        """Reconstruct WordCard from stored Anki fields via hidden JSON."""
        extended = fields.get("vocabulary扩展", {}).get("value", "")
        match = re.search(r'<span id="raw"[^>]*>(.+?)</span>', extended, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
            data["audio_ref"] = fields.get("英语发音", {}).get("value", "")
            return WordCard.from_dict(word, data)
        except (json.JSONDecodeError, KeyError):
            return None

    # ──────────────────────────────────────────────── field builders

    def _numbered_lines(self, items: list[str]) -> str:
        return "".join(f"({i+1}) {item}<br>" for i, item in enumerate(items))

    def _stars(self, n: int) -> str:
        n = max(0, min(5, n))
        return "★" * n + "☆" * (5 - n)

    def _vocab_brief(self, card: WordCard) -> str:
        word = f"<b><u>{card.word}</u></b>"
        return (
            f"{word} means: {card.simple_meaning} "
            f"{card.key_idea}"
        )

    def _vocab_extended(self, card: WordCard) -> str:
        raw_json = json.dumps(card.to_dict(), ensure_ascii=False)
        phrases = "".join(f"<li>{p}</li>" for p in card.common_phrases)
        similar = "".join(
            f"<li><b>{sw.word}</b>: {sw.difference}</li>"
            for sw in card.similar_words
        )
        return (
            f'<span id="raw" style="display:none">{raw_json}</span>'
            f"<b>When to use:</b> {card.when_to_use}<br><br>"
            f"<b>When NOT to use:</b> {card.when_not_to_use}<br><br>"
            f"<b>Memory tip:</b> {card.memory_tip}<br><br>"
            f"<b>Common phrases:</b><ul>{phrases}</ul>"
            f"<b>Similar words:</b><ul>{similar}</ul>"
        )

    def _collins_html(self, card: WordCard) -> str:
        if not card.collins_definition_en:
            return ""
        word_highlighted = f'<span class="text_blue">{card.word}</span>'
        ex_en = card.collins_example_en.replace(
            card.word, word_highlighted, 1
        ) if card.collins_example_en else ""
        return (
            '<div class="tab_content" id="dict_tab_101" style="display:block">'
            '<div class="part_main"><div class="collins_content">'
            '<div class="explanation_item"><div class="explanation_box">'
            '<span class="item_number">1</span>'
            f'<span class="explanation_label">[{card.collins_label}]</span>'
            f'<span class="text_blue">{card.collins_chinese}</span> '
            f'{card.collins_definition_en}'
            '</div>'
            f'<ul><li><p class="sentence_en">{ex_en}</p>'
            f'<p>{card.collins_example_zh}</p></li></ul>'
            '</div></div></div></div>'
        )
