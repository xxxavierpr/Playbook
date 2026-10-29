# Would MACD alone beat the paper book?

Research only. Nothing here changes the paper or live trader.

**MACD-only is worse.** On the same 22 mornings, the same 08:30–12:00 CT window, one position, and the same stop/target/time exits, every predeclared MACD entry loses more money than the current rules, and almost all of them win less often. The best cell in a 48-variant sweep still loses about $105 and still fails Xavier's bar (win rate above 70% on each day).

**MACD is not a reason to change entries.** Gating the existing fade/retest with "MACD histogram agrees" does raise the win rate in this sample (about 58% and 65%, versus 52% for the rules). The faster filter is also ahead on dollars (about +$40). That is a thin result: the 95% lower bound on that 65% is 48%, this week the filter still loses money, and a single no-trade or one-loss day fails the "above 70% every day" test. It is a curiosity, not a new book.

The current rules do not clear that bar either. They win 34 of 65 trades (52%) and lose about $63 after fees. Six of 22 days are above 70%, and several of those days are a single trade.

**MACD plus RSI, with no EMA20, no VWAP, no Heikin Ashi, and no day label, does not beat those rules and does not get near 70% every day.** On the same 22 mornings and the same two exit sets, a 24-cell grid runs 37–52% wins. Zero cells win more often than the rules. One cell is green on dollars (about +$36) and it wins less often than the rules (48%). The widest "days above 70%" count in the grid is 7 of 22. Details are in the follow-up section below.

**The curve rule on Xavier's chart — enter on the signal-line cross after the MACD line hooks, and get out when the line curls the other way — is worse than both.** In a 12-cell test the win rate runs 29–38%. Every cell loses money. The least-bad cell loses about $172. Not one day in any cell is above 70%.

**Entering the moment the line hooks, and getting out quickly, does not fix it.** A 13-cell in-and-out test wins as often as 66% and still loses money on every cell. The best dollars are about −$159, against −$63 for the rules. The high win rate is a small target: a +5% win is $1.20 after fees and a $0.30 stop is about an $8 loss. Today's 2:17 PM CT hook did fire, and the quick exit was out two minutes later for +$3.70, before the 2:30 PM push.

**A Bollinger touch plus that hook, held until the MACD curls back, made money in this sample and still fails the win-rate test.** The main version wins 29% of 212 trades and nets about +$240. Average win about +$23, average loss about −$8. Zero days are above 70%. Three days (October 1, 15, and 23) carry more than the whole profit. Banking the reversal at the middle band, instead of holding it, loses about $455.

## What "the current rules" means here

The paper book (`regime_mode` on the 2026-10-29 dry-run) was transcribed into `research/macd_only_backtest.py`. The trader itself was not imported and was not edited.

From 09:00 CT, each minute is labeled WARMUP, CHOP, TREND, or MIXED. Before 09:00 the label is WARMUP and the book is flat. MIXED is flat. CHOP fades a VWAP tag (Heikin Ashi color, $0.25 through VWAP, close back through). The stop is $0.05 past that bar, clamped to $0.15–$1.00 of QQQ, the target is +25% on the option, and the clock is 10 minutes. TREND takes the EMA20 retest (HA close within $0.15 of EMA20 or the near band, prior opposite HA color, VWAP side, plus the slope/cross gate, RSI 30–70, and the $0.80 chase cap). The stop is $0.30 of QQQ, the target is +12%, and the clock is 5 minutes. One contract, one position, one bar of cooldown after an exit, at most 12 buys a day. Entries are allowed on bars that open from 08:30 through 12:00 CT; the label keeps the book flat until 09:00.

The label moves during the morning. It is not one tag for the whole day. From 09:00 to 12:00 across these 22 sessions, about 32% of minutes are CHOP, 30% TREND, and 38% MIXED.

## Data

Yahoo Finance 1-minute bars for QQQ, premarket and postmarket included, 2026-09-30 through 2026-10-29. That is the free 1-minute window (older requests come back as HTTP 422). **22 sessions.** Oct 29 was refreshed through 14:35 CT so the afternoon hook could be scored. Oct 7 is short one regular-session minute.

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

## Follow-up: MACD + RSI only

Xavier asked for MACD and RSI with nothing else in the entry: no EMA20, no VWAP, no Heikin Ashi, no regime label. Same 22 sessions, entries 08:30–12:00 CT, one position, the same $0.50 / 0.22 / $1.30 proxy, and the same two exit sets (chop: bar stop up to $1, +25%, 10 minutes; trend: $0.30 stop, +12%, 5 minutes).

The grid was written into the script before this run. It is 24 cells:

- MACD signal-line cross, regular close: 12/26/9 and 6/13/5.
- RSI 14, and RSI 7.
- Confirm: take the MACD cross only when RSI is already above 50 for a call or below 50 for a put.
- Reversal: RSI crosses back above 30 (call) or back below 70 (put), and a same-side MACD cross prints on that bar or within the previous N bars on the tape. Enter once, on the later of the two events. N is 3 and N is 5.
- Each of those with both exit sets.

