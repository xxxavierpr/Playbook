# QQQ 0DTE: trend bars and chop bars need different trades

Stop buying the with-trend EMA20 retest on the contract the paper is actually filling, about a $0.50 premium and a 0.25 delta. On that contract, none of the 2,520 entry-and-exit cells is both above 70% and green after one cent on the train set. The three cells that do clear 70% and a positive train net are a closer $1.00 / delta-0.50 contract with a $0.60 stop, a +10% target, and a 3-minute clock. All three lose money on the last five sessions. Leave the current paper keys where they are. Do not widen `qqq_stop` to 0.60, do not cut `tp_pct` to 0.10, and do not shorten `time_exit_min` to 3.

The only book that is above 70% and still green after one cent, on the train and on the holdout, is a chop-only fade: when the morning is labeled chop, sell a VWAP tag that closes back through VWAP, stop $0.05 past that bar (floor $0.15, cap $1.00), take +25%, and flatten at 10 minutes. Hard-trend bars and mixed bars send nothing. That book is 15 wins in 20 trades, net +$41.55 after $2 of slippage. One holdout loss is a gap of −$32.50. It is a paper experiment. It is not a live rule.

`notes/2026-10-23-regime-grid.py` reprints every figure from the cutoff below. The Monday 10/26 paper build is the last section. It keeps the trend retest on, behind `regime_mode`, and the combined replay of that book is there too. `--live` is unchanged.

## Sample, contract, and the split

Yahoo 1-minute QQQ, regular hours, 2026-09-29 through 2026-10-23 11:31 CT. Nineteen sessions, 7,201 bars. The morning window runs to 12:00, so this slice is unfinished and a later bar can add a trade. The same source as the 09:32 note. 2026-10-07 is still missing the bar between 11:41 and 11:43 CT. Indicators match that note: EMA20 seeded with the first close, the same average on high and low, VWAP the cumulative average of (high+low+close)/3, Heikin Ashi reset at the open. A bar is "trending" in the PR #8 sense when close crosses EMA20 fewer than four times in 20 bars. That is a separate flag from the day label below.

The train set is every session except the last five. The holdout is 2026-10-19, 10-20, 10-21, 10-22, and 10-23. Rank is train win rate, then train net. A cell is eligible at 20 train trades (12 inside one regime, 8 if the regime is mixed), train win rate at least 70%, and train net above zero. The holdout is printed and does not re-rank. A fixed-stop winner also has to keep a non-negative train net on the adjacent stop and the adjacent target. That last check is what marks the three closer cells unstable.

P&L uses three contracts. The primary one is the live band: premium $0.50, delta 0.25, so a QQQ point is $25. A +10% target is $0.20 of QQQ and +$5. A +12% target is $0.24 and +$6. A +25% target is $0.50 and +$12.50. A $0.30 QQQ stop is −$7.50. The PR #8 proxy stays $0.30 / 0.30, a QQQ point $30, so +10% is about +$3 and a full $0.30 stop is −$9. The closer contract is $1.00 / 0.50. A win is a positive dollar result before slippage. Net subtracts $2 a trade. The stop fills when price trades strictly through it. A gap through the stop fills at the open. A gap through the target fills at the target. On a bar that touches both, the stop fills. One position, and the bar after an exit is skipped.

## What the two paper trades did

Both of today's tickets are the baseline retest, and both are hard-trend bars.

The 09:12 bar closed 705.50, EMA20 705.19, VWAP 704.19, HA green, label TREND up. That is the 713C filled at 9:13 for $0.46. The 09:13 low is 704.90, sixty cents under the entry, so every fixed stop in the grid ($0.15, $0.22, $0.30, $0.45, $0.60) fills on that bar. On the live contract the $0.30 stop is −$7.50, against the ticket's −$7. The 09:14 high is 705.75, which is the +12% target of $0.24. A stop wider than $0.60 would have taken +$6 on the next bar. The grid's widest fixed stop still loses $15 there, and the later low is 703.44. Giving that entry more room makes the loss larger inside the grid.

