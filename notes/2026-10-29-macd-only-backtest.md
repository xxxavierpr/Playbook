# Would MACD alone beat the paper book?

Research only. Nothing here changes the paper or live trader.

**MACD-only is worse.** On the same 22 mornings, the same 08:30–12:00 CT window, one position, and the same stop/target/time exits, every predeclared MACD entry loses more money than the current rules, and almost all of them win less often. The best cell in a 48-variant sweep still loses about $105 and still fails Xavier's bar (win rate above 70% on each day).

**MACD is not a reason to change entries.** Gating the existing fade/retest with "MACD histogram agrees" does raise the win rate in this sample (about 58% and 65%, versus 52% for the rules). The faster filter is also ahead on dollars (about +$40). That is a thin result: the 95% lower bound on that 65% is 48%, this week the filter still loses money, and a single no-trade or one-loss day fails the "above 70% every day" test. It is a curiosity, not a new book.

The current rules do not clear that bar either. They win 34 of 65 trades (52%) and lose about $63 after fees. Six of 22 days are above 70%, and several of those days are a single trade.

## What "the current rules" means here

The paper book (`regime_mode` on the 2026-10-29 dry-run) was transcribed into `research/macd_only_backtest.py`. The trader itself was not imported and was not edited.

From 09:00 CT, each minute is labeled WARMUP, CHOP, TREND, or MIXED. Before 09:00 the label is WARMUP and the book is flat. MIXED is flat. CHOP fades a VWAP tag (Heikin Ashi color, $0.25 through VWAP, close back through). The stop is $0.05 past that bar, clamped to $0.15–$1.00 of QQQ, the target is +25% on the option, and the clock is 10 minutes. TREND takes the EMA20 retest (HA close within $0.15 of EMA20 or the near band, prior opposite HA color, VWAP side, plus the slope/cross gate, RSI 30–70, and the $0.80 chase cap). The stop is $0.30 of QQQ, the target is +12%, and the clock is 5 minutes. One contract, one position, one bar of cooldown after an exit, at most 12 buys a day. Entries are allowed on bars that open from 08:30 through 12:00 CT; the label keeps the book flat until 09:00.

The label moves during the morning. It is not one tag for the whole day. From 09:00 to 12:00 across these 22 sessions, about 32% of minutes are CHOP, 30% TREND, and 38% MIXED.

## Data

Yahoo Finance 1-minute bars for QQQ, premarket and postmarket included, 2026-09-30 through 2026-10-29. That is the free 1-minute window (older requests come back as HTTP 422). **22 sessions, 18,975 bars.** Oct 29 stops around 13:41 CT because the cash session was still open when the file was pulled; 08:30–12:00 is complete. Oct 7 is short one regular-session minute.

The attached feed is in the test:

- `testdata/qqq_1m_yahoo_prepost.csv` — the Yahoo tape the backtest runs on
- `testdata/qqq_bars_20261026_29.json` — the paper feed, Oct 26–29
- `testdata/qqq_1m_20261022.csv` — the same feed, Oct 21–22

On the overlap, Yahoo closes match that feed to well under a cent (median absolute difference about $0.00002). Five bars differ by more than $0.05; the largest gap is $0.13.

Yahoo's 1-minute volume is not usable raw. A handful of bars print 10–20 million shares where the paper feed shows 15–30 thousand, and the 08:30 bar is several times too heavy. Session VWAP uses the attached volume on every bar that feed has. Leftover Yahoo regular-session volume is winsorized (08:30 capped at 5× the session median; any other bar above 8× the median is replaced with the median). That rule was set by matching the paper VWAP on Oct 27–29, before any strategy was scored.

Check against `trader_state.dryrun.json` at 11:58 CT on Oct 29: EMA20 error is under $0.00001, session VWAP error is about −$0.0001, and the 12/26/9 MACD histogram error is under 0.00001. Extended-hours prices are in the EMA, MACD, and Heikin Ashi, which is how the signal engine runs with extended hours on. VWAP itself starts at 08:30.

## How a trade becomes dollars

There are no historical option quotes in this test. Both books are scored with the same proxy, so the comparison is on one ruler. The ruler is optimistic on fast favorable wicks. See Thursday below.

