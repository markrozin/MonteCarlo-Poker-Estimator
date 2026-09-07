import random

import pytest

from cards import str_to_card
from simulator import (
    equity,
    equity_exact,
    equities,
    equities_exact,
    equities_auto,
    equity_auto,
    outcomes_auto,
    _simulate_counts,
)


def hand(*strings):
    return [str_to_card(s) for s in strings]


# --- sample vs exact agreement ---

def test_sample_matches_exact_on_turn():
    # AA vs KK with 4 board cards — only 44 possible rivers, cheap to enumerate.
    hero = hand("As", "Ah")
    villain = hand("Ks", "Kd")
    turn = hand("2c", "7d", "Td", "Jc")
    exact = equity_exact(hero, villain, board=turn)
    sampled = equity(hero, villain, board=turn, n=50_000, seed=1)
    assert abs(exact - sampled) < 0.02


# --- known preflop benchmarks (published equities ~82% / ~46% / ~43%) ---

def test_aa_vs_kk_benchmark():
    eq = equity(hand("As", "Ad"), hand("Ks", "Kd"), n=200_000, seed=42)
    assert abs(eq - 0.82) < 0.01


def test_aks_vs_qq_benchmark():
    eq = equity(hand("As", "Ks"), hand("Qh", "Qd"), n=200_000, seed=42)
    assert abs(eq - 0.46) < 0.01


def test_ako_vs_qq_benchmark():
    eq = equity(hand("As", "Kh"), hand("Qc", "Qd"), n=200_000, seed=42)
    assert abs(eq - 0.43) < 0.01


# --- symmetry ---

def test_hero_and_villain_wins_sum_to_n():
    # Derived from a single simulation so integer/half-integer counts sum exactly.
    # (Verifying the sum through two float equities isn't exact due to /n rounding.)
    hero = hand("As", "Ah")
    villain = hand("Ks", "Kh")
    n = 10_000
    wins = _simulate_counts([hero, villain], [], n, random.Random(42))
    assert sum(wins) == n


# --- river short-circuit: no sampling needed ---

def test_river_hero_wins_returns_one():
    # Board: 2 3 4 6 7 (no straight/flush). Hero AA plays pair of aces; villain KK
    # plays pair of kings. Hero wins outright, no cards to come.
    hero = hand("As", "Ah")
    villain = hand("Ks", "Kh")
    river = hand("2c", "3d", "4h", "6s", "7c")
    assert equity(hero, villain, board=river, n=500) == 1.0


def test_river_hero_loses_returns_zero():
    # Villain pairs aces; hero's 2-3 don't improve on board's high card.
    hero = hand("2c", "3d")
    villain = hand("As", "Ah")
    river = hand("5c", "6d", "7h", "Ks", "Qc")
    assert equity(hero, villain, board=river, n=500) == 0.0


def test_river_tie_returns_half():
    # Royal flush on board (all clubs). Both players play the board.
    hero = hand("2d", "3d")
    villain = hand("4h", "5s")
    river = hand("Ac", "Kc", "Qc", "Jc", "Tc")
    assert equity(hero, villain, board=river, n=500) == 0.5


# --- reproducibility ---

def test_same_seed_same_result():
    hero = hand("As", "Kh")
    villain = hand("Qc", "Qd")
    a = equity(hero, villain, n=5_000, seed=99)
    b = equity(hero, villain, n=5_000, seed=99)
    assert a == b


# --- multiway ---

def test_equities_sum_to_one():
    hands = [hand("As", "Ad"), hand("Ks", "Kd"), hand("Qh", "Qc")]
    result = equities(hands, n=20_000, seed=7)
    assert abs(sum(result) - 1.0) < 1e-9
    assert len(result) == 3


def test_equity_wrapper_matches_equities_first_entry():
    hero, villain = hand("As", "Ks"), hand("Qh", "Qd")
    assert equity(hero, villain, n=10_000, seed=3) == equities(
        [hero, villain], n=10_000, seed=3
    )[0]


def test_three_way_all_in_preflop_benchmark():
    # AA vs KK vs QQ. Full enumeration of all C(46,5) runouts gives
    # 0.66511 / 0.16721 / 0.16768 -- KK and QQ land nearly level three-way.
    result = equities(
        [hand("As", "Ad"), hand("Ks", "Kd"), hand("Qh", "Qc")],
        n=200_000,
        seed=42,
    )
    assert abs(result[0] - 0.66511) < 0.01
    assert abs(result[1] - 0.16721) < 0.01
    assert abs(result[2] - 0.16768) < 0.01


def test_three_way_sampled_matches_exact_on_turn():
    hands = [hand("As", "Ah"), hand("Ks", "Kd"), hand("7c", "7h")]
    turn = hand("2c", "9d", "Td", "Jc")
    exact = equities_exact(hands, board=turn)
    sampled = equities(hands, board=turn, n=50_000, seed=1)
    for e, s in zip(exact, sampled):
        assert abs(e - s) < 0.02