The 11:09 bar closed 708.29, EMA20 708.24, VWAP 706.36, HA green, label TREND up. That is the 712C filled at 11:10 for $0.53. The best price after the entry is the 11:10 high, 708.38, nine cents of favorable travel. The smallest target in the grid is +10%, which needs twenty cents, so no target prints. The $0.30 stop fills on the 11:13 low of 707.93 (adverse $0.36), −$7.50 in this contract. The ticket sold at 11:14 for −$8; the 11:14 low is 707.30, adverse $0.99, so a $0.45 or $0.60 stop fills on that bar for −$11.25 or −$15. A $0.60 stop with a 3-minute clock is the one grid pair that turns this entry into a small loss: out at the 11:12 close of 708.25, about −$1.12. That pair is the highest live-contract win rate in the all-morning grid, and the book is still −$54 on the train.

Waiting for the touch bar's low to hold cancels both. The 09:13 low breaks 705.32, and the 11:10 low breaks 708.29. That confirmation entry is in the grid. It does not produce a train book that makes money.

## The day label

The label is live at 09:00 CT, once 20 bars exist, and it updates on every completed minute. Before 09:00 the label is WARMUP and the regime book is flat.

- Hard TREND, in the direction of the 15-bar EMA20 slope, when all of these are true: at most 2 close/EMA20 crosses in the last 20 bars, the 15-bar slope is at least $0.40, at least 75% of the last 20 closes sit on the slope's side of VWAP, the current close is on that side, and either the 08:30–08:44 opening range is still broken in that direction or price is at least $0.50 from VWAP.
- CHOP when there are 4 or more crosses in 20 bars, or the 15-bar slope is under $0.20 and neither side of VWAP holds more than 65% of the last 20 closes.
- Anything else is MIXED.

A Heikin Ashi streak and an ATR multiple are not inputs. The opening-range hold is the range check the label uses. Inside the entry window the train bars split WARMUP 210, TREND 643, CHOP 892, MIXED 998. The holdout bars split WARMUP 75, TREND 342, CHOP 195, MIXED 339. Most of the morning is mixed or chop.

| Session | 09:00 | 09:30 | 11:00 |
| --- | --- | --- | --- |
| 09-29 | MIXED up | CHOP | CHOP |
| 09-30 | TREND up | CHOP | CHOP |
| 10-01 | CHOP | MIXED down | MIXED down |
| 10-02 | TREND up | TREND up | MIXED |
| 10-05 | MIXED | TREND up | MIXED up |
| 10-06 | CHOP | CHOP | CHOP |
| 10-07 | CHOP | CHOP | TREND up |
| 10-08 | CHOP | TREND up | CHOP |
| 10-09 | TREND down | MIXED up | MIXED |
| 10-12 | CHOP | TREND down | MIXED up |
| 10-13 | TREND up | CHOP | MIXED |
| 10-14 | MIXED down | CHOP | MIXED down |
| 10-15 | MIXED down | MIXED up | CHOP |
| 10-16 | TREND down | CHOP | MIXED down |
| 10-19 hold | CHOP | TREND up | CHOP |
| 10-20 hold | MIXED up | TREND up | CHOP |
| 10-21 hold | CHOP | MIXED up | TREND up |
| 10-22 hold | CHOP | TREND down | MIXED |
| 10-23 hold | TREND up | CHOP | MIXED up |

Today at 09:00: TREND up. Zero crosses in 20 bars, 15-bar slope +$1.28, all 20 closes above VWAP, close $1.12 above VWAP, opening range 701.16–704.50 already broken up, five green HA bars in a row. Still TREND up at the 09:12 retest. CHOP by 09:21 (4 crosses, slope −$0.09), and still CHOP at 09:30 (6 crosses, slope −$0.59). MIXED up at 11:00 (3 crosses, slope +$0.50, $2.31 above VWAP). TREND up again at the 11:09 retest (0 crosses, slope +$0.57). MIXED from 11:13 (3 crosses, slope +$0.37) through the 11:31 bar, close 706.91, VWAP 706.47.

## All-morning grid, no regime switch

