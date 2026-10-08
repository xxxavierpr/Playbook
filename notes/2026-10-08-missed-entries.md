# Thu 2026-10-08 — missed entries, and the 749 put

Review only. The book is unchanged. This file is pointers for a slow screenshot executor. It is not an order and it does not change the rails.

Trinity reads Webull through a screenshot-and-click loop that takes about 30–90+ seconds per cycle. The entry is a 1-minute Heikin Ashi close across EMA20. Both misses today were that close going unread until the bar was already gone. The 9:04 call was a valid reclaim. The 9:41 put was a valid cross, and the ~$0.80 no-chase band did not say to skip it.

The ticket that was taken, the 749 put, is in the last section.

Times are CT. Market opened 8:30. Distances below are arithmetic on the prints in this note. Where a live reading was not recorded, it is left blank.

## Process / tooling

Ranked by what would have changed the two misses, then by how safe it is to leave running next to a live ticket. Last week an Enter keypress submitted an order. Anything that fills a ticket has to survive that.

1. **Compute the 1-minute close on the box, and let the desktop agent only click.** Impact: highest. Safety: high, if the script cannot type into Webull.
   Why: the 9:04 close was the trigger and the agent only noticed around 9:06–9:07; the 9:41 close was the trigger and the 9:42 close was already too late to confirm.
   A script on the machine reads a 1-minute feed that prints the bar as it closes, builds the HA close, EMA20, and RSI14, and emits one line at the minute: side, bar close, EMA20, RSI14, and cents past EMA. The screenshot loop only has to click from that line. A 15-minute-delayed quote is the wrong feed for this.

2. **Keep an incomplete ticket ready, and finish it only after that line names a side.** Impact: high. Safety: acceptable only with the guardrails in this item.
   Why: even after the late read, building the 9:04 buy still ran about 9:08–9:10, and a fully filled ticket is what a stray Enter can send.
   A limit typed before the signal is a stale ask. With quantity already 1, that same ticket is a complete order.
   - Before the signal, the panel may show symbol, expiry, and the candidate strike. Quantity empty. Limit empty. No working order.
   - The script can list a call strike and a put strike. Quantity and limit go on the signaled side only.
   - Then quantity 1, limit equal to the ask on the screen, then a mouse click on Buy. No Enter.
   - On a pass or a cancel, clear quantity so the panel is incomplete again.
   - The script never sends keystrokes to the Webull window.

3. **Click before the next 1-minute close, or pass.** Impact: high. Safety: high.
   Why: the 9:04 ticket was still being built at 9:08–9:10 and was cancelled at 9:12, several closes after the trigger. A deadline stops a late read from becoming a late order.
   The signal minute is the entry window. The following close is the cutoff. That fits only when the script line is already up and the click is quantity, the live ask, and one mouse confirm. A full 90-second screenshot tour still loses the bar, and the pass is the right result.

4. **Use a Webull price alert as a backup wake-up when the script is quiet.** Impact: modest once the script is up. Safety: high.
   Why: nothing told the agent the 9:04 bar had closed, but EMA20 was 753.45 on that bar and 756.06 on the 9:41 bar, so a fixed price cannot be the entry.
   An alert near the last EMA can bring the agent to the screen. The trigger stays the HA close across EMA20. The alert only wakes the screen.

### Weighed, and not adopted

A resting stop or limit at the EMA price fills on a raw-price touch during the bar. The book wants the HA close. A resting order can also fill with nobody at the button, which is the stray-Enter failure with a timer on it. Levels stay alerts.

## Rule changes

Notes only. The book file was not edited. None of these are in force until they are written into the book on purpose.

1. **Leave the entry on the trigger bar's close.**
   Why: a "next bar confirms" rule is the 9:41 miss. The agent was already waiting on the 9:42 close and could not read it in time.
   The 9:41 cross was thin (HA close 755.99 vs EMA20 756.06, seven cents, after the 9:40 close finished four cents above its EMA). Extra certainty, if it is wanted later, is a state check from the script at the moment of the click: still on the signaled side of EMA, still inside the chase band, spread still ≤ $0.02. That check is the same bar.