- One contract. Assumed premium **$0.50**, the middle of the paper band ($0.30–$0.60). Thursday's four fills were $0.52, $0.55, $0.60, and $0.50.
- Delta **0.22**, held constant. Thursday's stop-outs were about $0.18–$0.23 of option per $1 of QQQ against the position.
- A +25% target is $0.125 of option premium, which is **$0.57 of QQQ** at that delta. A +12% target is **$0.27 of QQQ**.
- Fees **$0.65 per contract per side** ($1.30 round trip), taken out of every trade.
- A win is option net after fees above zero. A day "clears 70%" only when it has at least one trade and the win rate is strictly above 70%. A 2-for-3 day is 67% and fails. A day with no trade fails the "every day" bar too; those are counted separately.
- If the stop and the target both print on the same 1-minute bar, the fill is the level closer to that bar's open. A tie goes to the stop. Scoring the stop first whenever both print does not move the current-rules result (still 52.3%, still −$62.88).
- No extra slippage. No gamma and no theta. The paper's ask/spread filter (OTM, ask $0.30–$0.60, spread ≤ $0.05) is not applied. That filter can only remove trades.

At delta 0.15 the book is 48% and −$44. At delta 0.35 the target is a smaller QQQ move, so the win rate rises to 66% (44/67) and the net is still −$23, with 10 of 22 days above 70%. MACD-only stays red at both deltas. The conclusion does not depend on the 0.22 pick.

## Current rules, 22 sessions

| | |
| --- | --- |
| Trades | 65 |
| Wins | 34 (52.3%) |
| 95% lower bound on that win rate | 40% |
| Average win / average loss | +$6.66 / −$9.34 |
| QQQ points, summed | +0.98 |
| Option gross, before fees | +$22 |
| Fees | $84.50 |
| Net | **−$62.88** |
| Days above 70% | 6 of 22 |
| Days with no trade | 0 |

Exits: 30 targets (all wins), 30 stops (all losses), 5 time exits (4 of them wins after fees). The summed QQQ move is about one point across 65 trades. Fees, and the fact that the average loss is larger than the average win, are what make the book red.

Split by entry:

| Entry | Trades | Win rate | Net |
| --- | --- | --- | --- |
| VWAP fade (chop book) | 20 | 70% (14/20) | +$38 |
| EMA20 retest (trend book) | 45 | 44% (20/45) | −$101 |

The fade is the part that sits on Xavier's win-rate number **in aggregate**, on only 20 trades, and one of those 14 wins is Thursday's 09:47 put, which the paper actually lost (next section). The trend retest is where this reconstruction loses money.

Per day. "Pass" means win rate strictly above 70%.

| Day | Wins/trades | Win rate | Net | |
| --- | --- | --- | --- | --- |
| 2026-09-30 | 2/4 | 50% | −$3.30 | |
| 2026-10-01 | 1/2 | 50% | −$14.53 | |
| 2026-10-02 | 1/3 | 33% | −$2.40 | |
| 2026-10-05 | 2/2 | 100% | +$9.40 | pass |
| 2026-10-06 | 1/3 | 33% | −$4.49 | |
| 2026-10-07 | 1/1 | 100% | +$2.68 | pass |
| 2026-10-08 | 1/2 | 50% | −$3.20 | |
| 2026-10-09 | 2/3 | 67% | +$7.45 | |
| 2026-10-12 | 1/2 | 50% | −$3.20 | |
| 2026-10-13 | 1/5 | 20% | −$32.17 | |
| 2026-10-14 | 1/6 | 17% | −$34.93 | |
| 2026-10-15 | 1/1 | 100% | +$11.20 | pass |
| 2026-10-16 | 1/2 | 50% | −$3.31 | |
| 2026-10-19 | 3/3 | 100% | +$20.60 | pass |
| 2026-10-20 | 1/2 | 50% | −$3.20 | |
| 2026-10-21 | 4/5 | 80% | +$17.40 | pass |
| 2026-10-22 | 2/2 | 100% | +$15.90 | pass |
| 2026-10-23 | 0/2 | 0% | −$15.92 | |
| 2026-10-26 | 2/3 | 67% | +$8.11 | |
| 2026-10-27 | 1/2 | 50% | −$3.20 | |
| 2026-10-28 | 2/3 | 67% | −$1.85 | |
| 2026-10-29 | 3/7 | 43% | −$29.92 | |

