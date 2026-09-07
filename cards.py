RANKS = "23456789TJQKA"
SUITS = "cdhs"


def card_rank(card: int) -> int:
    return card // 4


def card_suit(card: int) -> int:
    return card % 4


def card_to_str(card: int) -> str:
    return RANKS[card_rank(card)] + SUITS[card_suit(card)]


def str_to_card(s: str) -> int:
    return RANKS.index(s[0]) * 4 + SUITS.index(s[1])


def build_deck() -> list[int]:
    return list(range(52))
