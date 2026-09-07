# Monte Carlo Poker Estimator

Texas hold'em equity calculator for 2–9 players, with a browser UI.
Pure standard library — the only dependency is `pytest`, for the tests.

```
python server.py          # then open http://localhost:8000
python -m pytest tests/   # 100 tests
```

Run `server.py` from the project root; it imports `simulator` as a sibling module.

---

## The one idea worth knowing

**Exact enumeration everywhere except preflop.** How many boards are left to deal
collapses the moment the flop lands:

| players | preflop | flop | turn | river |
|---------|-----------|------|------|-------|
| 2       | 1,712,304 | 990  | 44   | 1     |
| 9       |   278,256 | 465  | 30   | 1     |

Post-flop there are at most 990 possible runouts, so trying *every* one is both
faster than sampling and free of error. Measured on the flop:

| players | exact       | Monte Carlo, n=1,000 | Monte Carlo, n=20,000 |
|---------|-------------|----------------------|------------------------|
| 2       | **17 ms**, 0 error | 21 ms, ±0.028   | 256 ms, ±0.007         |
| 9       | **64 ms**, 0 error | 153 ms, ±0.029  | 2,757 ms, ±0.006       |

Exact beats even 1,000-trial sampling, and its edge *widens* with more players:
more hole cards means fewer cards left in the deck, so runouts drop while
Monte Carlo still pays for every trial.

Preflop is 300–1,700× larger, and it is the only street where sampling earns its
keep. `equities_auto` and `outcomes_auto` make that choice for you.

---

## Layout

| file | what it does |
|------|--------------|
| `cards.py` | Cards are ints `0–51`. `rank = card // 4`, `suit = card % 4`. |
| `evaluator.py` | Scores a hand as a comparable int. |
| `simulator.py` | Equity across runouts, for any number of players. |
| `server.py` | Stdlib HTTP server: static page + `POST /api/equity`. |
| `static/index.html` | The UI. Self-contained, no build step. |
| `tests/` | 100 tests. |

---

## Evaluator

A hand becomes a single integer, packed as six nibbles:

```
[category][tb1][tb2][tb3][tb4][tb5]
```

Category 1–9 (high card → straight flush) sits in the top nibble, tiebreak ranks
below it in order of significance. Plain `>` then gives both category dominance
and kicker-by-kicker comparison, with no special-case comparison logic anywhere.

Two implementations, both kept on purpose:

- **`evaluate(cards)`** — the reference. Tries all `C(7,5) = 21` five-card
  subsets and takes the max. Obviously correct, slow. **Not used in production
  any more; it exists as the test oracle.** Do not delete it.
- **`evaluate_fast(cards)`** — one pass over all 7 cards. **~25× faster**
  (≈5 µs vs ≈112 µs per 7-card hand).

`evaluate_fast` counts ranks with a flat 15-slot array rather than a `Counter`.
The win is not just skipping the hashing: walking the rank domain downward
(`range(14, 1, -1)`) yields the distinct ranks *already sorted* alongside the
count buckets, which removes both sorts the dict version needed.

Three things in it that are easy to get wrong:

- **Quads and full houses skip the flush and straight checks entirely.** Safe
  because those patterns leave at most 4 distinct ranks and both a flush and a
  straight need 5. Not a heuristic — exact.
- **The straight scan must run on deduped ranks.** On raw sorted ranks the
  "span of 4 across a 5-window" test fails both ways: `9 9 8 6 5 3 2` reports a
  straight that isn't there, and `9 8 8 7 7 6 5` misses a real one.
- **The full-house pair must come from a rank held twice.** `KKK 333 A` is kings
  full of *threes*; the ace is the highest spare rank but cannot fill a pair.

`evaluate_fast` is verified against `evaluate` on thousands of random hands
(`tests/test_evaluator_fast.py`) — including a rank-restricted deck sweep,
because straight flushes come up only ~3 times in 5,000 random full-deck hands
and the rarest paths would otherwise go untested.

---

## Simulator