Oct 26 is 2-for-3, the same score reported for Monday. The pass days with one trade do not mean the book was "above 70%" in any stable sense.

## This week versus the dry-run

Reported live/paper week: Monday 10/26 was 2-for-3, Tuesday and Wednesday had no trades, Thursday 10/29 was 0-for-4 and about −$58 after fees. The four Thursday closes in the state file sum to **−$50 before fees** (−$21, −$18, $0, −$11), about −$55 after $1.30 round trip. Same neighborhood as −$58.

On a complete tape the rules also go 2-for-3 on Monday (+$8 in the proxy). Tuesday and Wednesday **do** fire (a trend retest morning on the 27th, a chop-fade morning on the 28th). I do not have those days' state files, so I cannot tell whether the process was flat because of the feed, the contract filter, or a label that differed on the gappy tape. The comparison below is the rules against MACD on one complete tape.

Thursday's four paper entries are all in the reconstruction. Three more retests show up on minutes the dry-run state never received (09:37, 10:21, 10:28 — those minutes are holes in `rth_closes`).

| Entry (CT) | Paper | This proxy |
| --- | --- | --- |
| 09:10 put, VWAP fade | $1.00 stop, −$21 | $1.00 stop, −$23.30 |
| 09:47 put, VWAP fade | $1.00 stop, −$18 (option peaked at +14.5%) | scored a **win**, +$11.20 |
| 10:40 call, retest | $0.30 stop, $0 | $0.30 stop, −$7.90 |
| 11:47 put, VWAP fade | $0.47 stop, −$11 | $0.47 stop, −$11.53 |

The 09:47 disagreement is the proxy being generous. Entry was 713.68. The 09:49 low was 713.03, $0.65 under the entry, which is the model's +25% at delta 0.22. The paper option never got there (peak gain 14.5% on a $0.55 fill) and later stopped. Adverse stops line up much better than favorable wicks. Treat chop-book win rates in this note as a high reading.

## MACD alone

Variants, chosen before the run:

- Speeds: **12/26/9**, and **6/13/5** as the faster 1-minute setting (half the usual pair, signal 5). Not searched.
- Price: regular close, or Heikin Ashi close.
- Trigger: signal-line cross. A histogram cross through zero is that same event, so it is not a second test. The separate "histogram flip" is a **hook**: histogram turns up from a trough that is still below zero (call), or turns down from a peak that is still above zero (put). Third trigger: the MACD line itself crosses zero.
- Trend filter: none, or close on the correct side of EMA20. The filter is there so a good result cannot quietly be "MACD plus the trend we already use."
- Exits: the chop framework (bar stop, +25%, 10 minutes) or the trend framework ($0.30, +12%, 5 minutes), same as the book. MACD-only does not wait for the day label, so it can enter from 08:30.

That is 48 cells. Decision rule, written in the script before the run: a named reference cell has to beat the rules on **both** after-fee win rate and net dollars. The maximum in the grid is not the decision.

| Book | Trades | Win rate | Net | Days above 70% |
| --- | --- | --- | --- | --- |
| Current rules | 65 | 52.3% | −$63 | 6 |
| 12/26/9 cross, close, chop exits | 255 | 44.3% | −$269 | 0 |
| 12/26/9 cross, close, trend exits | 261 | 49.8% | −$401 | 0 |
| 12/26/9 cross, close, EMA filter, chop exits | 199 | 49.2% | −$105 | 4 |
| 12/26/9 cross, close, EMA filter, trend exits | 209 | 50.7% | −$293 | 3 |
| 6/13/5 cross, close, chop exits | 264 | 42.8% | −$413 | 0 |
| 6/13/5 cross, close, trend exits | 264 | 51.1% | −$366 | 0 |
| 12/26/9 zero-line cross, trend exits | 154 | 45.5% | −$287 | 5 |
| 12/26/9 histogram hook, chop exits | 264 | 47.0% | −$228 | 0 |
| 12/26/9 cross on HA close, chop exits | 250 | 37.2% | −$408 | 0 |
| 12/26/9 cross on HA close, trend exits | 255 | 45.9% | −$498 | 0 |

