"""
Hand evaluator: given 5-7 cards, return an integer where higher = stronger.

Encoding: 6 nibbles packed into a single int, most significant first:

    [category][tb1][tb2][tb3][tb4][tb5]

Category (1-9):
    1 high card, 2 one pair, 3 two pair, 4 trips,
    5 straight, 6 flush, 7 full house, 8 quads, 9 straight flush

Tiebreaks are ranks (2-14, 14=A), ordered by significance for the category
(e.g. quad rank then kicker; higher pair, lower pair, then kicker). For
straights, only the top card is significant — the wheel is 5-high. Unused
slots are 0. Category sits in the highest nibble, so plain int comparison
gives both category dominance and kicker-by-kicker tiebreak automatically.
"""

from collections import Counter
from itertools import combinations

from cards import card_rank, card_suit


HIGH_CARD = 1
ONE_PAIR = 2
TWO_PAIR = 3
THREE_KIND = 4
STRAIGHT = 5
FLUSH = 6
FULL_HOUSE = 7
FOUR_KIND = 8
STRAIGHT_FLUSH = 9


_CATEGORY_BY_PATTERN = {
    (2, 1, 1, 1): ONE_PAIR,
    (2, 2, 1): TWO_PAIR,
    (3, 1, 1): THREE_KIND,
    (3, 2): FULL_HOUSE,
    (4, 1): FOUR_KIND,
}


def _rank_value(card: int) -> int:
    # card_rank returns 0-12 (2 -> 0, A -> 12); the encoding uses 2-14.
    return card_rank(card) + 2


def _straight_top(unique_ranks_desc: list[int]) -> int:
    """Top card of the straight, or 0 if not one. Input: 5 unique ranks, descending."""
    if unique_ranks_desc == [14, 5, 4, 3, 2]:
        return 5  # wheel: ace plays low
    if unique_ranks_desc[0] - unique_ranks_desc[4] == 4:
        return unique_ranks_desc[0]
    return 0


def _pack(category: int, tiebreaks: list[int]) -> int:
    score = category
    for tb in tiebreaks:
        score = (score << 4) | tb
    return score


def encode_hand(five_cards: list[int]) -> int:
    """Encode a 5-card hand as a comparable integer."""
    ranks = [_rank_value(c) for c in five_cards]
    counts_by_rank = Counter(ranks)
    ranks_by_count = sorted(counts_by_rank.items(), key=lambda kv: (-kv[1], -kv[0]))
    pattern = tuple(count for _, count in ranks_by_count)

    if pattern == (1, 1, 1, 1, 1):
        is_flush = len({card_suit(c) for c in five_cards}) == 1
        ranks_desc = sorted(ranks, reverse=True)
        top = _straight_top(ranks_desc)
        if top and is_flush:
            return _pack(STRAIGHT_FLUSH, [top, 0, 0, 0, 0])
        if is_flush:
            return _pack(FLUSH, ranks_desc)
        if top:
            return _pack(STRAIGHT, [top, 0, 0, 0, 0])
        return _pack(HIGH_CARD, ranks_desc)

    category = _CATEGORY_BY_PATTERN[pattern]
    tiebreaks = [rank for rank, _ in ranks_by_count]
    tiebreaks += [0] * (5 - len(tiebreaks))
    return _pack(category, tiebreaks)


def evaluate(cards: list[int]) -> int:
    """Best score across all 5-card subsets of `cards` (5, 6, or 7 supported)."""
    return max(encode_hand(list(combo)) for combo in combinations(cards, 5))


_WHEEL = frozenset({14, 5, 4, 3, 2})


def _find_straight_top(ranks) -> int | None:
    """Top card of the highest straight in `ranks`, or None. Repeats are fine."""
    distinct = sorted(set(ranks), reverse=True)
    # Within a descending run of distinct values, a span of 4 across a 5-window
    # can only mean the five are consecutive. Scanning from the top means the
    # first hit is the best straight.
    for i in range(len(distinct) - 4):
        if distinct[i] - distinct[i + 4] == 4:
            return distinct[i]
    if _WHEEL.issubset(distinct):
        return 5  # ace plays low
    return None


def evaluate_fast(cards: list[int]) -> int:
    """Best score for 5-7 cards, in one pass. Same scale as `evaluate`."""
    # Ranks are small dense ints, so a flat tally beats a dict: no hashing and
    # no allocation. card_rank/card_suit are inlined below; this loop is hot.
    tally = [0] * 15
    for c in cards:
        tally[c // 4 + 2] += 1

    # A single descending pass over the rank domain yields both the distinct
    # ranks in order and the count buckets, so nothing below has to sort.
    ranks_desc = []
    by_count = ([], [], [], [], [])
    for r in range(14, 1, -1):
        n = tally[r]
        if n:
            ranks_desc.append(r)
            by_count[n].append(r)
    quads, trips, pairs = by_count[4], by_count[3], by_count[2]

    # Quads and full houses leave at most 4 distinct ranks, and both a flush and
    # a straight need 5 - so nothing can outrank these. Skip both checks.
    if quads:
        quad = quads[0]
        kicker = ranks_desc[0] if ranks_desc[0] != quad else ranks_desc[1]
        return _pack(FOUR_KIND, [quad, kicker, 0, 0, 0])

    if trips and (len(trips) > 1 or pairs):
        # The pair slot needs a rank held at least twice: a second trip counts,
        # a lone high card does not (KKK 333 A is kings full of threes).
        return _pack(FULL_HOUSE, [trips[0], max(trips[1:] + pairs), 0, 0, 0])

    # Out of 7 cards only one suit can reach 5, so the first match is the only
    # flush candidate - no need to compare across suits.
    suit_counts = [0, 0, 0, 0]
    for c in cards:
        suit_counts[c % 4] += 1
    for suit, n in enumerate(suit_counts):
        if n >= 5:
            suited = sorted(
                (c // 4 + 2 for c in cards if c % 4 == suit), reverse=True
            )
            top = _find_straight_top(suited)
            if top:
                return _pack(STRAIGHT_FLUSH, [top, 0, 0, 0, 0])
            return _pack(FLUSH, suited[:5])

    # ranks_desc is already deduped and descending - what the scan wants.
    top = _find_straight_top(ranks_desc)
    if top:
        return _pack(STRAIGHT, [top, 0, 0, 0, 0])

    if trips:
        trip = trips[0]
        kickers = [r for r in ranks_desc if r != trip][:2]
        return _pack(THREE_KIND, [trip, *kickers, 0, 0])

    if len(pairs) >= 2:
        # The kicker may be a third pair's rank, so pick it by rank alone.
        high, low = pairs[0], pairs[1]
        kicker = next(r for r in ranks_desc if r != high and r != low)
        return _pack(TWO_PAIR, [high, low, kicker, 0, 0])

    if pairs:
        pair = pairs[0]
        kickers = [r for r in ranks_desc if r != pair][:3]
        return _pack(ONE_PAIR, [pair, *kickers, 0])

    return _pack(HIGH_CARD, ranks_desc[:5])
