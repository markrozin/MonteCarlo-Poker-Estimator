"""
Monte Carlo (and exact) equity for Texas hold'em, for any number of players.

`equities` samples random runouts; `equities_exact` enumerates every remaining
runout. Both score every hand against the same board on each trial, so one pass
yields all players' equities at once.

A tie splits the pot evenly among the players holding the best hand: each trial
contributes exactly 1.0 spread across the winners, so the per-hand win counts
sum to the trial count exactly. Heads-up this reduces to the familiar 0.5 each.

`equities_auto` picks between them by street and is the recommended entry
point: from the flop on there are only 465-990 runouts left, so enumerating
every one is both faster than sampling and free of error. Preflop has 278k-1.7M,
which is the one street where sampling is the practical choice.

`equity` / `equity_exact` are two-player conveniences returning hero's share.
"""

import random
from itertools import combinations

from cards import build_deck, card_to_str
from evaluator import evaluate_fast


def _validate_deal(hands, board):
    """Raise ValueError if the deal is impossible. No card may appear twice."""
    if len(hands) < 2:
        raise ValueError(f"need at least 2 hands, got {len(hands)}")
    if len(board) > 5:
        raise ValueError(f"a board holds at most 5 cards, got {len(board)}")

    # One pass over every card in the deal; the first repeat names both places
    # it came from, so a UI can point at the offending seat.
    owner = {}
    groups = [(f"hand {i}", h) for i, h in enumerate(hands, 1)]
    groups.append(("the board", board))
    for label, cards in groups:
        for card in cards:
            if not isinstance(card, int) or isinstance(card, bool):
                raise ValueError(f"{card!r} in {label} is not a card index")
            if not 0 <= card < 52:
                raise ValueError(f"card index {card} in {label} is outside 0-51")
            if card in owner:
                where = (
                    f"twice in {label}"
                    if owner[card] == label
                    else f"in both {owner[card]} and {label}"
                )
                raise ValueError(f"{card_to_str(card)} appears {where}")
            owner[card] = label

    to_draw = 5 - len(board)
    remaining = 52 - len(owner)
    if to_draw > remaining:
        raise ValueError(
            f"not enough cards left to finish the board: "
            f"need {to_draw}, {remaining} remain"
        )


def _remaining_deck(hands, board):
    known = set(board)
    for hand in hands:
        known.update(hand)
    return [c for c in build_deck() if c not in known]


def _showdown_shares(hands, full_board):
    """Each hand's share of one pot: 1.0 for a lone winner, 1/k for a k-way chop."""
    scores = [evaluate_fast(list(hand) + full_board) for hand in hands]
    best = max(scores)
    share = 1.0 / scores.count(best)
    return [share if s == best else 0.0 for s in scores]


def _simulate_counts(hands, board, n, rng):
    """Sample `n` runouts. Returns per-hand win counts; their sum == n."""
    board = list(board or [])
    to_draw = 5 - len(board)
    if to_draw == 0:
        return [share * n for share in _showdown_shares(hands, board)]

    deck = _remaining_deck(hands, board)
    wins = [0.0] * len(hands)
    for _ in range(n):
        completed = board + rng.sample(deck, to_draw)
        for i, share in enumerate(_showdown_shares(hands, completed)):
            wins[i] += share
    return wins


def _enumerate_counts(hands, board):
    """Enumerate every remaining runout. Returns (per-hand win counts, total)."""
    board = list(board or [])
    to_draw = 5 - len(board)
    deck = _remaining_deck(hands, board)
    wins = [0.0] * len(hands)
    total = 0
    for runout in combinations(deck, to_draw):
        completed = board + list(runout)
        for i, share in enumerate(_showdown_shares(hands, completed)):
            wins[i] += share
        total += 1
    return wins, total


def equities(hands, board=None, n=100_000, seed=None):
    """Monte Carlo equity per hand, in the order given. Sums to 1.0."""
    board = list(board or [])
    _validate_deal(hands, board)
    rng = random.Random(seed)
    wins = _simulate_counts(hands, board, n, rng)
    return [w / n for w in wins]