Five trend entries, three contracts, 168 exits: 2,520 cells. Entries are the PR #8 retest (`base`), the same retest only after the touch low holds and a later bar closes back through EMA20 (`confirm`, three bars to do it), the retest only within $1.50 of VWAP (`vwap15`) or $3.00 (`vwap30`), and the retest only when the call low holds the EMA-low band (`band`). Exits are the five fixed stops, a stop $0.05 past the signal bar, and a stop $0.05 past the EMA / EMA-band, each clamped to $0.15–$1.00. Targets are 10, 12, 15, 20, and 25 percent, plus a +20% latch that arms when the target distance prints and sells on a later bar that trades back to the arm. Clocks are 3, 5, 8, and 10 minutes.

Ranked by train win rate, then train net, the top of the 2,520 is the old proxy with a +10% target. Eighty percent still loses, because a win is about +$3 and a loss is $13 to $15. Breakeven on that payoff is about 82%.

| Rank | Config | Train | Avg win | Avg loss | Train net | Holdout |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | band, proxy $0.30/0.30, EMA stop, +10%, 5m | 80.0% (52/65) | +$2.99 | −$13.51 | −$150.02 | 84.2% (16/19), −$47.44 |
| 2 | same, 8m | 80.0% (52/65) | +$3.00 | −$14.20 | −$158.57 | 84.2% (16/19), −$47.44 |
| 3 | same, 10m | 80.0% (52/65) | +$3.00 | −$14.20 | −$158.57 | 84.2% (16/19), −$47.44 |
| 4 | band, proxy, stop $0.60, +10%, 5m | 80.0% (52/65) | +$2.99 | −$15.01 | −$169.60 | 80.0% (16/20), −$64.00 |
| 5 | same, 8m | 80.0% (52/65) | +$3.00 | −$15.22 | −$171.84 | 80.0% (16/20), −$64.00 |

Only three cells are eligible. All three are the closer contract, all three fail the adjacent-stop check, and all three are red on the holdout.

| Eligible | Config | Train | Avg win | Avg loss | Train net | Holdout |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | base, closer $1/0.50, stop $0.60, +10%, 3m | 75.0% (51/68) | +$9.27 | −$18.18 | +$27.67 | 70.0% (14/20), −$25.57 |
| 2 | band, closer, stop $0.60, +10%, 3m | 74.6% (50/67) | +$9.26 | −$18.18 | +$19.67 | 65.0% (13/20), −$49.82 |
| 3 | vwap15, closer, stop $0.60, +10%, 3m | 74.5% (41/55) | +$9.23 | −$18.31 | +$11.92 | 66.7% (8/12), −$64.00 |

On the live contract, 840 cells have at least 20 train trades and none has a positive train net. The highest win rate is the baseline with a $0.60 stop, +10%, and a 3-minute clock: train 75.0% (51/68), average win +$4.63, average loss −$9.09, net −$54.16, holdout 70.0% (14/20), net −$32.78. A +$5 win against a $15 stop needs about 85% after the $2 haircut. The best live train net in that set is still −$49.04 (vwap15, stop $0.60, +10%, 3m).

The current paper rule on this contract, baseline retest, stop $0.30, +12%, 5 minutes: train 52.2% (35/67), net −$147.25; holdout 65.0% (13/20), net −$14.50; full sample 55.2% (48/87), net −$161.75. Today it takes both retests and stops both, −$7.50 and −$7.50.

## Separate books

Trend bars, live contract, the five pullback entries against all 168 exits: 840 cells with at least 12 train trades. Thirty-one of them win at least 70%. Zero of them have a positive train net. The least-bad is vwap15 with the EMA structure stop, +10%, and a 3-minute clock: train 71.4% (15/21), average win +$4.70, average loss −$6.94, net −$13.12; holdout 66.7% (4/6), net −$26.20. The +20% latch is inside those 168 exits. It does not pay. The trend book is a skip.

Chop bars, two fade entries against the same exits. The precommitted tight fade loses. VWAP fade, stop $0.30, +10%, 3 minutes: train 40.0% (6/15), net −$81.00; holdout 66.7% (4/6), net −$7.00. The $0.15 and $0.22 versions of that 3-minute fade are −$74.25 and −$62.00 on the train. Four chop cells have a positive train net and at least 8 trades, and only one also clears 70%:

| Chop cell | Train | Avg win | Avg loss | Train net | Holdout |
| --- | --- | --- | --- | --- | --- |
| VWAP fade, bar stop, +25%, 10m | 71.4% (10/14) | +$12.50 | −$18.36 | +$23.55 | 83.3% (5/6), +$18.00 |
| same, 8m | 64.3% (9/14) | +$12.03 | −$15.01 | +$5.17 | 83.3% (5/6), +$18.00 |
| VWAP fade, stop $0.45, +25%, 10m | 60.0% (9/15) | +$12.50 | −$12.88 | +$5.25 | 66.7% (4/6), +$15.50 |
| same, 8m | 60.0% (9/15) | +$12.03 | −$12.88 | +$1.00 | 66.7% (4/6), +$15.50 |

The fade is a mean-reversion entry. A call needs an HA green bar whose low tags VWAP by at least $0.25 and whose close finishes back above VWAP. A put is the mirror. The EMA-band fade did not clear the gate. Mixed bars were searched with the trend entries and both fades, at a lower bar of 8 train trades. Nothing there is eligible, so mixed is a skip too.

Stitched, trend off, mixed off, chop on the +25% bar-stop fade. Every dollar is the chop book.

| Split | Trades | Win rate | Avg win | Avg loss | Gross | Net of 1¢ |
| --- | --- | --- | --- | --- | --- | --- |
| Train | 14 | 71.4% (10/14) | +$12.50 | −$18.36 | +$51.55 | +$23.55 |
| Holdout | 6 | 83.3% (5/6) | +$12.50 | −$32.50 | +$30.00 | +$18.00 |
| Full | 20 | 75.0% (15/20) | +$12.50 | −$21.19 | +$81.55 | +$41.55 |

A +$12.50 win and an −$18 loss need about 60% before slippage and about 66% after the $2. The train rate sits just above that. The 95% lower bound on 10/14 is about 45%. The holdout net is one gap: 2026-10-20 10:13, a put, stop capped at $1.00, filled −$32.50 because the open gapped through the cap. Five targets at +$12.50 cover that gap and the slippage, with little left over.

The twenty fills:

| When | Side | Entry | P&L | Exit | Stop used |
| --- | --- | --- | --- | --- | --- |
| 09-29 09:11 | PUT | 737.51 | −$22.32 | stop | 0.89 |
| 09-29 09:15 | PUT | 737.79 | −$21.00 | stop | 0.58 |
| 09-29 10:00 | PUT | 738.49 | +$12.50 | target | 0.71 |
| 09-30 09:38 | CALL | 742.90 | +$12.50 | target | 0.85 |
| 10-01 09:45 | CALL | 740.43 | −$20.38 | stop | 0.82 |
| 10-02 09:52 | PUT | 752.23 | +$12.50 | target | 0.77 |
| 10-05 09:08 | CALL | 752.11 | +$12.50 | target | 0.67 |
| 10-06 09:23 | PUT | 760.82 | +$12.50 | target | 0.71 |
| 10-07 09:08 | CALL | 753.39 | +$12.50 | target | 0.58 |
| 10-13 09:19 | PUT | 742.78 | −$9.75 | stop | 0.39 |
| 10-13 09:27 | PUT | 742.79 | +$12.50 | target | 0.52 |
| 10-13 09:37 | CALL | 742.98 | +$12.50 | target | 0.58 |
| 10-15 09:01 | CALL | 719.05 | +$12.50 | target | 1.00 cap |
| 10-16 09:34 | CALL | 721.78 | +$12.50 | target | 0.44 |
| 10-19 11:45 hold | PUT | 721.20 | +$12.50 | target | 0.43 |
| 10-20 10:13 hold | PUT | 718.02 | −$32.50 | stop, gapped | 1.00 cap |
| 10-21 09:05 hold | PUT | 721.46 | +$12.50 | target | 1.00 cap |
| 10-22 09:06 hold | PUT | 713.37 | +$12.50 | target | 0.59 |
| 10-23 09:25 hold | PUT | 704.16 | +$12.50 | target | 0.73 |
| 10-23 09:29 hold | CALL | 704.87 | +$12.50 | target | 0.92 |