Across all 48 cells the win rate runs from 35% to 53% (median 46%). Net runs from −$814 to −$105 (median −$397). **Two cells win slightly more often than the rules. Zero cells make more money. Zero cells clear 70% on every session.**

The least-bad predeclared cell is 12/26/9, regular close, EMA20 filter, chop exits: 199 trades, 49%, −$105. Before fees that cell is +$153 gross. Fees are $259. It is a small gross edge churned to death, about nine trades a morning. This week it is 4/7, 5/7, 3/12, 3/9 and finishes Thursday at −$52. Several cells hit the 12-buy cap every single day (264 trades = 12 × 22). Their per-trade result is still negative, so raising the cap would lose more, not less.

Heikin Ashi MACD is worse than regular-close MACD. The zero-line cross trades less and still loses. The hook is the noisiest trigger and loses.

The highest win rate anywhere in the 48 is 53.3% (6/13/5, zero-line cross, EMA filter, trend exits). That cell loses $246 and clears 70% on 4 of 22 days. The highest net anywhere in the 48 is the −$105 row already in the table. With 48 looks at the same 22 days, both of those "best" figures are biased high, and both are still losers.

## MACD as a filter on the entries we already take

Same fade and retest. Take the trade only when the histogram is already on that side (call with histogram > 0, put with histogram < 0).

| Filter | Trades | Win rate | 95% lower bound | Net | Days above 70% | Flat days | This week (10/26–10/29) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 12/26/9 histogram sign | 24 | 58% (14/24) | 39% | +$4 | 8 | 5 | 2/6, about −$33 |
| 6/13/5 histogram sign | 34 | 65% (22/34) | 48% | +$40 | 12 | 4 | 7/11, about −$8 |

Thursday under the slower filter is still a losing day (it keeps the 09:10 stop and the generous 09:47 "win"). The faster filter's whole +$40 has a lower bound under 50%, and Oct 14 alone is 0-for-5 (−$40). Five or four days have no trade, which fails an every-day win-rate rule. **This is the "useful only as a filter" reading, and it does not clear the bar.**

## MACD as the entry, day-type gate kept

Same CHOP/TREND/MIXED gate and the same exits. The signal inside CHOP and TREND is a MACD cross instead of the fade or the retest. MIXED and WARMUP stay flat.

| Gate | Trades | Win rate | Net | Days above 70% | This week |
| --- | --- | --- | --- | --- | --- |
| 12/26/9 cross | 177 | 50% | −$94 | 4 | 11/34, −$116 |
| 12/26/9 cross, also require EMA20 side | 125 | 53% | +$32 | 9 | 10/26, −$60 |
| 6/13/5 cross | 244 | 45% | −$399 | 2 | −$115 |
| 12/26/9 zero-line cross | 66 | 41% | −$76 | 8 | −$40 |
| 12/26/9 hook | 262 | 48% | −$302 | 0 | −$77 |

The one green cell (+$32 on 125 trades, about $0.25 a trade) loses $60 on the week that prompted the question. Its 95% lower bound is 44%. I would not turn it on.

## What this sample can and cannot say

Twenty-two mornings and 65 rule-trades is a small sample. A real 70%-every-day book would be obvious here, and it is not, for the rules or for MACD. The bar is also harsher than the sample size: with two or three trades, one loss fails the day. Passing days in the table are often 1-for-1.

The 48-cell grid was scored on the same days it is reported on. That is why the decision uses the list written down first, and why the grid maximum is quoted and then ignored. Nothing was held out. A later month can disagree, especially on the filter, where moving one or two trades changes the sign of the dollars.

The option proxy matches Thursday's adverse stops and over-credits fast favorable wicks. If anything, that bias helps the chop target, which is the framework MACD needed in order to lose the least. It did not produce a MACD book that wins.

Rerun with `python3 research/macd_only_backtest.py`. The machine-readable dump is `research/macd_backtest_results.json`.
