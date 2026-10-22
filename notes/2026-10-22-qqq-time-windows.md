# QQQ 0DTE: which clock has the highest win rate

Xavier, same rule as the 10/22 exit note (PR #8). Trend-only 1m Heikin Ashi retest of EMA20, one contract, entry on the bar close from 08:45 to 14:30 CT, flat by 14:45. CALL when the bias is bull, the HA bar is green, one of the prior three HA bars is red, and the HA close is within $0.15 of EMA20 or EMA-high. PUT is the mirror. Stop is $0.30 of QQQ past the entry close, target is $0.12 (about +12% at delta 0.30), and the time exit is the close of the fifth minute. A stop touch exits before a target touch. A gap through the stop fills at the open. One position. Premium proxy is $0.30 with delta 0.30, so a QQQ point is $30. A win is a positive dollar result before slippage. "Net of 1¢" subtracts $2 a trade, one cent in and one cent out.

The 10/21 file in that note replays to the same 11 trades, the same hold times, the −$2.10 time exit at 13:35, and +$33.90. Turning the trend filter off adds the same three choppy retests (08:58, 09:02 stopped −$9, 11:38). Indicators are computed on regular-hours bars only, reset at 08:30. EMA20 is the recursive span-20 average seeded with the first close. VWAP is (high+low+close)/3 from the cash open. A session is choppy when close crosses EMA20 at least four times in the last 20 bars.

## Sample

Yahoo 1-minute QQQ, regular hours, 2026-09-29 through 2026-10-22 11:49 CT. That is the free 1-minute limit: 18 sessions, 6,829 bars. The attached file replaces Yahoo for all of 2026-10-21 and for 2026-10-22 through 09:33 CT. High and low on the overlap match to the penny, which is what the stop and the target use. Yahoo's open print sits on the close more often than the attached file (13% of minutes versus 5% on the 21st). Two of 187 exits filled on a gap through the stop. 2026-10-07 is missing the 11:43 bar. 2026-10-22 stops at 11:49, so every window after that has 17 sessions of opportunity and every earlier window has 18.

A full stop is −$9 and a target is +$3.60, so the gross breakeven win rate is 71% when every loser is a full stop. After $2 of slippage the same pair needs about 87% (the win is $1.60 and the loss is −$11).

## Whole rule, 18 sessions

187 trades, 122 wins, 65.2%. Average −$0.35. Total −$65.44. Net of 1¢ −$439.44. The 95% lower bound on 65% is 58%, under the 71% gross breakeven. Calls 94, puts 93. Exits were 121 targets, 51 stops, 15 time stops. Seven sessions were green before slippage. Two were green after the $2 haircut: 10/13 (+$3.40) and 10/21 (+$11.90). Dropping the 10/21 day the rule was fit on leaves 176 trades, a 63.6% win rate, and −$99.34.

The 90.9% day was that session. It does not repeat.

## 30-minute windows

Bucket is the entry bar, Central Time, half-open. Rank is win rate, then average dollars. A window with fewer than 15 trades is marked thin. The cells that clear that line still have a 95% lower bound near 50%, so none of them establishes an 80% win rate. The 14:30 bar is the last legal entry, which is why 14:30–15:00 is one trade.

| Rank | Window | n | Win rate | Avg | Total | Net of 1¢ | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| — | 14:30–15:00 | 1 | 100% (1/1) | +$3.60 | +$3.60 | +$1.60 | thin |
| — | 09:30–10:00 | 12 | 83.3% (10/12) | +$1.50 | +$18.00 | −$6.00 | thin |
| 1 | 13:00–13:30 | 16 | 75.0% (12/16) | +$0.72 | +$11.55 | −$20.45 |  |
| 2 | 12:00–12:30 | 19 | 73.7% (14/19) | +$0.80 | +$15.21 | −$22.79 |  |
| 3 | 11:30–12:00 | 21 | 71.4% (15/21) | +$0.61 | +$12.75 | −$29.25 |  |
| 4 | 13:30–14:00 | 27 | 66.7% (18/27) | +$0.06 | +$1.74 | −$52.26 |  |
| — | 14:00–14:30 | 12 | 66.7% (8/12) | −$0.01 | −$0.15 | −$24.15 | thin |
| — | 10:30–11:00 | 12 | 66.7% (8/12) | −$0.23 | −$2.70 | −$26.70 | thin |
| 5 | 10:00–10:30 | 20 | 65.0% (13/20) | −$0.81 | −$16.20 | −$56.20 |  |
| 6 | 11:00–11:30 | 20 | 60.0% (12/20) | −$1.18 | −$23.55 | −$63.55 |  |
| — | 09:00–09:30 | 13 | 53.8% (7/13) | −$2.22 | −$28.80 | −$54.80 | thin |
| — | 12:30–13:00 | 13 | 30.8% (4/13) | −$3.68 | −$47.89 | −$73.89 | thin |
| — | 08:30–09:00 | 1 | 0/1 | −$9.00 | −$9.00 | −$11.00 | thin |

09:30–10:00 leads on both keys once the one-trade cell is set aside. It fired on 8 of 18 sessions and 6 of those sessions were green. Both losers were full −$9 stops. Removing 10/21 leaves 9/11 and +$14.40. The lower bound on 10/12 is 55%. Ten wins at $1.60 and two losses at −$11 are −$6, which is why 83% still loses the spread.

Among cells with n≥15, 13:00–13:30 has the highest win rate and 12:00–12:30 has the higher average and the broader set of green days (9 of 12, against 6 of 9). Removing 10/21 drops 13:00–13:30 to 10/14 and +$4.35, and leaves 12:00–12:30 at 12/17 and +$8.01.

12:30–13:00 was red on all 9 sessions it traded. The regime count is live at 08:49. 08:30–09:00 still produced one trade in 18 sessions, a stop at 08:55. 09:00–09:30 is the same pattern one bucket later: 6 of 13 trades are full stops and the average is −$2.22.

## Named windows

Same trades, cut where you named them. These blocks mix the strong half-hours with the weak ones, so each one loses.

| Rank | Window | n | Win rate | Avg | Total | Net of 1¢ |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 13:45–15:00 power hour | 25 | 68.0% (17/25) | −$0.15 | −$3.75 | −$53.75 |
| 2 | 09:00–10:30 | 45 | 66.7% (30/45) | −$0.60 | −$27.00 | −$117.00 |
| 3 | 10:30–12:00 lunch | 53 | 66.0% (35/53) | −$0.25 | −$13.50 | −$119.50 |
| 4 | 12:00–13:45 | 63 | 63.5% (40/63) | −$0.19 | −$12.19 | −$138.19 |
| — | 08:30–09:00 open | 1 | 0/1 | −$9.00 | −$9.00 | −$11.00 |

09:00–10:30 averages the −$2.22 half-hour from 09:00, the +$1.50 cell, and the −$0.81 cell after 10:00. Lunch is the same: 11:30–12:00 is gross positive and the hour before it is not. Power hour entries stop at 14:30, and the average is already negative before the spread.

## 5-minute cross-check

Yahoo 5-minute bars, 2026-08-24 through 2026-10-22 11:45 CT. 43 sessions, 3,316 regular-hours bars. Same prices, same trend test, and the time stop is the next 5-minute bar. The 20-bar regime count on a 5-minute chart is first defined at 10:05, and the first fill in this sample is 10:10, so 08:30–10:00 is unscored here. These are 5-minute signals with the same prices and the same 5-minute clock, a second look at the afternoon.

68 trades, 36 wins (52.9%), average −$1.85, total −$125.53, net of 1¢ −$261.53, across 29 of the 43 sessions. Named blocks: power hour 10/15 (66.7%, −$6.45, net −$36.45), 12:00–13:45 18/30 (60.0%, −$27.75, net −$87.75), 09:00–10:30 3/7 (net −$39.20), lunch 5/16 (31.3%, −$66.13, net −$98.13). The only gross-positive half-hour is 12:00–12:30, 4/5, +$5.40, net −$4.60. 10:30–11:00 is 1/6 and −$41.40. The longer sample agrees that the midday half-hour is the least bad cell it can see, and that a 60% block does not pay this target and stop.

## What to sit

Sit 09:30–10:00 CT, and 12:00–12:30 if you want a second clock with more trades. Skip 12:30–13:00 and skip the 08:30–09:00 open. Skip 09:00–09:30 with them. Every named block loses money before slippage, and every 30-minute window with more than one trade loses money after one cent. No trading-bot code was changed.