That is 2 speeds × 2 RSI lengths × 2 exits × (1 confirm + 2 windows) = 24. Eight of them were named as the decision set before the run: 12/26/9 with RSI 14, confirm and the N=5 reversal, both exits; 6/13/5 with RSI 14, confirm, both exits; the fast pair together (6/13/5 with RSI 7, confirm, chop exits); and a tight reversal (12/26/9, RSI 7, N=3, chop exits). A cell "beats the rules" only if it is higher on after-fee win rate and higher on net. The other 16 cells are the same ideas with the other RSI length or the other N. The best of those 16 is reported and is not a new book.

### Does it beat the rules?

No. None of the 8 decision cells do. All 8 lose money. Their win rates are 38–49%, all below the rules' 52%. Days above 70% run from 0 to 4, against 6 for the rules.

| Book | Trades | Win rate | Net | Days above 70% | Flat days | Oct 26–29 |
| --- | --- | --- | --- | --- | --- | --- |
| Current rules | 65 | 52.3% | −$63 | 6 | 0 | 8/15, −$27 |
| MACD 12/26/9 cross, chop exits | 255 | 44.3% | −$269 | 0 | 0 | 20/46, −$50 |
| MACD 12/26/9 cross, trend exits | 261 | 49.8% | −$401 | 0 | 0 | 23/47, −$81 |
| MACD 6/13/5 cross, chop exits | 264 | 42.8% | −$413 | 0 | 0 | 23/48, −$49 |
| + RSI 14 confirm, 12/26/9, chop | 188 | 47.9% | −$150 | 3 | 0 | 13/33, −$70 |
| + RSI 14 confirm, 12/26/9, trend | 197 | 49.2% | −$312 | 1 | 0 | 17/36, −$68 |
| + RSI 14 confirm, 6/13/5, chop | 257 | 38.1% | −$755 | 1 | 0 | 22/43, +$1 |
| + RSI 14 confirm, 6/13/5, trend | 262 | 46.2% | −$490 | 0 | 0 | 24/47, −$46 |
| RSI 14 reclaim, N=5, 12/26/9, chop | 62 | 41.9% | −$66 | 2 | 0 | 8/13, +$39 |
| RSI 14 reclaim, N=5, 12/26/9, trend | 62 | 45.2% | −$127 | 4 | 0 | 7/13, −$9 |
| RSI 7 confirm, 6/13/5, chop | 258 | 38.8% | −$739 | 1 | 0 | 21/44, −$35 |
| RSI 7 reclaim, N=3, 12/26/9, chop | 97 | 40.2% | −$126 | 2 | 0 | 7/18, $0 |

Adding "RSI on the right side of 50" to a plain 12/26/9 cross does trim the MACD-only loss (chop exits: −$269 down to −$150, win rate 44% up to 48%). It is still worse than the rules on both win rate and dollars, and this week it is worse than the rules (−$70 vs −$27), including a 2-for-8 Thursday (−$63). Putting the same filter on the fast MACD makes that book worse, not better (−$755 vs −$413).

### The one green cell

Across all 24, win rate runs 37–52% (median 47%) and net runs −$755 to +$36 (median −$246). **Zero cells win more often than the rules.** One cell makes more money: 12/26/9, RSI 14, reversal within 3 bars, chop exits. It is 21 wins out of 44 trades (48%, 95% lower bound 34%), net **+$36**, 5 of 22 days above 70%, and 2 days with no trade. This week it is 6/9 and +$48, with Wednesday flat and only Monday above 70%.

That cell was in the predeclared 24. It was not in the decision 8, and it does not survive the checks next to it:

- The same signal with N=5 instead of N=3 loses **$66**. Two extra bars of patience flips the sign.
- The same N=3 signal with the trend exit instead of the chop exit loses **$81**. The dollars depend on the fat +25% target, which is the proxy that over-credits fast favorable wicks.
- Scoring a stop ahead of a target on the same bar does not change this cell (still +$36). The tie-break is not the source of the green number. It does make the 12/26/9 RSI-14 confirm book worse (−$150 becomes −$228).

The highest "days above 70%" in the 24 is 7 of 22, on a fast-MACD reversal that loses $140. Seven is not close to every day. The rules themselves get 6.

### This week, per day

Win rate strictly above 70% is marked pass. A blank day had no trade.

