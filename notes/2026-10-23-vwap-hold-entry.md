# QQQ 0DTE: skip the first EMA20 touch

Xavier, the paper rule from the 10/22 exit note (PR #8), with entries limited to 08:45–12:00 CT. One contract. The question is whether to skip the first with-trend EMA20 retest and buy only after EMA20 fails and VWAP holds.

The 9:13 CT buy today is that first touch. The 09:12 bar closed 705.50, EMA20 705.19, slope +0.22, trending, HA green, close above VWAP. The paper trader bought the 713C at $0.46. The stop was 705.20. The 09:13 bar low was 704.90, so the $0.30 QQQ stop filled. The ticket sold at $0.39, −$7. In this proxy the same stop is −$9.

## Sample and proxy

Yahoo 1-minute QQQ, regular hours, 2026-09-29 through 2026-10-23 09:32 CT. Nineteen sessions, 7,082 bars. The slice through 2026-10-22 11:49 CT is 6,829 bars, the same count as PR #9, and 2026-10-07 is still missing the bar between 11:41 and 11:43 CT. 10/23 stops at 09:32 CT, the last complete bar when this was run, so the morning window is not finished and any signal after that is absent. `notes/2026-10-23-vwap-hold-replay.py` reprints the table from that cutoff.

Indicators reset at 08:30 on regular-hours bars. EMA20 is the recursive span-20 average seeded with the first close, and the same average is run on the high and on the low. VWAP is the cumulative average of (high+low+close)/3. Heikin Ashi resets with the session. A session is trending when close crosses EMA20 fewer than four times in the last 20 bars. Slope is EMA20 now minus EMA20 five bars ago. That count is live at 08:49.

Option P&L is the PR #8 proxy: premium $0.30, delta 0.30, so a QQQ point is $30. A win is a positive dollar result before slippage. "Net of 1¢" subtracts $2 a trade, one cent in and one cent out.

Exits, on every row:

- $0.30 QQQ stop past the entry close. The stop fills when price trades through it. A wick of exactly $0.30 does not. The published 13:35 call on 10/21 still leaves on the clock at −$2.10. A gap through the stop fills at the open.
- Target $0.12 of QQQ (+12%, +$3.60) or $0.20 (+20%, +$6.00). On a bar that touches both, the stop fills. A gap through the target fills at the target.
- Time exit is the close of the fifth minute.
- The −50% option backstop is $0.50 of QQQ at this delta, wider than the $0.30 stop, so it changed no fill. A gap can lose more than $9. The 10-second wait before the bid target is already over by the next 1-minute bar.
- One position. The paper 1-bar cooldown skips the bar after an exit.

Check against the published 10/21 ledger: same +$33.90, same 13:35 time exit of −$2.10, same hold times on the ten shared prints. Yahoo's open, which Heikin Ashi uses, puts a 10:09 call where the attached file had the 14:19 call. Both are +$3.60. The whole rule through 10/22 11:49 CT, entries out to 14:30 and no cooldown, is 192 trades, 64.6%, −$127.70. PR #9 published 187, 65.2%, −$65.44 on a series that spliced the attached file over 10/21 and the morning of 10/22. Every variant below uses the Yahoo series only.

## The rows

(a) Baseline. CALL: trending, slope > 0, close > VWAP, close > EMA20, HA green, a red HA bar in the prior three, HA close within $0.15 of EMA20 or EMA-high. PUT is the mirror. This is the paper `retest_near_only` path, and it is what bought the 09:12 signal.

(b) Do not buy that signal. Arm the side. If a bar within the next 15 minutes closes through EMA20, the level failed. Then buy the first later bar, within 20 minutes and still inside 08:45–12:00, that tagged VWAP in the last five bars (a call low at or under VWAP+$0.15) and closes back on the trade side of VWAP with the HA bar in the trade's direction. A close more than $1 through VWAP cancels the arm. A bar that holds VWAP is bought before a new EMA20 retest can re-arm the skip. The slope filter is not applied again. The fail is what turns the slope down. Requiring the trend still be on at the VWAP entry leaves 9 trades and 5 wins, −$18.00 before the spread, and it skips the 09:20 bounce, where slope was −0.42.

(b2) Same as (b), and the confirmation close also has to be back through EMA20.

(c) Buy the baseline retest only when VWAP has already held: some bar in the last 10 tagged VWAP within $0.15, and no close from that tag through the signal finished more than $0.02 through VWAP.

(d) Buy the baseline retest only when EMA20 and VWAP are within $0.50. The same cut at $0.40, $0.75, and $1.00 was run as a check. None of those four is above 70% or positive after one cent. At 09:12 the replay distance was $1.00 (EMA 705.19, VWAP 704.19). The live log printed VWAP 703.97, a distance of $1.22. Both sit outside $0.50 and $0.75, so (d) skips the 9:13 buy on either print.

## Rank

Rank is win rate, then net of 1¢. A cell has to make money after the $2 haircut to be a rule to run. None does.

| Rank | Variant | TP | Trades | Win rate | Avg win | Avg loss | Gross | Net of 1¢ | 9:13 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | (b) VWAP hold after EMA20 fails | +12% | 21 | 71.4% (15/21) | +$3.60 | −$9.55 | −$3.30 | −$45.30 | skipped |
| 2 | (d) retest only if EMA and VWAP are within $0.50 | +20% | 30 | 66.7% (20/30) | +$6.00 | −$9.00 | +$30.00 | −$30.00 | skipped |
| 3 | (d) retest only if EMA and VWAP are within $0.50 | +12% | 30 | 66.7% (20/30) | +$3.60 | −$9.00 | −$18.00 | −$78.00 | skipped |
| 4 | (a) baseline EMA20 retest | +12% | 87 | 66.7% (58/87) | +$3.58 | −$8.54 | −$40.35 | −$214.35 | taken |
| 5 | (b2) VWAP hold and close back through EMA20 | +20% | 17 | 64.7% (11/17) | +$6.00 | −$9.55 | +$8.70 | −$25.30 | skipped |
| 6 | (b2) VWAP hold and close back through EMA20 | +12% | 17 | 64.7% (11/17) | +$3.60 | −$9.55 | −$17.70 | −$51.70 | skipped |
| 7 | (a) baseline EMA20 retest | +20% | 86 | 64.0% (55/86) | +$5.93 | −$8.57 | +$60.45 | −$111.55 | taken |
| 8 | (c) both EMA20 and VWAP held | +20% | 30 | 63.3% (19/30) | +$6.00 | −$9.00 | +$15.00 | −$45.00 | skipped |
| 9 | (c) both EMA20 and VWAP held | +12% | 30 | 63.3% (19/30) | +$3.60 | −$9.00 | −$30.60 | −$90.60 | skipped |
| 10 | (b) VWAP hold after EMA20 fails | +20% | 21 | 61.9% (13/21) | +$6.00 | −$8.29 | +$11.70 | −$30.30 | skipped |

The 9:13 column is the 09:12 signal, the order the paper log filled at 09:13. Skipped means that order is not sent. (b) then buys the 09:20 VWAP hold (close 704.57, back above VWAP 704.25, HA green). The 09:21 high is 705.46, through both the +12% and the +20% target, +$3.60 or +$6.00 in the proxy. There is no option quote for that bar in this replay. (b2) waits one more bar, the 09:21 close 705.07 back above EMA20 704.81, and also targets. (c) and (d) send nothing through 09:32.

## Why 71% still loses

A full stop is −$9 and a +12% target is +$3.60, so the gross breakeven is 71%. Fifteen wins and six full stops are exactly even. One of the six losses gapped through the stop and filled at −$12.30, so the average loss is −$9.55 and the gross is −$3.30. After $2 the win is +$1.60 and a full stop is −$11, and that breakeven is about 87%. The 95% lower bound on 15/21 is 50%.

+20% is gross positive on the baseline (+$60.45), on (d) (+$30.00), and on (b) (+$11.70). After one cent each of those is red. With a $6 win and an $11 loss the spread breakeven is about 73%, and the best +20% win rate in the table is 66.7%.

The morning window does not lift the baseline off the PR #9 result. 08:45–12:00 is 58/87, 66.7%, −$40.35 before the spread. Sitting out the first EMA20 touch would have avoided today's −$7 and caught the VWAP bounce that followed. Across these 19 sessions that filter is the highest win rate in the set, and it still loses money.

No trading-bot code was changed.
