# 2026-10-22 QQQ 725C entry review

Live log only. One contract. No rule change in code.

## What happened

Config C CALL on the 08:38 CT 1-minute bar. Close 713.88, EMA20 713.48 (+$0.40), VWAP 713.56 (+$0.32), RSI 56.1. Regime TRENDING with slope 0.032 and 2 crosses in 20 bars. The prior three closes were 713.64, 713.71, 713.47, so the signal was a $0.41 pop off a bar that finished a cent under the EMA. Six bars since the opposite signal. The 08:32 PUT and 08:33 CALL were both blocked as flips.

Bought 1x 22 Oct 725C at the $0.18 ask (bid $0.17) at 08:39:13. Stop $0.09, half the fill. The $0.20 ask cap skipped 724C at $0.24. 725 was the first strike at or under the cap, 11.12 points out of the money.

Regime flipped to CHOPPY at 08:41 (3 crosses) and stayed there. Mid went $0.185, $0.145, $0.125, $0.115, then $0.105 at 08:52 and 08:53 (−42% vs the fill). That is under the ~$0.13 low from the verbal note. The $0.09 stop was $0.015 under the worst mid and did not fill. Spot later printed 715.115 on the 09:01 bar (+$1.24 from the signal close). Exit was the choppy-regime +10% rule: signal at mid $0.205, sell limit $0.20, broker fill $0.21, +$3.

## Pullback on this trade

Yes. A resting limit a bit under the ask would have filled, and the entry price would have been better.

The contract did not need a long wait. Mid was $0.145 by 08:41, about two minutes after the fill, and $0.145 again at 08:42 and 08:43. A buy limit at $0.15 (85% of the $0.18 ask, rounded down to the penny) sits on that market. With a one-cent spread, mid $0.145 is bid $0.14 / ask $0.15, so the $0.15 limit is fillable inside a 5-bar arm.

A deeper $0.13 limit is a different bet. Mid did not print $0.13 in the first five minutes. It was still $0.165 at 08:44, then $0.125 at 08:46 and $0.105 at 08:52. A $0.13 order with a 5-minute fuse expires on the bounce and misses. A fuse long enough to catch $0.13 buys while spot is about $0.70 under EMA20 and the regime slope is negative. Better price, worse information. Skip that.

An EMA20 or VWAP retest used as the only trigger is also a poor fit for this tape. Price did lose the EMA by about $0.70, so a “tag and close back above” rule has nothing to buy during the washout. By the 09:01 close at 715.115 the call was already $0.21. A reclaim entry that waits for that hold pays the same or more than the ask that was skipped. The log has no spot print for each minute, so the exact reclaim bar is unknown. The open and the close of the trade are enough to show the retest gate is late.

## Rule to use

After a valid Config C break, split the entry in two.

1. Lift the ask only when the signal bar closes at least $0.75 above both EMA20 and VWAP, RSI is at least 60, and the regime is TRENDING. That is the runner path. This bar fails it (+$0.40, +$0.32, RSI 56).
2. Otherwise do not lift the ask. Rest a day limit at 85% of the signal ask, rounded down to the penny, for five 1-minute bars. This trade: $0.15. Cancel the limit if it is still open when the fifth bar closes. Do not chase.
3. Keep the half-premium stop off the actual fill. A $0.15 fill stops at $0.075, which is under today’s $0.105 low. The $0.18 fill stopped at $0.09, $0.015 under that low.

On this log the $0.15 limit fills near 08:41, while the regime is already CHOPPY. The current choppy +10% target on a $0.15 fill is $0.165, and mid printed $0.165 at 08:44. The booked win is about $1 to $1.50, smaller than the +$3 that came from sitting through $0.105 and selling $0.21. Heat is much smaller, and the stop is no longer one tick from the low. The rule improves the entry. It does not maximize this particular winner, because the exit still caps chop at +10%.

## What the rule gives up

A break that never trades 15% under the signal ask never fills. Those are the clean runners, and paying the ask is correct there. The $0.75 / RSI 60 / TRENDING gate is what keeps them. A shallow break like this morning is not in that set.

Five minutes is short on purpose. A longer rest or a limit down at $0.13 mostly fills failed breaks. That is the adverse-selection cost of “always buy the dip.”

One morning is one fill. This note does not claim the gate distances are tuned. $0.75 and RSI 60 describe “not this bar.” They should be checked on the next runners before they are hard-coded.

## Did 725 hurt

Yes, the distance hurt the path. The scanner still did what the cap says.

724C was $0.24 and correctly skipped. 725C at $0.18 was the first allowed strike, 11.12 points out. A one-cent tick is about 6% of premium, and the entry spread was the whole $0.01. The ~$0.70 spot dip took the mid from $0.185 to $0.105. The later rally from 713.88 to 715.115 paid $0.03. The logged +20% spot level was 714.48; spot went past it and the option was only about +14% at the exit signal ($0.205) and +17% on the $0.21 fill. Far out of the money, the down move in premium was larger than the up move.

Keep the $0.20 cap and the shallow-break limit is required, because noise is a large fraction of a $0.18 contract. A calmer contract means a higher cap: 723C was $0.31 and 722C was $0.41 at the same scan, both still out of the money and both closer. This log does not contain those tapes, so there is no claimed P&L for them.
