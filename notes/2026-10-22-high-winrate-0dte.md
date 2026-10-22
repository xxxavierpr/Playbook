# QQQ 0DTE: 80%+ win rate that still nets positive

Xavier, 1 contract, premiums about $0.15–$0.60, session 8:30–14:45 CT. The bot already has 1m Heikin Ashi, EMA20 of close / high / low, VWAP, RSI14, MACD, and Bollinger (20, 2). Option P&L is the replay proxy: premium $0.30, delta 0.30, so $0.10 of QQQ is $3 (10% of premium). No theta in the proxy.

Sample is the attached file only: RTH 2026-10-21 (390 bars) and 2026-10-22 8:30–9:33 CT (64 bars). One day plus an hour. 13 wins in 14 tries has a 95% lower bound near 70%, so 80% is not established.

## Win rate vs payoff

Breakeven win rate = loss / (win + loss). Here a QQQ distance in points equals the option move as a fraction of the $0.30 premium.

| Take-profit | QQQ stop | Loss if that stop fills | Breakeven | Expectancy at 80% |
| --- | --- | --- | --- | --- |
| +8% ($2.40) | $0.20 | $6 (20%) | 71% | +$0.72 |
| +10% ($3.00) | $0.50 | $15 (50%) | 83% | −$0.60 |
| +10% ($3.00) | $0.30 | $9 (30%) | 75% | +$0.60 |
| +12% ($3.60) | $0.30 | $9 (30%) | 71% | +$1.08 |
| +12% ($3.60) | $0.50 | $15 (50%) | 81% | −$0.12 |
| +15% ($4.50) | $0.30 | $9 (30%) | 67% | +$1.80 |

The last replay is row 2: trend retest, +10% target, −50% option stop, 13/14 (93%, +$24). 93% clears an 83% breakeven, which is why that run made $24, and why 75% on the same pair loses about $1.50 a trade. One full stop erases five +10% wins.

What to change, and why it is specific to 0DTE:

- Theta. A −50% stop is $0.15 of premium, about $0.50 of QQQ at this delta. A cheap 0DTE contract can give a large share of that back over a flat 15–30 minutes. In this file the 13:35 call sat near flat and only printed −$15 at minute 12 (13:47). A 5-minute exit on that same trade is −$2.10.
- Spread. QQQ is a penny wide. A $0.30 option is often $0.01–$0.03 wide, 3–10% of premium, the same size as an +8–10% target. A tight stop on the option sits in the quote. Put the stop on the QQQ print and sell the option when the print hits. Tables below also show a $2 haircut (one cent in, one cent out).

Median 1m range here is $0.31 (75th percentile $0.52). A QQQ stop of $0.12–$0.22 plus a $0.08–$0.12 target often sits inside one bar. The fill rule takes the stop before the target, and those cells won 60–71%, under 80%, and lost money after the $2 haircut.

## Candidates

Regime matches the harness: CHOPPY when close crosses EMA20 at least 4 times in 20 bars, else TRENDING. BULL means close > VWAP and the 5-bar EMA slope is up; BEAR means both are down. Signals on the bar close, from 8:45 to 14:30 CT, one contract, flat by 14:45. Same-bar rule: stop touch exits before a target touch. A gap through the stop fills at the open.

### 1. EMA retest — TRENDING

CALL: bias BULL, HA green, at least one red HA bar in the prior 3, HA close within $0.15 of EMA20 or EMA-high.
PUT: bias BEAR, HA red, at least one green HA bar in the prior 3, HA close within $0.15 of EMA20 or EMA-low.
Stop: $0.30 of QQQ past the entry close (about −30% of premium). Target: $0.12 of QQQ (about +12%). Time: sell the close of minute 5 if neither has printed.

### 2. VWAP tag — TRENDING

CALL: slope up, bias BULL, HA green, close back above VWAP by at most $0.45, RSI14 in 42–72, and this bar or the prior red bar tagged VWAP (low between VWAP−$0.25 and VWAP+$0.05).
PUT: mirror, RSI 28–58, tag on the high.
Same exit: +$0.12 / −$0.30 / 5 minutes.

### 3. Bollinger fade — CHOPPY

CALL, 8:50–14:00: prior low at or through the lower band and that bar's RSI ≤ 40; this bar HA green, closes back inside the band, and is still under VWAP+$0.15.
PUT: prior high through the upper band, RSI ≥ 60, HA red, close back inside and above VWAP−$0.15.
Same exit. Opening-range breaks were left out: the first 5 minutes were $2.03 wide on the 21st and $2.29 on the 22nd, so the far side of the range is many times the premium, and there is one signal a day.

## Backtest

