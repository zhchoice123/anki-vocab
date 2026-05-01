from collections import OrderedDict

from models import WordCard


class _LRUCache:
    """LRU cache backed by OrderedDict.

    OrderedDict preserves insertion order and supports move_to_end(),
    which lets us maintain access order without any third-party library.
    The least-recently-used entry always sits at the front (last=False).
    """

    def __init__(self, maxsize: int):
        self._maxsize = maxsize
        self._data: OrderedDict[str, WordCard] = OrderedDict()

    def get(self, key: str) -> WordCard | None:
        if key not in self._data:
            return None
        self._data.move_to_end(key)   # mark as most-recently used
        return self._data[key]

    def put(self, key: str, value: WordCard) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self._maxsize:
            self._data.popitem(last=False)  # evict least-recently used

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)


class CachingAnkiRepository:
    """Decorator Pattern — adds LRU caching in front of AnkiRepository.

    find()   → cache hit  : return immediately, zero Anki requests
               cache miss : query Anki, populate cache, return
    save()   → write-through: save to Anki then update cache
    update() → write-through: update Anki then update cache
    """

    def __init__(self, inner, maxsize: int = 200):
        self._inner = inner
        self._cache = _LRUCache(maxsize)

    # ─────────────────────────────────────────── cached operations

    def find(self, word: str) -> WordCard | None:
        key = word.lower()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        card = self._inner.find(word)
        if card is not None:
            self._cache.put(key, card)
        return card

    def save(self, card: WordCard) -> int:
        result = self._inner.save(card)
        self._cache.put(card.word.lower(), card)
        return result

    def update(self, card: WordCard) -> None:
        self._inner.update(card)
        self._cache.put(card.word.lower(), card)

    # ─────────────────────────────────────────── passthrough

    def store_media(self, filename: str, data_b64: str) -> None:
        self._inner.store_media(filename, data_b64)

    def recent_words(self, limit: int = 10, exclude: set[str] | None = None) -> list[WordCard]:
        cards = self._inner.recent_words(limit=limit, exclude=exclude)
        for card in cards:
            self._cache.put(card.word.lower(), card)
        return cards
