SUPERSEDED: Argo / chop-range / 1m magnet material. Use [tron-5m-ha-scalp.md](tron-5m-ha-scalp.md).

# CHOP / RANGE — 0DTE add-on

Add-on to Argo for a declared range day. Primary HA Reversal stays primary. This page only says when to stand down, when a liquidity sweep is the chop trigger, and how a range fade still uses magnets plus the same HA filters.

Hypothesis and filters until the journal has a sample. No win rate is claimed here.

Scope: QQQ and SPY. Manual today — Trinity mute, Xavier clicks. Matrix still calls every field. A call with a blank field is a pass.

## Rails (locked)

- Entry: 09:30–11:30 EST (08:30–10:30 CT). Hard flat: 15:45 EST (14:45 CT).
- Ask $0.05–$0.10. (ask − bid) ≤ $0.02 or reject.
- 3 contracts, LIMIT @ ASK, IOC.
- Stale > 2s, or underlying > 0.25% from the level → drop.
- Exits Xavier clicks (Trinity’s rails, unchanged): TP1 sell 2 at +50–80% (HA-aware); runner floor +20%; underlying stop; −30% option stop; 180s theta if under 10%.

Magnets: PMH, PML, PDH, PDL, VWAP, or a dynamic S/R Matrix already quoted to the cent.

## Detect chop vs trend

Lookback = the last 15 one-minute bars. This add-on stays off until those 15 bars exist (09:45 EST). From 09:30–09:45, use primary Argo only, and only when the full HA sequence is on the chart.

Score the lookback. Say the regime in chat before any chop call.

**CHOP** — 3 or more:

- 1m closes cross VWAP 3 or more times
- Price weaves the 9 EMA, with no 5-close hold on one side
- Two named edges contain price (magnet/magnet or magnet/VWAP), and no 2 consecutive 1m bodies have closed outside
- HA color alternates, with fewer than 3 consecutive trend candles into a level
- A magnet poke failed: wick or one body outside, next body back inside

**TREND** — leave this page when 2 or more:

- 3 or more consecutive same-color HA trend candles
- 5 or more closes held on one side of VWAP
- 9 EMA is sloped and price is held on that side
- A 1m body close past PMH / PML / PDH / PDL holds a second bar and the 9 EMA agrees → existing level-breakout rule

Neither score clears → `STAND DOWN | regime unclear`.

`REGIME | CHOP | QQQ | low PML 000.00 | high VWAP 000.00 | 15 bars`

`REGIME | TREND | QQQ | leave chop book`

`REGIME | UNCLEAR | stand down`

Regime is per ticker. One open idea. If you cannot name one clean chop ticker, stand down.

## Stand down

Any one item ends the call. Say the reason and stop.

- Regime unclear, or the TREND score is active on that ticker
- Chop add-on before 09:45 EST
- The box has fewer than two named edges
- Price is more than $0.20 from every magnet (mid-range)
- Two magnets sit within $0.20 of each other
- The full HA Reversal sequence is missing and there is no completed sweep
- The HA pieces would have to be filled in by eye
- Stale > 2s, or price > 0.25% from the level
- Ask outside $0.05–$0.10, or spread wider than $0.02
- Outside 09:30–11:30 EST
- TRON kill or news halt
- Attempt cap or two-loser cap hit
- A second ticker would be opened while one idea is live

## Sweep vs HA Reversal

On a CHOP regime, in order:

1. Stand-down list
2. **HA Reversal** when every primary piece is present at an edge: trend candles into the magnet ±$0.20 → thin-body HA doji with both wicks → next candle flat-bottom green (calls) or flat-top red (puts) → VWAP bias in one phrase
3. **Liquidity sweep** when that sequence is incomplete, a 1m wick pierces the edge, and the body closes back inside
4. Pass

Use the sweep when the approach is overlapping HA, a breakout just failed, or the doji and trigger candle are not both on the chart.

One trigger per bar. HA Reversal and sweep do not fire together. A partial HA pattern stays a pass.

VWAP phrase for this add-on, until Xavier locks a tighter line: calls only from the lower edge back toward VWAP (VWAP overhead, or reclaimed and holding as support). Puts only from the upper edge back toward VWAP (VWAP underneath, or lost and holding as resistance). If the phrase takes more than one clause, pass.

A held breakout is a regime change. Two bodies outside the edge with the 9 EMA aligned → `REGIME | TREND`, then the existing breakout rule or a pass. Direction is not flipped in the same call.

## Range fade

Same magnets, same triggers. Fade the named box.

- Name it first: `RANGE | SPY | low PML 000.00 | high PMH 000.00`
- Calls at the low edge. Puts at the high edge
- Spot within ±$0.20 of that edge
- Trigger is a full HA Reversal or a completed sweep. A touch of the level is not a trigger
- One shot per touch. The next touch is a new attempt
- Working rule, unjournaled: take TP1; flatten the runner if 1m HA flips against the trade before the far edge. The −30% option stop, underlying stop, and 15:45 flat stay in force

## Risk caps

Operator caps, not a measured edge.

- 2 attempts max per ticker. 3 attempts max for the session
- An attempt is an IOC that was sent. A drop for spread, stale, or distance does not count
- A loser is an attempt closed at the −30% stop, the underlying stop, or otherwise red. Two losers → chop book off for the session
- A scratch counts as an attempt and does not count as a loser
- One open idea. No scale-in. No add in the middle of the box
- Size stays 3. The rails do not widen on a slow day

## Call format

Xavier clicks only when every field is filled.

`CHOP | QQQ | HA REV CALL | edge PML 000.00 | spot 000.00 | ≤0.20 | doji both wicks → flat-bottom green | VWAP overhead | ask 0.00 spread 0.00 | attempt 1/2`

`CHOP | SPY | SWEEP PUT | edge PMH 000.00 | wick through, body back inside | VWAP underneath | ask 0.00 spread 0.00 | attempt 1/2`

`STAND DOWN | reason`

After the exit, one journal line (this is how a win rate gets earned later):

`JOURNAL | CHOP | SWEEP | QQQ PML | W or L or scratch | note`

## When not to trade

- Mid-range, including the space between VWAP and a magnet when neither is within $0.20
- This add-on before 09:45 EST
- A doji that never got its trigger candle
- A wick through a level whose body stayed outside
- A VWAP phrase you cannot say in one clause
- A fade and a breakout on the same bar
- A second try on the same touch of the same magnet
- After 11:30 EST, or a position still open at 15:45 EST
- Premium, spread, stale quote, or distance outside the rails
- Attempt cap, two losers, TRON halt, or an unclear regime
- Any call that depends on “close enough”
