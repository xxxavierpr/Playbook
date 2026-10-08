# Thu 2026-10-08 — two missed QQQ entries

Review only. The book is unchanged. This file is pointers for a slow screenshot executor. It is not an order and it does not change the rails.

Trinity reads Webull through a screenshot-and-click loop that takes about 30–90+ seconds per cycle. The entry is a 1-minute Heikin Ashi close across EMA20. Both misses today were that close going unread until the bar was already gone. The 9:04 call was a valid reclaim. The 9:41 put was a valid cross, and the ~$0.80 no-chase band did not say to skip it.

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

No 9:04 option ask, no 9:41 option quote, no 9:41 RSI, MACD, or VWAP, no live EMA at 9:07 or at the put read, no option P&L. Those are not guessed here.
