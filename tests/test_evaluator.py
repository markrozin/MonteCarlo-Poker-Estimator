from cards import str_to_card
from evaluator import (
    encode_hand,
    evaluate,
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


# --- category classification ---

def test_high_card_category():
    assert category_of(encode_hand(hand("As", "Kh", "Qd", "Jc", "9s"))) == HIGH_CARD


def test_one_pair_category():
    assert category_of(encode_hand(hand("As", "Ah", "Kd", "Qc", "Js"))) == ONE_PAIR


def test_two_pair_category():
    assert category_of(encode_hand(hand("As", "Ah", "Kd", "Kc", "Qs"))) == TWO_PAIR


def test_trips_category():
    assert category_of(encode_hand(hand("As", "Ah", "Ad", "Kc", "Qs"))) == THREE_KIND


def test_straight_category():
    assert category_of(encode_hand(hand("9s", "Th", "Jd", "Qc", "Ks"))) == STRAIGHT


def test_flush_category():
    assert category_of(encode_hand(hand("2s", "5s", "7s", "9s", "Ks"))) == FLUSH


def test_full_house_category():
    assert category_of(encode_hand(hand("As", "Ah", "Ad", "Kc", "Ks"))) == FULL_HOUSE


def test_quads_category():
    assert category_of(encode_hand(hand("As", "Ah", "Ad", "Ac", "Kd"))) == FOUR_KIND


def test_straight_flush_category():
    assert category_of(encode_hand(hand("9s", "Ts", "Js", "Qs", "Ks"))) == STRAIGHT_FLUSH


# --- higher hand wins within same category ---

def test_higher_pair_beats_lower_pair():
    # AA228 vs KK228 — same kickers, aces beat kings
    aa = encode_hand(hand("As", "Ah", "2c", "2d", "8s"))
    kk = encode_hand(hand("Ks", "Kh", "2c", "2d", "8s"))
    # Note: AA228 is two pair (aces and twos with 8 kicker). Test that two-pair
    # aces-high beats two-pair kings-high with the same lower pair and kicker.
    assert aa > kk


def test_pair_kicker_matters():
    high_kicker = encode_hand(hand("As", "Ah", "Kd", "Qc", "Js"))
    low_kicker = encode_hand(hand("As", "Ah", "Kd", "Qc", "9s"))
    assert high_kicker > low_kicker


def test_full_house_trips_rank_dominates_pair_rank():
    # KKKQQ (kings full of queens) beats QQQAA (queens full of aces).
    kings_full = encode_hand(hand("Ks", "Kh", "Kd", "Qc", "Qs"))
    queens_full = encode_hand(hand("Qs", "Qh", "Qd", "As", "Ah"))
    assert kings_full > queens_full


def test_higher_flush_beats_lower_flush():
    ace_high = encode_hand(hand("As", "Ts", "8s", "5s", "3s"))
    king_high = encode_hand(hand("Ks", "Ts", "8s", "5s", "3s"))
    assert ace_high > king_high


def test_higher_straight_beats_lower_straight():
    broadway = encode_hand(hand("Ts", "Jh", "Qd", "Kc", "As"))
    nine_high = encode_hand(hand("5s", "6h", "7d", "8c", "9s"))
    assert broadway > nine_high


# --- category dominance ---

def test_lowest_two_pair_beats_highest_one_pair():
    low_two_pair = encode_hand(hand("2s", "2h", "3d", "3c", "4s"))
    high_pair = encode_hand(hand("As", "Ah", "Kd", "Qc", "Js"))
    assert low_two_pair > high_pair
    assert category_of(low_two_pair) == TWO_PAIR
    assert category_of(high_pair) == ONE_PAIR


def test_straight_flush_beats_quads():
    sf = encode_hand(hand("2s", "3s", "4s", "5s", "6s"))
    quads = encode_hand(hand("As", "Ah", "Ad", "Ac", "Kd"))
    assert sf > quads


# --- the wheel ---

def test_wheel_is_five_high_straight():
    wheel = encode_hand(hand("As", "2h", "3d", "4c", "5s"))
    assert category_of(wheel) == STRAIGHT
    # tb1 (top card) is at bits 16-19
    assert ((wheel >> 16) & 0xF) == 5


def test_wheel_loses_to_six_high_straight():
    wheel = encode_hand(hand("As", "2h", "3d", "4c", "5s"))
    six_high = encode_hand(hand("2s", "3h", "4d", "5c", "6s"))
    assert wheel < six_high


def test_wheel_straight_flush():
    steel_wheel = encode_hand(hand("As", "2s", "3s", "4s", "5s"))
    assert category_of(steel_wheel) == STRAIGHT_FLUSH
    assert ((steel_wheel >> 16) & 0xF) == 5


# --- exact ties ---

def test_identical_best_five_from_different_seven():
    # Both 7-card hands share the same best 5: A A K K Q (two pair, queen kicker)
    seven_a = hand("As", "Ah", "Kc", "Kd", "Qs", "2c", "3d")
    seven_b = hand("As", "Ah", "Kc", "Kd", "Qs", "4h", "5c")
    assert evaluate(seven_a) == evaluate(seven_b)


# --- 7-card evaluation picks the right subset ---

def test_evaluate_picks_best_when_using_only_one_hole_card():
    # Hole cards: A♠ 2♣. Board: K♠ Q♠ J♠ T♠ 5♦.
    # Best 5 = A♠ K♠ Q♠ J♠ T♠ (royal flush) — uses only A♠ from hole; 2♣ is
    # worthless. A naive "use both hole cards" approach would miss this.
    seven = hand("As", "2c", "Ks", "Qs", "Js", "Ts", "5d")
    score = evaluate(seven)
    expected = encode_hand(hand("As", "Ks", "Qs", "Js", "Ts"))
    assert score == expected
    assert category_of(score) == STRAIGHT_FLUSH


def test_evaluate_plays_the_board():
    # Hole cards are irrelevant; the board itself is a straight flush.
    seven = hand("2c", "3d", "9s", "Ts", "Js", "Qs", "Ks")
    score = evaluate(seven)
    expected = encode_hand(hand("9s", "Ts", "Js", "Qs", "Ks"))
    assert score == expected
    assert category_of(score) == STRAIGHT_FLUSH