def test_three_way_chop_when_everyone_plays_the_board():
    # Board is a royal flush: nothing can beat it and no hole card improves it,
    # so all three players chop.
    board = hand("As", "Ks", "Qs", "Js", "Ts")
    hands = [hand("2c", "3d"), hand("4h", "5c"), hand("6d", "7h")]
    result = equities(hands, board=board, n=500)
    assert result == [1 / 3, 1 / 3, 1 / 3]


def test_two_of_three_chop_leaves_third_with_nothing():
    # Both ace hands play A A K J 9; the third player has only king high.
    board = hand("2c", "7d", "9h", "Js", "Kc")
    hands = [hand("As", "Ad"), hand("Ah", "Ac"), hand("3s", "4d")]
    assert equities(hands, board=board, n=500) == [0.5, 0.5, 0.0]


def test_win_counts_sum_to_n_four_way():
    hands = [
        hand("As", "Ah"),
        hand("Ks", "Kh"),
        hand("Qs", "Qh"),
        hand("Js", "Jh"),
    ]
    n = 5_000
    wins = _simulate_counts(hands, [], n, random.Random(42))
    assert sum(wins) == n
    assert len(wins) == 4


def test_nine_way_runs_and_sums_to_one():
    deck_hands = [
        hand("As", "Ah"), hand("Ks", "Kh"), hand("Qs", "Qh"),
        hand("Js", "Jh"), hand("Ts", "Th"), hand("9s", "9h"),
        hand("8s", "8h"), hand("7s", "7h"), hand("6s", "6h"),
    ]
    result = equities(deck_hands, n=5_000, seed=5)
    assert len(result) == 9
    assert abs(sum(result) - 1.0) < 1e-9
    # Aces are still the favourite nine-handed, but far from a lock.
    assert result[0] == max(result)
    assert result[0] < 0.5


# --- deal validation ---

def test_rejects_same_card_twice_in_one_hand():
    with pytest.raises(ValueError, match="As appears twice in hand 1"):
        equities([hand("As", "As"), hand("Kd", "Kc")], n=10)


def test_rejects_card_shared_between_hands():
    with pytest.raises(ValueError, match="As appears in both hand 1 and hand 2"):
        equities([hand("As", "Ad"), hand("As", "Kc")], n=10)


def test_rejects_hand_card_also_on_board():
    with pytest.raises(ValueError, match="As appears in both hand 1 and the board"):
        equities(
            [hand("As", "Ad"), hand("Kh", "Kc")], board=hand("As", "2c", "3d"), n=10
        )


def test_rejects_duplicate_on_the_board():
    with pytest.raises(ValueError, match="2c appears twice in the board"):
        equities(
            [hand("As", "Ad"), hand("Kh", "Kc")], board=hand("2c", "2c", "3d"), n=10
        )


def test_rejects_fewer_than_two_hands():
    with pytest.raises(ValueError, match="need at least 2 hands"):
        equities([hand("As", "Ad")], n=10)


def test_rejects_out_of_range_card_index():
    with pytest.raises(ValueError, match="outside 0-51"):
        equities([[52, 3], hand("Kd", "Kc")], n=10)


def test_rejects_oversized_board():
    with pytest.raises(ValueError, match="at most 5 cards"):
        equities(
            [hand("As", "Ad"), hand("Kh", "Kc")],
            board=hand("2c", "3d", "4h", "5s", "6c", "7d"),
            n=10,
        )


def test_exact_path_validates_too():
    with pytest.raises(ValueError, match="As appears in both hand 1 and hand 2"):
        equities_exact(
            [hand("As", "Ad"), hand("As", "Kc")], board=hand("2c", "3d", "4h", "5s")
        )


def test_heads_up_wrappers_validate():
    with pytest.raises(ValueError, match="As appears in both hand 1 and hand 2"):
        equity(hand("As", "Ad"), hand("As", "Kc"), n=10)
    with pytest.raises(ValueError, match="As appears in both hand 1 and hand 2"):
        equity_exact(
            hand("As", "Ad"), hand("As", "Kc"), board=hand("2c", "3d", "4h", "5s")
        )


def test_valid_deal_still_accepted():
    result = equities([hand("As", "Ad"), hand("Kh", "Kc")], n=500, seed=1)
    assert abs(sum(result) - 1.0) < 1e-9


# --- street-aware dispatch ---

def test_auto_matches_exact_on_flop_turn_and_river():
    hands = [hand("As", "Ah"), hand("Ks", "Kd"), hand("7c", "7h")]
    flop = hand("2c", "9d", "Td")
    for board in (flop, flop + hand("Jc"), flop + hand("Jc", "4s")):
        assert equities_auto(hands, board=board) == equities_exact(hands, board=board)