| Day | Rules | MACD 12/26/9 chop | RSI14 confirm, chop | RSI14 reclaim N=3, chop | RSI14 reclaim N=5, chop |
| --- | --- | --- | --- | --- | --- |
| 10/26 | 2/3, +$8 | 6/11, $0 | 4/7, +$4 | 3/3, +$34 pass | 3/4, +$19 pass |
| 10/27 | 1/2, −$3 | 5/11, +$7 | 4/6, +$29 | 2/4, +$8 | 3/5, +$6 |
| 10/28 | 2/3, −$2 | 5/12, −$9 | 3/12, −$40 | no trade | 1/2, +$8 |
| 10/29 | 3/7, −$30 | 4/12, −$48 | 2/8, −$63 | 1/2, +$7 | 1/2, +$7 |
| Week | 8/15, −$27 | 20/46, −$50 | 13/33, −$70 | 6/9, +$48 | 8/13, +$39 |

No row is above 70% on all four days. The reversal's good week is real inside this sample and it is also the book that loses money once the window is 5 bars, and loses money over the full 22 days at N=5.

### Per day, the three 12/26/9 + RSI 14 books people would actually look at

Confirm, chop exits (188 trades, 48%, −$150, 3 days above 70%):

| Day | W/L count | Win rate | Net | |
| --- | --- | --- | --- | --- |
| 09-30 | 3/11 | 27% | −$96 | |
| 10-01 | 6/12 | 50% | −$3 | |
| 10-02 | 5/10 | 50% | −$31 | |
| 10-05 | 2/7 | 29% | −$14 | |
| 10-06 | 3/6 | 50% | +$12 | |
| 10-07 | 3/10 | 30% | −$26 | |
| 10-08 | 1/6 | 17% | −$34 | |
| 10-09 | 4/8 | 50% | +$18 | |
| 10-12 | 3/7 | 43% | −$19 | |
| 10-13 | 5/6 | 83% | +$38 | pass |
| 10-14 | 6/11 | 55% | +$7 | |
| 10-15 | 8/12 | 67% | +$38 | |
| 10-16 | 6/8 | 75% | +$32 | pass |
| 10-19 | 4/10 | 40% | −$39 | |
| 10-20 | 4/7 | 57% | +$26 | |
| 10-21 | 3/8 | 38% | −$29 | |
| 10-22 | 5/8 | 62% | $0 | |
| 10-23 | 6/8 | 75% | +$39 | pass |
| 10-26 | 4/7 | 57% | +$4 | |
| 10-27 | 4/6 | 67% | +$29 | |
| 10-28 | 3/12 | 25% | −$40 | |
| 10-29 | 2/8 | 25% | −$63 | |

Reclaim within 3 bars, chop exits (44 trades, 48%, +$36, 5 days above 70%, 2 flat):

| Day | W/L count | Win rate | Net | |
| --- | --- | --- | --- | --- |
| 09-30 | 2/2 | 100% | +$22 | pass |
| 10-01 | 1/3 | 33% | −$26 | |
| 10-02 | 1/2 | 50% | +$4 | |
| 10-05 | 0/3 | 0% | −$10 | |
| 10-06 | 1/2 | 50% | +$7 | |
| 10-07 | 1/1 | 100% | +$11 | pass |
| 10-08 | 0 | | $0 | flat |
| 10-09 | 0/1 | 0% | −$5 | |
| 10-12 | 0/1 | 0% | −$7 | |
| 10-13 | 2/5 | 40% | +$2 | |
| 10-14 | 0/1 | 0% | −$9 | |
| 10-15 | 1/1 | 100% | +$11 | pass |
| 10-16 | 2/4 | 50% | −$1 | |
| 10-19 | 0/1 | 0% | −$11 | |
| 10-20 | 1/3 | 33% | −$13 | |
| 10-21 | 1/1 | 100% | +$11 | pass |
| 10-22 | 1/2 | 50% | −$7 | |
| 10-23 | 1/2 | 50% | +$6 | |
| 10-26 | 3/3 | 100% | +$34 | pass |
| 10-27 | 2/4 | 50% | +$8 | |
| 10-28 | 0 | | $0 | flat |
| 10-29 | 1/2 | 50% | +$7 | |

Reclaim within 5 bars, chop exits (62 trades, 42%, −$66, 2 days above 70%). Same idea, two bars looser, and the 22-day result is red. Per day it is the N=3 list with extra trades on the days N=3 was flat or thin: 10/01 goes from 1/3 to 1/4, 10/08 from flat to 0/1, 10/26 from 3/3 to 3/4, 10/28 from flat to 1/2. The week stays green (+$39) while the full sample does not.

Every other cell's per-day rows are in `research/macd_backtest_results.json`.

### Multiple testing

Twenty-four new cells, scored on the same 22 days as the earlier 48. The best cell in a list of 24 will look better than a typical cell from that list. Here the "best" dollars are +$36 on 44 trades, the lower bound on the win rate is 34%, and the next predeclared window (N=5) loses $66. That is what multiple testing looks like when you can check the neighbor: the green cell does not repeat. I would not trade it, and I would not add it to the paper book.

## Follow-up: enter on the cross after the hook, exit on the curl