```python
from cards import str_to_card as card
from simulator import equities_auto, outcomes_auto

hero    = [card("As"), card("Ah")]
villain = [card("Ks"), card("Kd")]

equities_auto([hero, villain])                          # preflop, sampled
equities_auto([hero, villain], board=[card("2c"), card("7d"), card("9h")])
```

| function | returns |
|----------|---------|
| `equities_auto(hands, board, n, seed)` | equity per hand — **start here** |
| `outcomes_auto(hands, board, n, seed)` | `{equity, win, chop, lose, stderr}` per hand |
| `equity_auto(hero, villain, ...)` | two-player convenience, hero's share |
| `equities` / `equities_exact` | force sampling / force enumeration |
| `equity` / `equity_exact` | two-player versions of those |

`n` and `seed` are consulted **only preflop** — post-flop results are exact and
identical across seeds.

### Ties

Each trial distributes exactly `1.0`, split evenly among the best hands, so
per-hand shares always sum to the trial count. Heads-up this is the familiar
0.5 each; three-handed, two players can chop while the third gets nothing.

### Equity hides the tie rate

Equity folds wins and chops together, which can make very different hands look
identical:

| | equity | win | chop |
|---|--------|-----|------|
| `8♠8♥` vs `8♦8♣` preflop | 50.0% | **2.2%** | **95.7%** |
| `K♣Q♥` vs `A♥4♥` on `7♣T♥J♣` | 49.6% | **49.6%** | **0.0%** |

Same equity, opposite hands — one almost never wins a pot outright, the other
never shares one. `outcomes_auto` reports both, and the UI shows them.

(The 88 vs 88 figures are exact, from all 1,712,304 runouts. Hero wins outright
37,210 times and loses 37,210 — identical, since the hands are mirror images.
Every one of those wins is a flush or straight flush: the ranks are identical,
so only suit can break the tie.)

### Reading a preflop number

Preflop is sampled, so it wobbles. At the default 25,000 trials the standard
error on 88 vs 88 is ~0.07 points, and a displayed 50.2 / 49.8 is ordinary
noise, not a bug. `outcomes_auto` returns `stderr` per hand, computed from the
observed spread of per-trial shares rather than the textbook
`sqrt(p(1-p)/n)` — which would report ±0.32% here, roughly 5× too pessimistic,
because chopped pots contribute almost no variance.

| trials | std. error | preflop time (3-way) |
|--------|-----------|----------------------|
| 10,000 | ±0.11 pts | ~0.2 s |
| 25,000 | ±0.07 pts | ~0.6 s |
| 100,000 | ±0.03 pts | ~1.8 s |

### Validation

`equities_auto` and `outcomes_auto` raise `ValueError` before doing any work if
a card appears twice — within one hand, across two hands, or between a hand and
the board — naming both places it came from (`"As appears in both hand 1 and hand 2"`),
so a UI can point at the offending seat. Also rejects out-of-range
card indices, fewer than two hands, and boards over five cards.

---

## Web UI

Click an empty slot to open the card picker; cards already in play are greyed
out, so duplicates cannot be created in the first place. Click a placed card —
it turns red with an × — to remove it. Cards stay where they are: a removed
board card leaves a hole, and the board is flagged invalid until it is filled.

`Calculate` unlocks only for a legal deal: every hand complete, and the board
contiguous with 0, 3, 4, or 5 cards. That also stops the app from asking for an
exact solve on a 1- or 2-card board, which would enumerate `C(45,4)` runouts for
a board no street can produce.

Each seat shows equity, a bar, and `Win x% · Chop y%`. A badge under the table
says whether the answer was exact or estimated, and with what margin.

---

## Tests

```
python -m pytest tests/ -q      # 100 tests, ~20 s
```

The load-bearing one is the differential test: `evaluate_fast` is checked
against `evaluate` on thousands of random hands. That is what makes the fast
evaluator safe to change — the entire rank-count dispatch was rewritten from a
`Counter` to an array with the differential test as the only safety net.

Keep `evaluate` around. It is dead code in production and live code in the tests.