Today the stitch skips both retests. At 09:25 the label is CHOP and the bar is a put fade: high 704.84 against VWAP 704.29, close 704.16, HA red. Stop 704.89, target 703.66, filled on the 09:26 low, +$12.50. At 09:29 a call fade: low 704.00 against VWAP 704.27, close 704.87, HA green. Stop 703.95, target 705.37, filled on the 09:30 high of 705.54, +$12.50. The position is flat before the run to 707.48 at 09:40. From 11:00 the label is mixed, then trend for the 11:09 retest, then mixed again, and the book takes nothing.

## Monday paper switch

The ranking above leaves trend flat, because that book has no profitable exit. For the Monday 10/26 paper test the switch is built the other way: trend bars keep the current PR #8 retest (stop $0.30, +12%, 5 minutes), chop bars take the VWAP fade, and mixed or warmup bars send nothing. It lives in `trader.py` behind `regime_mode`. The flag defaults off. `--live` ignores it, and a new live day still rebuilds `trader_state.json` with no override and no day-regime history.

`report_combined` in `notes/2026-10-23-regime-grid.py` replays that combination on the same Yahoo mornings, live contract $0.50 / delta 0.25, through 2026-10-23 12:55 CT. The entry window had closed. The replay stop fills when price trades strictly through the level. The paper bot's existing cursor exit fills when the bar touches the level. Today's two $0.30 stops are through the level either way.

| Split | Regime | Trades | Win rate | Avg win | Avg loss | Net of 1¢ |
| --- | --- | --- | --- | --- | --- | --- |
| Train | TREND retest | 29 | 48.3% (14/29) | +$6.00 | −$7.50 | −$86.50 |
| Train | CHOP fade | 14 | 71.4% (10/14) | +$12.50 | −$18.36 | +$23.55 |
| Train | Combined | 43 | 55.8% (24/43) | +$8.71 | −$9.79 | −$62.95 |
| Holdout | TREND retest | 13 | 61.5% (8/13) | +$6.00 | −$7.50 | −$15.50 |
| Holdout | CHOP fade | 6 | 83.3% (5/6) | +$12.50 | −$32.50 | +$18.00 |
| Holdout | Combined | 19 | 68.4% (13/19) | +$8.50 | −$11.67 | +$2.50 |
| Full | TREND retest | 42 | 52.4% (22/42) | +$6.00 | −$7.50 | −$102.00 |
| Full | CHOP fade | 20 | 75.0% (15/20) | +$12.50 | −$21.19 | +$41.55 |
| Full | Combined | 62 | 59.7% (37/62) | +$8.64 | −$10.24 | −$60.45 |

Mixed contributes no trades. The holdout combined net is +$2.50. The train combined net is −$62.95, and the full sample is −$60.45. Both of today's retests are in the trend column, −$7.50 each, and both fades are in the chop column, +$12.50 each.

## What to set for paper

On the dry-run state only (`trader_state.dryrun.json`), the override block:

```json
{
  "regime_mode": true,
  "entry_mode": "retest_trend",
  "retest_trend_only": true,
  "retest_near_only": true,
  "tp_pct": 0.12,
  "tp_min_hold_s": 10,
  "qqq_stop": 0.30,
  "time_exit_min": 5,
  "reentry_cooldown_bars": 1,
  "quick_tp": false,
  "max_vwap_dist": 6.0,
  "paper_min_ask": 0.30,
  "paper_max_ask": 0.60,
  "paper_max_spread": 0.05,
  "max_buys": 12
}
```

A new paper day keeps that block and clears the position, the buy count, and `done`. Live does not. `done` stops further paper entries once `buys` has reached `max_buys`. Under the cap it stays clear, so the 12-buy paper day can take the next fade after a stop.

While the flag is on, every dry-run decision line (`no_entry`, `entry_blocked`, `entry_signal`, `retest_check`, and `hold` / `exit_signal` while a paper position is open) carries `day_regime`. Chop exits are armed on the position itself: stop $0.05 past the signal bar, clamped to $0.15–$1.00, `tp_pct` 0.25, `time_exit_min` 10. Trend exits stay on the keys above. Entries stay inside 08:45–12:00 CT. Before 09:00 the label is WARMUP, so the first fifteen minutes of the window are flat. The closer-contract spike stays off the list: `qqq_stop` 0.60, `tp_pct` 0.10, `time_exit_min` 3, and a $1 ask.