Xavier's photo is the MACD panel: blue MACD line, orange signal line, histogram teal then white above zero and orange then pink below. The line curls up, crosses above the signal, peaks and curls over, then crosses down and flattens. His rule, in his words: when the MACD line starts to curve, take the position once it crosses the signal line, and get out when the line starts to curve the other way. The exit is the curl. There is no +25%, no +12%, and no 5- or 10-minute clock.

How that was coded, before the run:

- A bullish turn is the MACD line's slope flipping from flat or down to up. A bearish turn is the flip the other way.
- Enter a call on the first bullish signal-line cross while that up-turn is still the latest turn. Enter a put the same way after a down-turn. The turn and the cross can be the same bar. A turn the other way cancels the setup. No same-bar reversal: the exit bar does not also open the opposite trade.
- Exit on the first bar the slope flips against the open trade, at that bar's close.
- Also tested the photo's histogram colors as the definition of "curve." One white or pink bar is the histogram changing direction for one bar. Two bars means it has shrunk for two bars in a row. Entry is still the signal cross after that turn. Exit is the same kind of turn against the trade.
- Two risk versions: no stop at all, and a disaster stop at $0.50 of QQQ, filled if that bar's high or low trades through it. If the stop and the curl happen on the same bar, the stop fills.
- Speeds 12/26/9 and 6/13/5. Regular closes for the rule. Heikin Ashi closes are a check on the 12/26/9 slope rule only.
- That is 12 cells, not every combination. The decision set is the four slope cells on regular closes (both speeds, with and without the $0.50 stop). The histogram rows and the HA check are the sensitivity. One position. Entries 08:30–12:00 CT. No 12-trade cap, because this is not the paper override. A trade still open at the last regular-session bar is marked there. In this test the curl almost always arrived first. Same $0.50 premium, 0.22 delta, and $1.30 fees.

### Does it beat the rules, or the earlier MACD tests?

No. None of the 12 cells win more often than the rules, and none make more money. The rules are 52% and −$63, with 6 days above 70%. The earlier MACD-only grid bottomed out around −$105 and topped out around 53% wins. The one green MACD+RSI cell was +$36 at 48% wins. This rule's best win rate is 38%, and its best net is −$172.

| Book | Trades | Win rate | Avg win / avg loss | Net | Days above 70% | Oct 26–29 |
| --- | --- | --- | --- | --- | --- | --- |
| Current rules | 65 | 52% | +$6.66 / −$9.34 | −$63 | 6 | 8/15, −$27 |
| 12/26/9 slope, no stop | 319 | 34% | +$18.33 / −$11.21 | −$356 | 0 | 17/59, −$44 |
| 12/26/9 slope, $0.50 stop | 324 | 31% | +$17.62 / −$8.87 | −$172 | 0 | 16/60, −$23 |
| 6/13/5 slope, no stop | 562 | 30% | +$13.42 / −$8.93 | −$1,286 | 0 | 37/97, −$134 |
| 6/13/5 slope, $0.50 stop | 572 | 29% | +$13.03 / −$7.89 | −$1,081 | 0 | 33/97, −$166 |
| 12/26/9, histogram shrinks 1 bar, no stop | 326 | 34% | +$13.38 / −$9.22 | −$496 | 0 | 18/59, −$130 |
| 12/26/9, histogram shrinks 2 bars, no stop | 279 | 38% | +$16.68 / −$12.09 | −$323 | 0 | 20/53, +$11 |
| 12/26/9 on Heikin Ashi, slope, no stop | 314 | 33% | +$20.79 / −$11.97 | −$318 | 0 | 18/57, −$2 |

The curl does let winners run. A winning 12/26/9 trade averages about $18, against about $7 on the rules' fixed targets. That is not enough. You only win about a third of the time, the average loss is still about $11, and 319 trades cost about $415 in fees. Before fees that book is only about +$59. The $0.50 stop cuts the average loss to about $9 and cuts the 22-day loss from $356 to $172. It also drops the win rate from 34% to 31%, and $172 is still worse than the rules' $63. The fast MACD loses before fees as well (about −$555 on the no-stop version). The white/pink histogram definition is the same shape, a bit worse. Heikin Ashi does not rescue it.

Across all 12 cells the win rate runs 29–38% (median 32%) and the net runs −$1,286 to −$172 (median −$373). **Zero cells have a single day above 70%.** Not one morning, in any version.

### This week

| Day | Rules | 12/26/9 slope, no stop | 12/26/9 slope, $0.50 stop |
| --- | --- | --- | --- |
| 10/26 | 2/3, +$8 | 3/11, +$50 | 3/12, +$56 |
| 10/27 | 1/2, −$3 | 6/13, +$62 | 6/13, +$62 |
| 10/28 | 2/3, −$2 | 5/18, −$40 | 5/18, −$32 |
| 10/29 | 3/7, −$30 | 3/17, −$116 | 2/17, −$110 |
| Week | 8/15, −$27 | 17/59, −$44 | 16/60, −$23 |

