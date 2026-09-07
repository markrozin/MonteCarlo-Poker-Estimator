"""Tests for `evaluate_fast`, using `evaluate` as the correctness oracle."""

import random
import time

from cards import str_to_card, build_deck
from evaluator import (
    encode_hand,
    evaluate,
    evaluate_fast,
    HIGH_CARD,
    ONE_PAIR,
    TWO_PAIR,
    THREE_KIND,
    STRAIGHT,
    FLUSH,
    FULL_HOUSE,
    FOUR_KIND,
    STRAIGHT_FLUSH,
)


def hand(*strings: str) -> list[int]:
    return [str_to_card(s) for s in strings]


def category_of(score: int) -> int:
    return score >> 20


def top_card_of(score: int) -> int:
    # tb1 sits at bits 16-19
    return (score >> 16) & 0xF


def check(cards: list[int], category: int) -> int:
    """Assert fast == oracle and lands in `category`; return the score."""
    score = evaluate_fast(cards)
    assert score == evaluate(cards)
    assert category_of(score) == category
    return score


# --- differential test against the oracle (the important one) ---

def test_matches_oracle_on_random_seven_card_hands():
    rng = random.Random(20260831)
    deck = build_deck()
    for _ in range(5000):
        cards = rng.sample(deck, 7)
        assert evaluate_fast(cards) == evaluate(cards), [
            "%02d" % c for c in cards
        ]


def test_matches_oracle_on_random_five_and_six_card_hands():
    rng = random.Random(7)
    deck = build_deck()
    for n in (5, 6):
        for _ in range(2000):
            cards = rng.sample(deck, n)
            assert evaluate_fast(cards) == evaluate(cards), [
                "%02d" % c for c in cards
            ]