2. **Leave the ~$0.80 no-chase band as written, and apply that number.**
   Why: the 9:41 put was 0.2–0.4 past EMA when it was skipped, which is inside $0.80, and the underlying then ground from the 755.99 close to ~754.1.
   The band already said to take that put. A tighter number changes the 9:41 decision only if it is pulled in through that 0.2–0.4 reading, which is the skip that gave up the grind. A looser number changes nothing. Latency caused both misses. The 9:07 call was $0.76 above the 9:04 EMA print (QQQ 754.21 vs 753.45) and $0.66 above the 9:04 close (753.55). That is inside ~$0.80 against a stale EMA. The live EMA at 9:07 was not recorded, so the 9:07 click is left unscored against the band. The 760C was 0.12/0.13 then, spread $0.01, still the book's ~$0.15 ticket.
   An option-premium chase needs the ask at the signal and the ask at the click. The only option print today is that 760C. There is no 9:04 ask and no put ask. On that one print the premium was still in range while the underlying had already moved $0.66. One print is not a new threshold. Log both asks from the script for a sample of days before moving the band onto premium.

3. **Do not add a headline veto that skips a finished EMA reclaim.**
   Why: the 9:04 call was inside the book (close back above EMA20, RSI14 ~48 so the >70 call-skip was off, MACD histogram +0.14 and rising), the first 5-minute candle was green (753.94 to 754.83), and the underlying ran to 757.18 by about 9:30 with no pullback to EMA20.
   The 9:04 call stays. Pre-open bias was bearish (oil above $105, 10Y at 5.34%, hawkish Fed minutes), and the dip to 752.11 around 8:55–9:00 is where that bias showed up. The 9:04 bar was the reclaim of that dip. VWAP was confirmation only: price was above VWAP 753.86 by about 9:06. The 9:04 VWAP itself was not recorded.
   The 9:41 put is the setup that matches the morning bias, and the underlying did follow through, from the 755.99 close to ~754.1 by about 10:10. It is the thinner cross, and on the data recorded today it is not the better setup. Seven cents through EMA. RSI, MACD, VWAP, and the option quote were not recorded on that bar. RSI14 went under 30 around 9:54, so the hard put-skip was off at 9:41 and would have blocked a later put. Max one trade a day means the two signals compete. The call was first, and it is the one with the indicators written down. The underlying also moved farther on the call (753.55 to 757.18) than on the put. There is no option P&L for either, so this note leaves the dollar ranking blank.

## Tape used

- Open context: bearish headlines. First 5-minute candle 753.94 / 754.83. Low 752.11 around 8:55–9:00.
- 9:04 call: 1-minute close 753.55 vs EMA20 753.45. Prior 9:03 bar closed below. RSI14 ~48. MACD histogram +0.14, rising. By ~9:06, price above VWAP 753.86.
- Agent read ~9:06–9:07. ~9:07: QQQ 754.21, 0DTE 760C 0.12/0.13. Buy started ~9:08–9:10. Cancelled unsubmitted at 9:12. Then 757.18 by ~9:30, price held 0.5–1.4 above EMA20, RSI14 above 70 for much of that run.
- 9:41 put: HA open 756.24, HA close 755.99, EMA20 756.06. 9:40 close 756.11 vs EMA20 756.07. Later read 0.2–0.4 below EMA and falling, skipped as a chase. Grind to ~754.1 by ~10:10. RSI14 under 30 around 9:54. Bounces failed under EMA20.
- 10:10 snapshot: QQQ 754.13, EMA20 754.49, VWAP 754.90, RSI14 38.5.

## Left blank on purpose

No 9:04 option ask, no 9:41 option quote, no 9:41 RSI, MACD, or VWAP, no live EMA at 9:07 or at the 9:41 read. The 749 put that was filled is below. Nothing else is guessed here.

## The 749 put that was taken

Today's one trade, after the two misses above. Review only. Result +$0.01 a contract, about +$1 gross, about +$0.85–0.90 net.