Thursday is 3-for-17 or 2-for-17. Two of the non-decision cells are green on this week only (the 2-bar histogram with the $0.50 stop is about +$40 on the week, and the HA slope with the stop is about +$78). Both lose more than $230 over the 22 days, and neither has a day above 70%. A good week inside a losing rule is the trap.

### Per day, the rule as he described it (12/26/9, regular close, slope)

No day passes 70%. The best win rate on a single day in the no-stop book is 7/12 on October 23 (58%). October 13 makes +$124 and is still only 6/12.

| Day | No stop | $0.50 stop |
| --- | --- | --- |
| 09-30 | 2/17, −$191 | 2/17, −$137 |
| 10-01 | 9/20, −$40 | 6/20, −$106 |
| 10-02 | 5/15, −$61 | 4/15, −$47 |
| 10-05 | 5/15, +$11 | 5/15, +$11 |
| 10-06 | 4/11, −$17 | 4/11, −$23 |
| 10-07 | 5/14, −$45 | 5/14, −$41 |
| 10-08 | 6/12, +$43 | 6/12, +$59 |
| 10-09 | 5/14, −$32 | 5/14, −$31 |
| 10-12 | 3/13, −$30 | 3/13, −$7 |
| 10-13 | 6/12, +$124 | 6/12, +$132 |
| 10-14 | 4/16, −$94 | 4/18, −$79 |
| 10-15 | 9/19, −$38 | 9/20, +$1 |
| 10-16 | 4/12, −$85 | 4/12, −$44 |
| 10-19 | 5/18, −$7 | 5/18, +$22 |
| 10-20 | 4/12, +$68 | 5/13, +$112 |
| 10-21 | 5/16, −$62 | 4/16, −$45 |
| 10-22 | 4/12, +$82 | 4/12, +$98 |
| 10-23 | 7/12, +$61 | 5/12, −$24 |
| 10-26 | 3/11, +$50 | 3/12, +$56 |
| 10-27 | 6/13, +$62 | 6/13, +$62 |
| 10-28 | 5/18, −$40 | 5/18, −$32 |
| 10-29 | 3/17, −$116 | 2/17, −$110 |

The other eight cells' per-day rows are in `research/macd_backtest_results.json`.

### Multiple testing

Twelve cells, chosen before the run, on the same 22 days. The best of 12 is the number a search would want to keep, and that number is −$172 with a 31% win rate and zero days above 70%. There is no green cell to talk ourselves into. The $0.50 stop is the version that loses the least, and it loses less by cutting losers, not by winning more often. I would not trade this, and I would not put it on the paper book.

## Follow-up: enter on the hook, get out quickly

Xavier clarified the rule after the 2:30 PM CT chart on October 29. The MACD was curling up from below zero into a discount zone, a green Heikin Ashi candle printed, and his BUY mark was on. He would enter as soon as the MACD line starts to curve, not after it crosses the signal line, and he would be in and out, taking whatever profit is there.

Coded before this run, 13 cells:

- Entry is the slope flip itself. Call on the first bar the MACD line turns up. Put on the first bar it turns down. One check uses a one-bar histogram turn instead (the white/pink bar).
- Quick exit, every cell: a $0.30 QQQ disaster stop, plus one of +5% in 2 minutes, +10% in 3 minutes, +15% in 3 minutes, or +10% in 3 minutes or the first Heikin Ashi bar in the trade's direction, whichever comes first.
- Speeds 12/26/9 and 6/13/5, regular closes. The eight morning slope cells are the decision set.
- A context filter meant to match the photo: MACD line still on the right side of zero and in the outer 25% of its last 30 values, and price beyond both VWAP and EMA20. Tested in the morning and across the full session, 08:30–14:59 CT.
- One position. No 12-trade cap. Same $0.50 premium, 0.22 delta, $1.30 round trip.

What the fees do to a book this fast: +5% of a $0.50 option is $2.50, which is **$1.20 after the $1.30 fee**. +10% nets $3.70. +15% nets $6.20. The $0.30 stop is 0.30 × 0.22 × 100 = $6.60, **about $7.90 after fees**. A time exit that goes nowhere is a $1.30 loss. You need roughly a 5-to-1 win rate just to tread water at +5%, because one stop eats five of those wins.

### Today, 2:17 PM CT

The hook is real, and it is not at 2:30. On the 12/26/9 line:

| Time | QQQ | HA | MACD line | Histogram | What happened |
| --- | --- | --- | --- | --- | --- |
| 14:16 | 712.44 | red | −0.069 | −0.086 | Still falling. Under EMA and under VWAP. |
| 14:17 | 712.77 | green | −0.065 | −0.065 | **Line turns up.** Still below zero, bottom fifth of the last 30 readings, price under both EMA20 (712.83) and VWAP (714.46). |
| 14:18 | 713.07 | green | −0.037 | −0.030 | The +10% target is hit. Quick book is out, **+$3.70**. |
| 14:20 | 713.17 | green | +0.005 | +0.012 | This is the signal-line cross the older rule waited for. |
| 14:30 | 714.30 | green | +0.243 | +0.099 | The push on the photo. No new hook. |
| 14:33 | 714.41 | green | +0.349 | +0.119 | Still the same upswing. |
| 14:35 | 713.83 | red | +0.329 | +0.059 | Line turns down. |

The 14:17 bar is the photo: discount, MACD curling up from below zero, green Heikin Ashi. The in-and-out rule took it and was flat at 14:18. Holding that same entry to the 14:33 close is 712.77 to 714.41, about +$35 on this proxy, before any giveback. That is why the chart feels like a winner. The rule he asked to test does not hold it. Nothing between 14:25 and 14:35 is a new curl-up.

### Does the quick book beat the rules?

No. Six of the 13 cells win more often than the rules' 52%. **None make more money.** The best net in the grid is −$159. The rules are −$63. The highest win rate is 66%, on the +5% / 2-minute package, and that cell loses **$1,065**. Its average win is $1.20 and its average loss is $6.66. October 29 on that package is 26 wins out of 34 (76%) and still −$32. A day can clear 70% and lose money when the win is a fee-sized scalp and the loss is a $0.30 stop.

| Book | Trades | Win rate | Avg win / avg loss | Fees | Net | Days above 70% | Oct 26–29 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Current rules | 65 | 52% | +$6.66 / −$9.34 | $85 | −$63 | 6 | 8/15, −$27 |
| 12/26/9 hook, +10%, 3 min, morning | 675 | 56% | +$3.56 / −$7.05 | $878 | −$781 | 2 | 58/114, −$179 |
| same, also exit on the first green/red bar | 745 | 46% | +$3.22 / −$5.29 | $968 | −$1,049 | 0 | 52/123, −$210 |
| 12/26/9 hook, +5%, 2 min, morning | 719 | 66% | +$1.20 / −$6.66 | $935 | −$1,065 | 8 | 76/120, −$190 |
| 12/26/9 hook, +15%, 3 min, morning | 650 | 45% | +$5.48 / −$6.96 | $845 | −$905 | 0 | 51/111, −$133 |
| 6/13/5 hook, +10%, 3 min, morning | 913 | 55% | +$3.56 / −$7.18 | $1,187 | −$1,174 | 1 | 76/152, −$271 |
| Photo filter, 12/26/9, morning | 185 | 55% | +$3.09 / −$5.72 | $240 | −$159 | 4 | 16/31, −$46 |
| Photo filter, full session | 336 | 48% | +$2.93 / −$4.82 | $437 | −$371 | 0 | 26/60, −$89 |
| No filter, full session, 12/26/9 | 1,348 | 43% | +$2.97 / −$4.58 | $1,752 | −$1,781 | 0 | 94/228, −$341 |

The photo filter is the least-bad version. It cuts the morning from 745 trades to 185 and from −$1,049 to −$159. Before fees that filtered book is about +$81. The fees are $240, so the edge it has is smaller than the commission. Four of 22 days are above 70%. This week it is 16/31 and −$46, and Thursday's filtered morning is 4/8, −$7. Opening the same filter to the afternoon makes it worse (−$371, no day above 70%).

The unfiltered hook, morning only, on the +10% target with the color exit, loses money every single day of the 22. Per day it runs from about −$2 to −$114. There is no day to point at.

### Per day, the photo filter in the morning

12/26/9, enter on the hook only when MACD is extended through zero and price is beyond VWAP and EMA20, out at +10% or the first favorable Heikin Ashi bar or 3 minutes or the $0.30 stop.

| Day | Wins/trades | Win rate | Net | |
| --- | --- | --- | --- | --- |
| 09-30 | 2/5 | 40% | −$14 | |
| 10-01 | 2/6 | 33% | −$12 | |
| 10-02 | 4/12 | 33% | −$35 | |
| 10-05 | 6/9 | 67% | −$1 | |
| 10-06 | 5/9 | 56% | +$2 | |
| 10-07 | 5/8 | 62% | −$8 | |
| 10-08 | 6/10 | 60% | −$3 | |
| 10-09 | 5/11 | 45% | −$31 | |
| 10-12 | 3/8 | 38% | −$20 | |
| 10-13 | 5/9 | 56% | −$10 | |
| 10-14 | 7/9 | 78% | +$10 | pass |
| 10-15 | 7/8 | 88% | +$24 | pass |
| 10-16 | 4/7 | 57% | −$5 | |
| 10-19 | 4/7 | 57% | −$3 | |
| 10-20 | 3/6 | 50% | −$1 | |
| 10-21 | 7/13 | 54% | −$9 | |
| 10-22 | 6/7 | 86% | +$14 | pass |
| 10-23 | 5/10 | 50% | −$12 | |
| 10-26 | 2/3 | 67% | −$1 | |
| 10-27 | 5/13 | 38% | −$46 | |
| 10-28 | 5/7 | 71% | +$8 | pass |
| 10-29 | 4/8 | 50% | −$7 | |

