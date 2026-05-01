from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from models import WordCard

_NUMBERS = ["①", "②", "③", "④", "⑤", "⑥"]
_console = Console()


class CardRenderer:
    """Renderer Pattern — all terminal display logic lives here."""

    def render(self, card: WordCard, is_new: bool) -> None:
        status = "✓  Saved to Anki" if is_new else "◉  Already in your deck"
        color = "bright_green" if is_new else "bright_blue"
        _console.print()
        _console.print(Panel(
            self._build(card, status, color),
            box=box.ROUNDED,
            border_style="bright_blue",
            padding=(0, 1),
        ))
        _console.print()

    def status(self, msg: str) -> None:
        _console.print(f"[dim]{msg}[/dim]")

    def error(self, msg: str) -> None:
        _console.print(f"[bold red]Error:[/] {msg}")

    # ─────────────────────────────────────────────────────────────── private

    def _build(self, card: WordCard, status: str, status_color: str) -> Text:
        c = Text()

        # Word + Chinese definition
        c.append(f"\n  {card.word}", style="bold bright_yellow")
        if card.chinese_definition:
            import re
            zh = re.sub(r"<[^>]+>", "", card.chinese_definition)
            c.append(f"  {zh}", style="bold")
        c.append("\n\n")

        # Collins stars
        if card.collins_stars:
            stars = "★" * card.collins_stars + "☆" * (5 - card.collins_stars)
            c.append(f"  {stars}\n\n", style="yellow")

        self._section(c, "1. SIMPLE MEANING", card.simple_meaning)
        self._section(c, "2. KEY IDEA", card.key_idea)
        self._section(c, "3. WHEN TO USE", card.when_to_use)
        self._section(c, "4. WHEN NOT TO USE", card.when_not_to_use)
        self._list_section(c, "5. COMMON PHRASES", card.common_phrases)

        # English + Chinese examples side by side
        c.append("  6. EXAMPLES\n", style="bold cyan")
        for i, (en, zh) in enumerate(zip(card.examples, card.chinese_examples or [])):
            num = _NUMBERS[i] if i < len(_NUMBERS) else "•"
            c.append(f"  {num}  {en}\n", style="bold")
            c.append(f"      {zh}\n", style="bold dim")
        # remaining English-only examples (if more EN than ZH)
        for i in range(len(card.chinese_examples or []), len(card.examples)):
            num = _NUMBERS[i] if i < len(_NUMBERS) else "•"
            c.append(f"  {num}  {card.examples[i]}\n", style="bold")
        c.append("\n")

        self._section(c, "7. MEMORY TIP", card.memory_tip)

        c.append("  8. SIMILAR WORDS\n", style="bold cyan")
        for sw in card.similar_words:
            c.append(f"  • {sw.word}: ", style="bold bright_yellow")
            c.append(f"{sw.difference}\n", style="bold")
        c.append("\n")

        # Collins excerpt
        if card.collins_definition_en:
            c.append("  COLLINS\n", style="bold cyan")
            c.append(f"  [{card.collins_label}] ", style="dim")
            c.append(f"{card.collins_definition_en}\n", style="bold")
            if card.collins_example_en:
                c.append(f'  “{card.collins_example_en}”\n', style="italic")
                c.append(f"  {card.collins_example_zh}\n", style="dim")
            c.append("\n")

        audio = "🔊" if card.audio_ref else "  "
        c.append(f"  {audio}  {status}", style=f"bold {status_color}")
        return c

    def _section(self, c: Text, title: str, content: str) -> None:
        c.append(f"  {title}\n", style="bold cyan")
        c.append(f"  {content}\n\n", style="bold")

    def _list_section(self, c: Text, title: str, items: list[str]) -> None:
        c.append(f"  {title}\n", style="bold cyan")
        for i, item in enumerate(items):
            num = _NUMBERS[i] if i < len(_NUMBERS) else "•"
            c.append(f"  {num}  {item}\n", style="bold")
        c.append("\n")