def test_matches_oracle_on_rank_restricted_decks():
    """A narrow rank window makes straights, flushes and quads common.

    Over a full deck a random 7-card hand is a straight flush about once in
    2000, so the rarest code paths are barely exercised above. Dealing from a
    7-rank slice concentrates them by two orders of magnitude.
    """
    rng = random.Random(4242)
    for low in range(0, 7):
        short_deck = [c for c in build_deck() if low <= c // 4 < low + 7]
        for _ in range(1500):
            cards = rng.sample(short_deck, 7)
            assert evaluate_fast(cards) == evaluate(cards), [
                "%02d" % c for c in cards
            ]


# --- one explicit case per 7-card rank pattern ---

def test_pattern_4_1_1_1_quads():
    score = check(hand("As", "Ah", "Ad", "Ac", "Kh", "Qd", "7s"), FOUR_KIND)
    assert score == encode_hand(hand("As", "Ah", "Ad", "Ac", "Kh"))


def test_pattern_4_2_1_quads_kicker_beats_the_pair():
    # Quad aces with a pair of threes and a lone king: the king is the kicker,
    # even though the pair sorts ahead of it by count.
    score = check(hand("As", "Ah", "Ad", "Ac", "3h", "3d", "Kc"), FOUR_KIND)
    assert score == encode_hand(hand("As", "Ah", "Ad", "Ac", "Kc"))


def test_pattern_4_3_quads():
    score = check(hand("As", "Ah", "Ad", "Ac", "3h", "3d", "3c"), FOUR_KIND)
    assert score == encode_hand(hand("As", "Ah", "Ad", "Ac", "3h"))


def test_pattern_3_3_1_full_house_from_two_trips():
    # Two trips plus a lone ace: kings full of threes. The ace cannot pair.
    score = check(hand("Ks", "Kh", "Kd", "3s", "3h", "3d", "Ac"), FULL_HOUSE)
    assert score == encode_hand(hand("Ks", "Kh", "Kd", "3s", "3h"))


def test_pattern_3_2_1_1_full_house():
    score = check(hand("Ks", "Kh", "Kd", "3s", "3h", "Ac", "Qd"), FULL_HOUSE)
    assert score == encode_hand(hand("Ks", "Kh", "Kd", "3s", "3h"))


def test_pattern_3_2_2_full_house_takes_higher_pair():
    score = check(hand("Ks", "Kh", "Kd", "3s", "3h", "5c", "5d"), FULL_HOUSE)
    assert score == encode_hand(hand("Ks", "Kh", "Kd", "5c", "5d"))


def test_pattern_3_1_1_1_1_trips():
    score = check(hand("Ks", "Kh", "Kd", "3s", "7h", "9c", "Jd"), THREE_KIND)
    assert score == encode_hand(hand("Ks", "Kh", "Kd", "Jd", "9c"))


def test_pattern_2_2_2_1_three_pair_uses_top_two():
    # Three pairs (A, K, Q) plus a deuce: the queen pair is unused, but the
    # queen is still the best available kicker.
    score = check(hand("As", "Ah", "Ks", "Kh", "Qs", "Qh", "2d"), TWO_PAIR)
    assert score == encode_hand(hand("As", "Ah", "Ks", "Kh", "Qs"))


def test_pattern_2_2_2_1_kicker_can_be_the_odd_card():
    score = check(hand("As", "Ah", "Ks", "Kh", "3s", "3h", "7d"), TWO_PAIR)
    assert score == encode_hand(hand("As", "Ah", "Ks", "Kh", "7d"))


def test_pattern_2_2_1_1_1_two_pair():
    score = check(hand("As", "Ah", "Ks", "Kh", "3d", "7c", "9s"), TWO_PAIR)
    assert score == encode_hand(hand("As", "Ah", "Ks", "Kh", "9s"))


def test_pattern_2_1_1_1_1_1_one_pair():
    score = check(hand("As", "Ah", "Ks", "3d", "7c", "9h", "Jd"), ONE_PAIR)
    assert score == encode_hand(hand("As", "Ah", "Ks", "Jd", "9h"))


def test_pattern_1_1_1_1_1_1_1_high_card():
    score = check(hand("As", "Kh", "9d", "7c", "5s", "3h", "2d"), HIGH_CARD)
    assert score == encode_hand(hand("As", "Kh", "9d", "7c", "5s"))


# --- the wheel ---

def test_wheel_straight_scores_five_high():
    score = check(hand("As", "2h", "3d", "4c", "5s", "Kh", "Qd"), STRAIGHT)
    assert top_card_of(score) == 5


def test_wheel_straight_loses_to_six_high_straight():
    wheel = evaluate_fast(hand("As", "2h", "3d", "4c", "5s", "Kh", "Qd"))
    six_high = evaluate_fast(hand("2h", "3d", "4c", "5s", "6h", "Kd", "Qs"))
    assert wheel < six_high


def test_wheel_straight_flush_scores_five_high():
    score = check(hand("As", "2s", "3s", "4s", "5s", "Kh", "Qd"), STRAIGHT_FLUSH)
    assert top_card_of(score) == 5


def test_wheel_straight_flush_loses_to_six_high_straight_flush():
    steel_wheel = evaluate_fast(hand("As", "2s", "3s", "4s", "5s", "Kh", "Qd"))
    six_high = evaluate_fast(hand("2s", "3s", "4s", "5s", "6s", "Kh", "Qd"))
    assert steel_wheel < six_high


# --- flush / straight-flush traps ---

def test_flush_and_straight_present_but_no_straight_flush():
    # Spades K T 9 8 6 make a flush with no straight inside them. The board
    # also contains T-9-8-7-6, but the seven is a heart, so the straight spans
    # suits: this is a flush, not a straight flush.
    cards = hand("Ks", "Ts", "9s", "8s", "6s", "7h", "2d")
    score = check(cards, FLUSH)
    assert score == encode_hand(hand("Ks", "Ts", "9s", "8s", "6s"))
    assert score > evaluate_fast(hand("Ts", "9s", "8s", "7h", "6s"))


def test_straight_flush_in_a_sub_window_of_seven_suited_cards():
    # Seven spades: A K are too high to join the run, so the straight flush
    # lives in the 6-5-4-3-2 window, not the top five.
    score = check(hand("As", "Ks", "6s", "5s", "4s", "3s", "2s"), STRAIGHT_FLUSH)
    assert top_card_of(score) == 6


def test_straight_flush_in_a_sub_window_of_six_suited_cards():
    score = check(hand("Ks", "9s", "8s", "7s", "6s", "5s", "2d"), STRAIGHT_FLUSH)
    assert top_card_of(score) == 9


def test_six_suited_cards_without_a_straight_take_top_five():
    score = check(hand("Ks", "Js", "9s", "7s", "5s", "3s", "2d"), FLUSH)
    assert score == encode_hand(hand("Ks", "Js", "9s", "7s", "5s"))


def test_seven_suited_cards_without_a_straight_take_top_five():
    score = check(hand("As", "Ks", "Js", "9s", "7s", "5s", "3s"), FLUSH)
    assert score == encode_hand(hand("As", "Ks", "Js", "9s", "7s"))


# --- informational speed comparison ---

def test_speed_versus_oracle(capsys):
    rng = random.Random(99)
    deck = build_deck()
    hands = [rng.sample(deck, 7) for _ in range(2000)]

    start = time.perf_counter()
    slow = [evaluate(h) for h in hands]
    slow_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    fast = [evaluate_fast(h) for h in hands]
    fast_elapsed = time.perf_counter() - start

    assert slow == fast
    with capsys.disabled():
        print(
            f"\nevaluate: {slow_elapsed / len(hands) * 1e6:7.1f} us/hand"
            f"\nevaluate_fast: {fast_elapsed / len(hands) * 1e6:7.1f} us/hand"
            f"\nspeedup: {slow_elapsed / fast_elapsed:.1f}x"
        )