The other cells' per-day rows are in `research/macd_backtest_results.json`.

### Multiple testing

Thirteen cells, named before the run, on the same 22 days. Six of them beat the rules on win rate and every one of those six loses more money than the rules, most of them by hundreds of dollars. The best dollar figure in the list, −$159, is the photo filter, and its 95% lower bound on the 55% win rate is 48%. That is not a hidden winner. It is a small gross edge that a $1.30 ticket erases. I would not trade the hook as an in-and-out book, and I would not add it to the paper rules.

## Follow-up: Bollinger touch plus the MACD hook

Xavier's line: a MACD that is starting to cross, on a Bollinger Band touch, is the best sign of a reversal. The last test took today's 2:17 PM CT hook for +$3.70 and was flat before the push. Holding that same entry to 2:35 would have been worth keeping. So this test holds.

Coded before the run. Thirteen cells.

- Bands are the 20-bar average ± 2.0 standard deviations (population, same as the signal engine). One check uses 2.5.
- A call needs the low through the lower band on this bar or within the previous N bars, and a MACD trigger. Puts use the upper band. N is 2 in the main test (the touch can be this bar or the two before it). One check requires the touch on the same bar.
- Two triggers: the first bar the MACD line turns, and the signal-line cross.
- Optional filter, one cell: MACD line still below zero for a call and above zero for a put.
- Exits, each with a disaster stop: hold until the MACD line curls back against the trade; exit at the middle band; exit at the opposite band; or hold until the option is up 20% and then sell when the line curls back. The main stop is $0.50 of QQQ. One check uses $0.30.
- 12/26/9, with 6/13/5 as a speed check. Regular closes. Morning entries, and two full-session cells (08:30–14:59). A trade entered in the morning can be held past noon until the exit or the last regular bar. One position. No 12-trade cap. Same $0.50 / 0.22 / $1.30 proxy.

The decision set is the four morning 12/26/9 cells with the 2.0 bands, a touch within 2 bars, no zero filter, and the $0.50 stop: curl exit, signal-line cross with a curl exit, middle-band exit, and the +20% latch.

### Today, 2:17 PM CT

The lower band was tagged on the way down, then the line turned up one bar later.

| Time | Low | Lower band (20, 2) | MACD line |
| --- | --- | --- | --- |
| 14:14 | 712.42 | 712.59 | −0.011, low through the band |
| 14:15 | 712.46 | 712.51 | still through the band |
| 14:16 | 712.41 | 712.44 | still through the band |
| 14:17 | 712.44 | 712.43 | **line turns up**, −0.065, green Heikin Ashi. The low misses the band by a cent. |
| 14:20 | 712.90 | 712.45 | signal line crosses up. The band touch is now four bars old. |
| 14:35 | 713.83 | 712.45 | line turns down. |

The hook-plus-touch rule, with N=2, takes the call at 14:17 because 14:16 was a touch. Requiring the touch on the same bar misses it. Waiting for the signal-line cross also misses it: by 14:20 the touch is too old. MACD is still below zero at 14:17, so the photo filter would have taken it too.

On the full-session book, that trade scores:

| Exit | Out | Result |
| --- | --- | --- |
| Curl back, at 14:35 | 713.83 | **+$21.91** |
| +20% latch, then the same curl | 14:35 | **+$21.91** |
| Middle band | 14:18 | +$2.07 |

Holding to the curl is the trade on the chart. Selling at the middle band gives it back. The morning window does not take this trade at all. It is after noon.

### Does it beat the rules?

On dollars, several hold versions do. On win rate, none do. The rules win 52% and make −$63, with 6 days above 70%. Every Bollinger cell wins less often than that. The best win rate in the 13 is 49%.