def test_auto_is_deterministic_post_flop_regardless_of_seed():
    hands = [hand("As", "Ah"), hand("Ks", "Kd")]
    flop = hand("2c", "9d", "Td")
    assert equities_auto(hands, board=flop, seed=1) == equities_auto(
        hands, board=flop, seed=999
    )


def test_auto_samples_preflop():
    hands = [hand("As", "Ah"), hand("Ks", "Kd")]
    assert equities_auto(hands, n=5_000, seed=8) == equities(hands, n=5_000, seed=8)


def test_auto_validates_the_deal():
    with pytest.raises(ValueError, match="As appears in both hand 1 and hand 2"):
        equities_auto([hand("As", "Ad"), hand("As", "Kc")], board=hand("2c", "3d", "4h"))


def test_equity_auto_two_player_wrapper():
    hero, villain = hand("As", "Ah"), hand("Ks", "Kd")
    flop = hand("2c", "9d", "Td")
    assert equity_auto(hero, villain, board=flop) == equities_exact(
        [hero, villain], board=flop
    )[0]


# --- win / chop / lose breakdown ---

def test_outcome_fractions_sum_to_one_per_hand():
    result = outcomes_auto(
        [hand("As", "Ah"), hand("Ks", "Kd"), hand("7c", "7h")],
        board=hand("2c", "9d", "Td"),
    )
    for o in result:
        assert abs(o["win"] + o["chop"] + o["lose"] - 1.0) < 1e-9


def test_outcome_equity_matches_equities_auto():
    hands = [hand("As", "Ah"), hand("Ks", "Kd"), hand("7c", "7h")]
    flop = hand("2c", "9d", "Td")
    detailed = outcomes_auto(hands, board=flop)
    plain = equities_auto(hands, board=flop)
    for o, e in zip(detailed, plain):
        assert o["equity"] == e


def test_identical_pairs_almost_always_chop():
    # 8s8h vs 8d8c: the ranks are identical, so only a flush can break the tie.
    # Over every runout from this rainbow flop the chop rate stays very high.
    result = outcomes_auto(
        [hand("8s", "8h"), hand("8d", "8c")], board=hand("2c", "7d", "Kh")
    )
    assert result[0]["chop"] > 0.85
    assert result[0]["chop"] == result[1]["chop"]
    # Perfectly symmetric hands split the pot exactly down the middle.
    assert result[0]["equity"] == result[1]["equity"] == 0.5
    assert result[0]["win"] == result[1]["win"]


def test_equity_near_one_half_can_mean_two_different_things():
    # Both hands sit at ~50% equity but get there completely differently.
    # 88 vs 88 chops nearly every pot and almost never scoops.
    chopper = outcomes_auto(
        [hand("8s", "8h"), hand("8d", "8c")], board=hand("2c", "7d", "Kh")
    )[0]
    assert chopper["equity"] == 0.5
    assert chopper["chop"] > 0.85 and chopper["win"] < 0.10

    # KQ vs A4 is a coinflip that never chops - every pot goes to somebody.
    scooper = outcomes_auto(
        [hand("Qh", "Kc"), hand("4h", "Ah")], board=hand("7c", "Th", "Jc")
    )[0]
    assert abs(scooper["equity"] - 0.5) < 0.02
    assert scooper["chop"] == 0.0
    # With no chops at all, equity and outright win rate coincide exactly.
    assert scooper["equity"] == scooper["win"]


def test_three_way_partial_chop_counts_as_chop_not_win():
    # Two ace hands split; the third player loses outright.
    board = hand("2c", "7d", "9h", "Js", "Kc")
    result = outcomes_auto(
        [hand("As", "Ad"), hand("Ah", "Ac"), hand("3s", "4d")], board=board
    )
    assert result[0]["chop"] == 1.0 and result[0]["win"] == 0.0
    assert result[1]["chop"] == 1.0 and result[1]["win"] == 0.0
    assert result[2]["lose"] == 1.0
    assert result[0]["equity"] == result[1]["equity"] == 0.5
    assert result[2]["equity"] == 0.0


def test_outright_river_win_is_a_win_not_a_chop():
    board = hand("2c", "3d", "4h", "6s", "7c")
    result = outcomes_auto([hand("As", "Ah"), hand("Ks", "Kh")], board=board)
    assert result[0]["win"] == 1.0 and result[0]["chop"] == 0.0
    assert result[1]["lose"] == 1.0


def test_outcomes_validates_the_deal():
    with pytest.raises(ValueError, match="As appears in both hand 1 and hand 2"):
        outcomes_auto([hand("As", "Ad"), hand("As", "Kc")], board=hand("2c", "3d", "4h"))
