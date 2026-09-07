import pytest
from cards import card_to_str, str_to_card, build_deck, RANKS, SUITS


# --- card_to_str ---

def test_lowest_card():
    assert card_to_str(0) == "2c"


def test_highest_card():
    assert card_to_str(51) == "As"


def test_ace_of_hearts():
    assert card_to_str(str_to_card("Ah")) == "Ah"


def test_known_spot_checks():
    assert card_to_str(str_to_card("Qs")) == "Qs"
    assert card_to_str(str_to_card("Td")) == "Td"
    assert card_to_str(str_to_card("2h")) == "2h"


# --- str_to_card ---

def test_str_to_card_range():
    for rank in RANKS:
        for suit in SUITS:
            c = str_to_card(rank + suit)
            assert 0 <= c <= 51


def test_rank_encoding():
    # rank = card // 4
    assert str_to_card("2c") // 4 == 0
    assert str_to_card("Ac") // 4 == 12


def test_suit_encoding():
    # suit = card % 4
    assert str_to_card("2c") % 4 == SUITS.index("c")
    assert str_to_card("2h") % 4 == SUITS.index("h")
    assert str_to_card("2s") % 4 == SUITS.index("s")


def test_invalid_rank_raises():
    with pytest.raises((ValueError, IndexError)):
        str_to_card("Xc")


def test_invalid_suit_raises():
    with pytest.raises((ValueError, IndexError)):
        str_to_card("Ax")


# --- round-trip ---

def test_round_trip_all_cards():
    for card in range(52):
        assert str_to_card(card_to_str(card)) == card


def test_round_trip_all_strings():
    for rank in RANKS:
        for suit in SUITS:
            s = rank + suit
            assert card_to_str(str_to_card(s)) == s


# --- build_deck ---

def test_deck_length():
    assert len(build_deck()) == 52


def test_deck_unique():
    deck = build_deck()
    assert len(set(deck)) == 52


def test_deck_range():
    assert set(build_deck()) == set(range(52))