| Book | Trades | Win rate | Avg win / avg loss | Net | Days above 70% | Oct 26–29 |
| --- | --- | --- | --- | --- | --- | --- |
| Current rules | 65 | 52% | +$6.66 / −$9.34 | −$63 | 6 | 8/15, −$27 |
| Hook + band, hold to the curl, morning | 212 | 29% | +$23.47 / −$7.89 | +$240 | 0 | 11/32, +$14 |
| Signal-line cross + band, hold to the curl | 53 | 34% | +$17.93 / −$9.86 | −$22 | 4 | 4/8, +$17 |
| Hook + band, exit at the middle band | 220 | 47% | +$5.34 / −$8.71 | −$455 | 1 | 15/32, −$91 |
| Hook + band, +20% then curl | 188 | 37% | +$23.41 / −$10.67 | +$345 | 0 | 12/28, +$32 |
| Same hook, exit at the opposite band | 225 | 49% | +$17.75 / −$12.09 | +$562 | 1 | 16/32, +$23 |
| Fast 6/13/5, hold to the curl | 325 | 34% | +$16.51 / −$7.93 | +$159 | 1 | 21/53, +$67 |
| Stricter 2.5 band, hold to the curl | 74 | 24% | +$20.91 / −$8.02 | −$73 | 1 | 5/14, +$17 |
| Touch must be the same bar | 67 | 34% | +$15.96 / −$8.38 | −$2 | 2 | 3/11, −$48 |
| Also require MACD through zero | 199 | 29% | +$23.52 / −$7.81 | +$263 | 0 | 9/29, −$7 |
| $0.30 stop instead of $0.50 | 220 | 24% | +$20.71 / −$6.57 | −$27 | 0 | 11/32, +$45 |
| Full session, hold to the curl | 380 | 27% | +$19.71 / −$6.79 | +$175 | 0 | 17/63, −$68 |

Holding is the part that pays, in this sample. The curl exit, the +20% latch, and the opposite-band exit are all green, on the standard speed and on the fast one. Selling at the middle band loses $455, and it loses before fees too. That is the same lesson as the scalp test, from the other direction: taking the first profit at the mean gives the reversal away.

It still is not his bar. The profitable morning curl book is above 70% on **zero** days. You are wrong about 7 trades in 10. The average winner is large enough that the dollars come out ahead anyway. October 1 (+$149), October 15 (+$102), and October 23 (+$119) are more than the entire +$240. Drop those three days and the book is about −$130. This week the same book is 11/32 and +$14. Thursday morning is 2/5 and −$12.

The checks that should have confirmed a real rule do not. A 2.5 band loses $73. Requiring the touch on the hook bar itself is flat. A $0.30 stop, which sounds safer, loses the dollars and drops the win rate to 24%. Opening it to the full session makes this week −$68 even though the 22-day total stays green. Requiring the MACD to still be through zero, which is today's photo, is about the same book (+$263, 29%, no day above 70%) and this week it is −$7.

### Per day, hook plus the 2.0 band, hold until the line curls back

Morning, 12/26/9, $0.50 stop. No day passes.

| Day | Wins/trades | Net | Day | Wins/trades | Net |
| --- | --- | --- | --- | --- | --- |
| 09-30 | 0/6 | −$44 | 10-14 | 4/11 | +$22 |
| 10-01 | 4/10 | +$149 | 10-15 | 5/12 | +$102 |
| 10-02 | 2/14 | −$79 | 10-16 | 4/10 | +$35 |
| 10-05 | 2/9 | −$19 | 10-19 | 1/12 | −$18 |
| 10-06 | 2/14 | −$11 | 10-20 | 2/8 | +$13 |
| 10-07 | 1/7 | −$22 | 10-21 | 2/8 | −$7 |
| 10-08 | 3/10 | −$13 | 10-22 | 4/13 | +$24 |
| 10-09 | 2/9 | −$42 | 10-23 | 6/9 | +$119 |
| 10-12 | 3/8 | −$9 | 10-26 | 2/7 | −$17 |
| 10-13 | 3/10 | +$25 | 10-27 | 2/8 | −$13 |
| | | | 10-28 | 5/12 | +$56 |
| | | | 10-29 | 2/5 | −$12 |

The other cells' per-day rows are in `research/macd_backtest_results.json`.

### Multiple testing

Thirteen cells, named first, on the same 22 days as every earlier grid. Seven are green on dollars. Three more lose less than the rules' −$63 and are still red. The three that lose more than the rules are the two middle-band exits and the 2.5-band curl. The green result is not one lucky exit: the curl, the +20% latch, and the far band agree, and the fast MACD agrees. The cells that tighten the idea (wider bands, same-bar touch, tighter stop) do not. That is stronger than a single best cell, and it is still a 29% win-rate system whose profit sits in three days. Xavier ranks the win rate first, and this loses that comparison to the book he already has. I would not replace the rules with it. Twenty-two days is not enough to trust a reversal that is wrong most of the time, even when the winners are large.

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

The 48-cell MACD grid, the 24-cell MACD+RSI grid, the 12-cell curve-exit grid, the 13-cell in-and-out grid, and the 13-cell Bollinger grid were scored on the same days they are reported on. That is why each test uses a list written down first, and why a grid maximum is quoted and then ignored. Nothing was held out. A later month can disagree, especially on the filter and on the one green RSI-reversal cell, where moving one or two trades, or widening the confirmation window from 3 bars to 5, changes the sign of the dollars.

The option proxy matches Thursday's adverse stops and over-credits fast favorable wicks. If anything, that bias helps the chop target, which is the framework MACD needed in order to lose the least. It did not produce a MACD book that wins.

Rerun with `python3 research/macd_only_backtest.py`. The machine-readable dump is `research/macd_backtest_results.json`.
