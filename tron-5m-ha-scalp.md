# TRON Multi-Agent Options Scalp (LOCKED)
Locked by Xavier 2026-10-01 evening. Replaces Matrix/Trinity Argo HA Reversal book.

## Architecture
- **TRON** — Master Control: state machine, failsafes, routes Matrix ↔ Trinity. No broker orders.
- **Matrix** — Signal & analysis: 5m Heikin Ashi, VWAP, EMA_20. Arms setups, fires ENTRY/EXIT to TRON.
- **Trinity** — Execution & risk: contract select, buy, hard stop, market sell on TRON command.

## Global
- Tickers: **SPY, QQQ** only
- Chart: Heikin Ashi **5-minute**
- Indicators: Session VWAP, 5m EMA_20
- Session: **RTH only** 09:30–16:00 EST (08:30–15:00 CT). Ignore extended hours.
- **One contract active at a time.** One trade max until flat.
- Start scanning **at the bell** (09:30 EST).

---

## Matrix protocol

### 1. Scanning (bias → ARMED)
**CALL ARMED:** Index ABOVE VWAP; EMA_20 sloping UP and ABOVE VWAP; current or prior 5m HA low touches/dips into EMA_20.

**PUT ARMED:** Index BELOW VWAP; EMA_20 sloping DOWN and BELOW VWAP; current or prior 5m HA high touches/rallies into EMA_20.

Alert TRON when ARMED.

### 2. Entry trigger → EXECUTE ENTRY to TRON
**CALL:** 5m HA closes SOLID GREEN with **FLAT BOTTOM** (zero lower wick).

**PUT:** 5m HA closes SOLID RED with **FLAT TOP** (zero upper wick).

### 3. Exit triggers (in trade) → EXECUTE EXIT to TRON if ANY:
- **Trend break:** 5m HA closes RED (calls) or GREEN (puts)
- **EMA break:** 5m HA closes BELOW EMA_20 (calls) or ABOVE EMA_20 (puts)
- **Theta cutoff:** 3 consecutive 5m candles (15m) with no new local high (calls) / local low (puts)
- Caution only (no exit): flat-bottom/top HA prints a wick against the trend → alert TRON momentum slowing

---

## Trinity protocol

### Entry (on TRON EXECUTE ENTRY)
- 1× **0DTE or 1DTE** OTM option (calls/puts per signal)
- Target premium ~**$0.15**
- Abort if Bid/Ask spread **>$0.02**
- BUY 1× at Ask

### Risk (on fill)
- Hard stop: Entry − **50%** (stop loss order)
- No take-profit limit — hold for max extension until TRON EXIT

### Exit (on TRON EXECUTE EXIT)
- MARKET SELL immediately; cancel −50% stop

---

## TRON failsafes
1. No stacked entries — max **1** active contract
2. **3:45 PM EST (2:45 PM CT)** — FLATTEN ALL to Trinity (no overnight)
3. Matrix uses HA structure for signals; Trinity exits on **real** market prices, not HA synthetic levels
4. Kill switch still owned by TRON

## Mode notes (Xavier 2026-10-01)
- Trinity **re-armed** for this book (execution live per this prompt)
- Matrix calls ARMED / ENTRY / EXIT in Trading; TRON routes; Trinity fills
- Prior Argo 1m magnet HA Reversal + chop add-on **superseded** (keep files for journal only)