### What matched

At 10:10, QQQ 754.13 was 0.36 under EMA20 754.49 and 0.77 under VWAP 754.90, with RSI14 at 38.5. Passing on that print was right. Price was already grinding under EMA. The plan was a bounce into 754.5–754.9, which is that print's EMA to VWAP, and a red close back under EMA20. That is the book's cross. VWAP stays confirmation only.

The order that was recorded matches the ticket rules. Buy to open 1 QQQ 749 put, 0DTE, limit $0.16 at the ask. Sell stop $0.08, which is half of $0.16. One contract, premium on the ~$0.15 rail, hard stop at −50%. At the 10:10 plan, RSI14 38.5 left the under-30 put skip off.

The exit waited for a book reason. The 10:44 bar was green only while it was forming, so there was no HA color flip to sell. Price came back to EMA20 near 753.45 around 10:46–10:47, and there was no confirmed 1-minute close above it, so there was no EMA break to sell. From about 10:43, QQQ sat in 753.05–753.43, a 0.38 box, and the open P&L came off +$6.45 at about 10:41 (premium about $0.22) to +$1.45–2.45 by 10:46. Sell to close 1 at limit $0.17, at the bid, submitted 10:47:44, filled. The box runs from about 10:43 to that sell, which is the ~3 minute chop on the times recorded. The start bar was not stamped, so it is not a scored 3:00. Flat well before 2:45.

### What was wrong, or cannot be checked

The entry time was not captured. The fill sits somewhere between about 10:15 and about 10:40. No HA open or close, no EMA20, no RSI14, and no bid/ask spread on the entry bar. The plan had the right shape. This note cannot score the fill against that bar. The spread ≤ $0.02 gate and the RSI < 30 skip are unchecked at the click.

The $0.08 stop was cancelled before the limit sell, and the cancel time was not written down. The stop never hit. The marks that were recorded stayed above it, from about $0.22 at the peak to the $0.17 sale. Cancelling first still takes the hard stop off before a closing order is working.

### Pointers

Ranked by what changes the next review or the next live exit. The book was not edited.

1. **Log the entry bar at the fill.** Impact: highest for any later review. Safety: a log only.
   Why: a window from about 10:15 to about 10:40 hides the HA cross, the RSI < 30 skip, and the $0.02 spread gate, so the day's only trade cannot be passed or failed.
   One line at the fill: time, HA open, HA close, EMA20, RSI14, QQQ, bid, ask, spread, limit, strike.

2. **Lift the stop only in the same action as the sell, and put $0.08 back if the sell is rejected.** Impact: high on a live contract. Safety: this is the rail.
   Why: the −50% stop is the hard exit, and cancelling it first leaves the put with no stop until the limit is accepted. This sale filled at $0.17, and the stop was never threatened. The gap itself has no recorded length.
   If the platform allows it, send the sell limit first and cancel the stop once that sell is accepted. If one contract cannot carry two sells, cancel and submit the limit on the next click. A rejected sell gets the $0.08 stop back before anything else.

3. **Keep this chop exit. Leave trails and premium targets out.** Impact: stops a one-trade rewrite of the exit. Safety: high.
   Why: the flip and the EMA break were both unconfirmed, and the 753.05–753.43 box from about 10:43 through the 10:47:44 sell is the ~3 minute chop, with the open profit already down from +$6.45 to +$1.45–2.45 by 10:46.
   A trail at the $0.16 entry is still below the 10:46 open P&L of +$1.45–2.45 and below the $0.17 sale. It does not take the +$6.45. Selling the peak at about 10:41 would have been before the chop, before an HA flip, and before a close through EMA. That is a new target. One round trip from +$6.45 to about +$1 does not earn it. Keep recording the peak P&L and its time so a later sample can look.

4. **Stamp the chop-start bar and the stop-cancel time on the exit line.** Impact: modest, and it is what makes pointer 3 checkable next time. Safety: a log only.
   Why: "~3 minutes" and "cancelled before the sell" are the two judgments on this exit, and the only clock time recorded is the 10:47:44 submit.