def equities_exact(hands, board=None):
    """Exact equity per hand, enumerating every remaining runout."""
    board = list(board or [])
    _validate_deal(hands, board)
    wins, total = _enumerate_counts(hands, board)
    return [w / total for w in wins]


def equity(hero_cards, villain_cards, board=None, n=100_000, seed=None):
    """Monte Carlo hero equity vs one villain. Ties count as 0.5."""
    return equities([hero_cards, villain_cards], board, n, seed)[0]


def equity_exact(hero_cards, villain_cards, board=None):
    """Exact hero equity vs one villain by enumerating all remaining runouts."""
    return equities_exact([hero_cards, villain_cards], board)[0]


def equities_auto(hands, board=None, n=100_000, seed=None):
    """Equity per hand: exact from the flop on, sampled preflop.

    Post-flop the whole runout space is at most 990 boards, so enumeration beats
    sampling on both speed and accuracy -- and its edge widens as players are
    added, since more hole cards mean fewer cards left to deal. `n` and `seed`
    are therefore only consulted preflop.
    """
    board = list(board or [])
    _validate_deal(hands, board)
    if board:
        wins, total = _enumerate_counts(hands, board)
        return [w / total for w in wins]
    rng = random.Random(seed)
    return [w / n for w in _simulate_counts(hands, board, n, rng)]


def equity_auto(hero_cards, villain_cards, board=None, n=100_000, seed=None):
    """Two-player `equities_auto`, returning hero's share."""
    return equities_auto([hero_cards, villain_cards], board, n, seed)[0]


def _outcome_counts(hands, runouts):
    """Tally share/win/chop/lose per hand across an iterable of complete boards.

    A "win" is a pot taken outright; a "chop" is any pot shared with at least
    one other hand. Equity folds the two together, so it cannot tell a hand that
    scoops 50% of the time from one that chops every single pot.
    """
    count = len(hands)
    shares = [0.0] * count
    squares = [0.0] * count
    wins = [0] * count
    chops = [0] * count
    losses = [0] * count
    trials = 0
    for full_board in runouts:
        scores = [evaluate_fast(list(hand) + full_board) for hand in hands]
        best = max(scores)
        winners = scores.count(best)
        split = 1.0 / winners
        for i, score in enumerate(scores):
            if score != best:
                losses[i] += 1
            elif winners == 1:
                wins[i] += 1
                shares[i] += 1.0
                squares[i] += 1.0
            else:
                chops[i] += 1
                shares[i] += split
                squares[i] += split * split
        trials += 1
    return shares, squares, wins, chops, losses, trials


def outcomes_auto(hands, board=None, n=100_000, seed=None):
    """Per-hand {equity, win, chop, lose} fractions. Exact post-flop, as `equities_auto`.

    `win + chop + lose == 1` for every hand, and `equity == win + (shared pot
    fractions)`, so equity alone can look identical for very different hands.
    """
    board = list(board or [])
    _validate_deal(hands, board)
    to_draw = 5 - len(board)
    deck = _remaining_deck(hands, board)

    if board:
        runouts = (board + list(combo) for combo in combinations(deck, to_draw))
    else:
        rng = random.Random(seed)
        runouts = (board + rng.sample(deck, to_draw) for _ in range(n))

    shares, squares, wins, chops, losses, trials = _outcome_counts(hands, runouts)

    def stderr(i, mean):
        # Enumeration visits every runout, so its answer carries no error at all.
        # Sampling does: use the observed spread of per-trial shares rather than
        # a coin-flip approximation, which badly overstates it when pots chop.
        if board or trials < 2:
            return 0.0
        variance = max(squares[i] / trials - mean * mean, 0.0)
        return (variance / trials) ** 0.5

    results = []
    for i in range(len(hands)):
        mean = shares[i] / trials
        results.append({
            "equity": mean,
            "win": wins[i] / trials,
            "chop": chops[i] / trials,
            "lose": losses[i] / trials,
            "stderr": stderr(i, mean),
        })
    return results