Same indicators as `replay_tune.py`. Rank is win rate, then average dollars. "Net of 1¢" subtracts $2 a trade. Every retest below is 2026-10-21 only. 2026-10-22 through 9:33 produced no retest.

| Rank | Rule | n | Win rate | Avg | Total | Net of 1¢ |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | VWAP tag, +12% / $0.30 / 5m | 4 | 100% | +$3.60 | +$14.40 | +$6.40 |
| 2 | Retest, regime filter off, +12% / $0.50 / 5m | 14 | 92.9% (13/14) | +$3.19 | +$44.70 | +$16.70 |
| 3 | Retest, TRENDING only, +12% / $0.30 / 5m | 11 | 90.9% (10/11) | +$3.08 | +$33.90 | +$11.90 |
| — | Replay: retest, +10% / −50% option, no clock | 14 | 93% | +$1.71 | +$24.00 | −$4.00 |
| — | Replay: EMA-break exit (harness X3) | 8 | 62% | +$11.55 | +$92.40 | +$76.40 |
| — | Bollinger fade, +12% / $0.30 / 5m | 1 | 0/1 | −$9.00 | −$9.00 | −$11.00 |

EMA-break makes more dollars and misses the win-rate target. The channel-cross entry (harness signal A) peaked near 76% (21 trades) and was still about −$22, because losers ran $0.50 in 1–3 minutes and the clock never got there.

Trend-retest trades in the rank-3 set, all +$3.60 except the last loss:

`09:20 P 1m, 09:30 C 1m, 10:05 C 1m, 10:24 C 1m, 10:56 C 1m, 12:03 C 3m, 12:15 C 1m, 13:14 C 1m, 13:26 C 4m, 13:35 C −$2.10 time 5m, 14:19 C 2m.`

The 13:35 call wicked −$0.30 at 13:39, was −$0.07 at the 5-minute close, and went through −$0.50 only at 13:47. The 5-minute clock cut that loss from $15 to $2. Three CHOPPY retests (08:58, 09:02, 11:38) also won +$3.60 against a $0.50 stop. 09:02 dipped $0.33 on the next bar before printing +$0.12, so the $0.30 stop and the target are in the same bar. Dropping CHOPPY entries is what holds the $0.30 stop at 10/11.

VWAP, all +$3.60: `10-21 09:27 C 1m, 14:16 C 1m, 14:19 C 2m, 10-22 09:08 P 1m.`

Bollinger: one signal, `10-21 09:13 CALL`, stopped −$9 on the next bar at $0.30. A $0.50 stop would have marked that same bar +$3.60. Either reading is one trade.

The +12% figure is the top of a plateau, not a one-cell fit. On all 14 retests, a $0.50 disaster stop with a 3, 4, 5, or 6 minute clock each went 13/14. +8% and +10% did too. +15% fell to 11/14 (78.6%). Two minutes fell to 12/14. Eight minutes stayed 13/14 but the loser was −$10.50, because the flush starts at minute 8. Stops of $0.12–$0.22 on this entry were 60–71%.

## Rule to run

VWAP leads the table and has four trades, so it stays off the bot. The rule below is the highest win rate that still uses a $0.30 QQQ stop, clears 80% on this file, and stays positive after one cent of spread. Widening that stop to $0.50 and allowing CHOPPY retests is rank 2 (13/14, +$44.70): the extra stop never filled, and the three added trades include the one path-ambiguous chop win.

```
# 1 contract. Enter only 08:45-14:30 CT. Flat by 14:45.
# TRENDING: fewer than 4 close/EMA20 crosses in the last 20 bars.
# slope: EMA20 now minus EMA20 five bars ago.
# BULL: close > VWAP and slope > 0. BEAR: close < VWAP and slope < 0.

on each 1m bar close:
  if a position is open: run the exit; skip
  if outside the entry window, or regime is not TRENDING: skip
  if BULL and HA green
     and any of the prior 3 HA bars is red
     and min(|HA_close - EMA20|, |HA_close - EMA_high|) <= 0.15:
       buy CALL
       stop = close - 0.30
       target = close + 0.12
  if BEAR and HA red
     and any of the prior 3 HA bars is green
     and min(|HA_close - EMA20|, |HA_close - EMA_low|) <= 0.15:
       buy PUT
       stop = close + 0.30
       target = close - 0.12

on each later 1m bar, in order:
  if QQQ trades through stop: sell
  else if QQQ trades through target: sell    # +12% at delta 0.30
  else if 5 minutes have elapsed: sell
```

The $0.30 stop did not fill on those 11 trades. The loser wicked $0.30 at minute 4 and left on the clock for −$2.10, so $0.30 is the tightest grid point that held this win rate, and the clock is doing the work. No trading-bot code was changed.
