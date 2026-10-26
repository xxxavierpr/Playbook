#!/usr/bin/env python3
"""trader.py - Trinity's QQQ 0DTE executor on top of bar_signal.py (which stays signal-only).

Reads /workspace/bar-signal/latest.json at each 1-minute close and trades through the Webull
Individual OpenAPI (account 5JT43423).

DEFAULT IS DRY-RUN: it looks up contracts and quotes, builds the exact order payloads and calls
POST /trading/orders/preview, but never places, cancels or changes an order. Fills are simulated.
Only `--live` lets it call /trading/orders/place and /trading/orders/cancel.

Paper day-type switch (Xavier 2026-10-23, Monday 10/26 test): override key regime_mode.
Default off. Ignored when --live, and it is not written into the live state file.
TREND fires only when the 09:00 classifier says TREND. Those positions ride:
latch at trend_latch_pct (default 0.20 on the bid), then sell on an HA bar
against the trade or a slip back to that gain. Before the latch, sell on an
HA close through EMA20 (trend_ema_buf, default 0) or trend_qqq_stop (default
0.30). trend_tp_pct defaults to 0, so there is no hard target. trend_time_exit_min
defaults to 0, so there is no clock. trend_entry stays "retest" unless set to
"pullback" (EMA20 tag, trend direction only). regime_trend_enabled defaults
true; false still logs the check and sends no trend entry. The chop keys
tp_pct / qqq_stop / time_exit_min do not arm a trend position. CHOP fades a
VWAP tag, stop $0.05 past the signal bar (clamped $0.15-$1.00), +25% or 10
minutes. MIXED and WARMUP send nothing. Window stays 08:45-12:00 CT.

Book (Xavier's locked rules):
  Entry  SIGNAL=CALL/PUT (Config C channel break) OR alt_signal=CALL (doji_demand_bb)
         on a closed RTH bar. Config C: CALL RSI<=70 / PUT RSI>=30, chase |close-band|<=0.80,
         |QQQ-VWAP|<=3.00, flip-skip 5. Alt doji_demand_bb / doji_supply (bias-aware; *_ct = countertrend retest, +10% TP): skip chase + flip-skip
         (counter-trend bounce by design); still max 1 buy/day, ask<=0.20, spread<=0.02.
         no new entries at/after 14:35 CT, always exactly 1 contract.
         Contract: today's expiry (0DTE), OTM strike closest to the money with
         ask <= 0.20 and ask-bid <= 0.02. BUY 1 LIMIT @ ask.
  Exits  stop at -50% of fill (broker-side STOP_LOSS order in live mode).
         Below +20% nothing else exits it.
         At >= +20% (on a bar close): hold while momentum is strong; sell on the first
         loss of momentum = HA bar against the trade, or MACDh ticking against it.
         Flatten everything at 14:45 CT.
  Kill   file /workspace/bar-signal/KILL: no new orders. If it contains FLATTEN, also flatten.
"""
from __future__ import annotations

import argparse, json, math, os, sys, time, uuid
from dataclasses import dataclass, asdict
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
HERE = Path(__file__).resolve().parent
LATEST = HERE / "latest.json"
STATE = HERE / "trader_state.json"
ALT_REASONS = ("doji_demand_bb", "doji_demand_bb_ct", "doji_supply", "doji_supply_ct")
LOG = HERE / "trader.log"
KILL = HERE / "KILL"
SIGNALS_LOG = HERE / "signals.log"

CFG = dict(
    max_ask=0.20, min_ask=0.05, max_spread=0.02,
    rsi_call_max=70.0, rsi_put_min=30.0, max_ema_dist=0.80, max_vwap_dist=3.00,
    stop_frac=0.50, arm_gain=0.20, chop_tp=0.10, chop_slope=0.03, chop_crosses=3,
    first_hour_dual_ema=False, flip_skip_bars=5, rth_open=dtime(8, 30), no_entry_after=dtime(14, 35), flatten_at=dtime(14, 45),
    max_bar_age_s=30.0, fill_timeout_s=20.0, sell_timeout_s=8.0, poll_s=2.0,
    max_strikes=15, max_attempts=3,
)


# --------------------------------------------------------------------------- utils
def now_ct() -> datetime:
    return datetime.now(CT)


def occ(underlying: str, expiry: str, side: str, strike: float) -> str:
    y, m, d = expiry.split("-")
    return f"{underlying}{y[2:]}{m}{d}{'C' if side == 'CALL' else 'P'}{int(round(strike * 1000)):08d}"


def fnum(x) -> Optional[float]:
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def stop_price_for(fill: float, frac: float = 0.5) -> float:
    """-50% stop, floored to the cent so it never triggers above -50%. Min $0.01."""
    return max(0.01, math.floor(fill * (1 - frac) * 100 + 1e-9) / 100)


# Paper day-regime (notes/2026-10-23-regime-exits.md). Pure so the tests can lock it.
DAY_CLASSIFY_FROM = dtime(9, 0)
DAY_WINDOW_LO = dtime(8, 45)
DAY_WINDOW_HI = dtime(12, 0)
FADE_TAG = 0.25


def classify_day_regime(hist, or_hi, or_lo, when: dtime) -> dict:
    """hist is (close, ema, vwap) oldest to newest, including the bar being labeled.

    WARMUP before 09:00 CT or before 21 bars. TREND: <=2 EMA20 crosses in 20 bars,
    |15-bar EMA slope| >= $0.40, >=75% of those closes on the slope's side of VWAP,
    the close itself on that side, and the opening range (bars before 08:45) still
    held or price >= $0.50 from VWAP. CHOP: >=4 crosses, or |slope| < $0.20 with
    neither VWAP side above 65%. Anything else is MIXED.
    """
    blank = {"label": "WARMUP", "direction": 0, "crosses": None, "slope15": None, "side_frac": None}
    if when < DAY_CLASSIFY_FROM or len(hist) < 21:
        return blank
    window = hist[-20:]
    slope = hist[-1][1] - hist[-16][1]
    crosses, last = 0, 0
    for close, ema, _vwap in window:
        sg = 1 if close > ema else (-1 if close < ema else 0)
        if sg == 0:
            continue
        if last and sg != last:
            crosses += 1
        last = sg
    above = sum(1 for close, _ema, vwap in window if close > vwap)
    frac_up = above / 20.0
    direction = 1 if slope > 0 else -1
    side_frac = frac_up if direction > 0 else 1.0 - frac_up
    close, _ema, vwap = hist[-1]
    close_with = (close - vwap) * direction > 0
    or_hold = False
    if or_hi is not None and or_lo is not None:
        or_hold = (direction > 0 and close > or_hi) or (direction < 0 and close < or_lo)
    away = abs(close - vwap) >= 0.50
    hard = (crosses <= 2 and abs(slope) >= 0.40 and side_frac >= 0.75
            and close_with and (or_hold or away))
    maj = max(frac_up, 1.0 - frac_up)
    chop = crosses >= 4 or (abs(slope) < 0.20 and maj <= 0.65)
    if hard:
        label, direc = "TREND", direction
    elif chop:
        label, direc = "CHOP", 0
    else:
        label, direc = "MIXED", direction if close_with else 0
    return {"label": label, "direction": direc, "crosses": crosses,
            "slope15": round(slope, 4), "side_frac": round(side_frac, 4)}


def vwap_fade_side(color, high, low, close, vwap):
    """CALL: HA green, low tags VWAP by >= $0.25, close back above VWAP. PUT is the mirror."""
    if None in (high, low, close, vwap) or color not in ("green", "red"):
        return None
    if color == "green" and low <= vwap - FADE_TAG and close > vwap:
        return "CALL"
    if color == "red" and high >= vwap + FADE_TAG and close < vwap:
        return "PUT"
    return None


def fade_stop_dist(side, entry, high, low):
    """$0.05 past the signal bar, clamped to $0.15-$1.00 of QQQ."""
    if side == "CALL":
        dist = entry - (low - 0.05)
    else:
        dist = (high + 0.05) - entry
    if dist != dist:
        return None
    return min(1.0, max(0.15, dist))


class Logger:
    def __init__(self, path: Path, mode: str, echo: bool = True):
        self.path, self.mode, self.echo = path, mode, echo

    def __call__(self, event: str, **kw):
        rec = {"ts": now_ct().isoformat(timespec="milliseconds"), "mode": self.mode, "event": event, **kw}
        line = json.dumps(rec, default=str)
        with open(self.path, "a") as f:
            f.write(line + "\n")
        if self.echo:
            print(line, flush=True)
        return rec


@dataclass
class Quote:
    bid: Optional[float]
    ask: Optional[float]
    source: str
    realtime: bool


# --------------------------------------------------------------------------- order payloads
def build_order(side: str, strike: float, expiry: str, action: str, order_type: str,
                limit_price: Optional[float] = None, stop_price: Optional[float] = None,
                cid: Optional[str] = None) -> dict:
    """side CALL/PUT, action BUY/SELL. Always quantity 1 (hard rule)."""
    assert action in ("BUY", "SELL") and side in ("CALL", "PUT")
    o = {
        "client_order_id": cid or uuid.uuid4().hex,
        "combo_type": "NORMAL", "option_strategy": "SINGLE", "instrument_type": "OPTION",
        "market": "US", "symbol": "QQQ", "side": action,
        "position_intent": "BUY_TO_OPEN" if action == "BUY" else "SELL_TO_CLOSE",
        "quantity": "1", "entrust_type": "QTY", "order_type": order_type, "time_in_force": "DAY",
        "legs": [{"side": action, "quantity": "1", "symbol": "QQQ",
                  "strike_price": f"{strike:g}", "option_expire_date": expiry,
                  "instrument_type": "OPTION", "option_type": side, "market": "US"}],
    }
    if order_type in ("LIMIT", "STOP_LOSS_LIMIT"):
        o["limit_price"] = f"{limit_price:.2f}"
    if order_type in ("STOP_LOSS", "STOP_LOSS_LIMIT"):
        o["stop_price"] = f"{stop_price:.2f}"
    return o


def check_one_contract(order: dict):
    if order.get("quantity") != "1" or any(l.get("quantity") != "1" for l in order.get("legs", [])):
        raise ValueError("refusing order: quantity must be exactly 1")


# --------------------------------------------------------------------------- broker adapters
class NasdaqDelayedQuotes:
    """Fallback quote source: nasdaq.com option chain. Treated as DELAYED (~15 min)."""
    URL = ("https://api.nasdaq.com/api/quote/QQQ/option-chain?assetclass=etf&fromdate={d}&todate={d}"
           "&excode=oprac&callput=callput&money=all&type=all&limit=500")
    UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

    def __init__(self):
        self._cache = (0.0, None, {})

    def quotes(self, expiry: str, wanted: dict) -> dict:
        import requests
        ts, d, table = self._cache
        if d != expiry or time.time() - ts > 5:
            r = requests.get(self.URL.format(d=expiry), headers={"User-Agent": self.UA, "Accept": "application/json"}, timeout=6)
            rows = (((r.json() or {}).get("data") or {}).get("table") or {}).get("rows") or []
            table = {}
            for row in rows:
                k = fnum(row.get("strike"))
                if k is None:
                    continue
                table[("CALL", k)] = (fnum(row.get("c_Bid")), fnum(row.get("c_Ask")))
                table[("PUT", k)] = (fnum(row.get("p_Bid")), fnum(row.get("p_Ask")))
            self._cache = (time.time(), expiry, table)
        out = {}
        for sym, (side, k) in wanted.items():
            if (side, k) in table:
                b, a = table[(side, k)]
                out[sym] = Quote(b, a, "nasdaq_delayed", False)
        return out


class WebullBroker:
    """Thin adapter over wb_api.WebullAPI. place/cancel only work when live=True."""

    def __init__(self, live: bool, log: Logger, use_nasdaq: bool = True):
        sys.path.insert(0, str(HERE))
        from wb_api import WebullAPI
        self.api = WebullAPI(live=live)
        self.live = live
        self.log = log
        self.webull_quotes_ok = True
        self.nasdaq = NasdaqDelayedQuotes() if use_nasdaq else None

    def contracts(self, expiry: str, side: str, spot: float) -> list:
        lo, hi = math.floor(spot) - 16, math.ceil(spot) + 16
        st, d = self.api.option_contracts("QQQ", expiry, side, lo, hi)
        if st != 200 or not isinstance(d, dict):
            self.log("contracts_error", status=st, body=str(d)[:300])
            return []
        out = []
        for c in d.get("data") or []:
            if c.get("expiration_date") == expiry and c.get("tradable_status") == "OC" and c.get("option_type") == side:
                out.append({"symbol": c["symbol"], "strike": float(c["strike_price"])})
        return out

    def quotes(self, expiry: str, wanted: dict) -> dict:
        out = {}
        if self.webull_quotes_ok:
            st, d = self.api.option_snapshots(list(wanted)[:20])
            if st == 200 and isinstance(d, list):
                for q in d:
                    out[q.get("symbol")] = Quote(fnum(q.get("bid")), fnum(q.get("ask")), "webull", True)
            else:
                self.log("webull_quotes_unavailable", status=st, body=str(d)[:200])
                if st == 403:
                    self.webull_quotes_ok = False   # MARKET_DATA_NOT_SUBSCRIBED: stop asking today
        if not out and self.nasdaq:
            try:
                out = self.nasdaq.quotes(expiry, wanted)
            except Exception as e:  # noqa: BLE001
                self.log("nasdaq_quotes_error", err=str(e)[:200])
        return out

    def preview(self, order: dict):
        check_one_contract(order)
        return self.api.preview(order)

    def place(self, order: dict):
        check_one_contract(order)
        if not self.live:
            raise PermissionError("place refused in dry-run")
        return self.api.place(order)

    def cancel(self, cid: str):
        if not self.live:
            raise PermissionError("cancel refused in dry-run")
        return self.api.cancel(cid)

    def order_status(self, cid: str) -> dict:
        st, d = self.api.order_get(cid)
        if st != 200 or not isinstance(d, dict):
            return {"status": "UNKNOWN", "http": st, "raw": str(d)[:300]}
        o = (d.get("orders") or [d])[0]
        return {"status": str(o.get("status") or "UNKNOWN").upper(),
                "filled_price": fnum(o.get("filled_price")),
                "filled_qty": fnum(o.get("filled_quantity")) or 0.0}

    def position_mark(self, side: str, strike: float, expiry: str) -> Optional[float]:
        st, d = self.api.positions()
        if st != 200 or not isinstance(d, list):
            return None
        for p in d:
            for leg in p.get("legs") or []:
                if (leg.get("symbol") == "QQQ" and leg.get("option_type") == side
                        and leg.get("option_expire_date") == expiry
                        and fnum(leg.get("option_exercise_price")) == strike):
                    return fnum(leg.get("last_price"))
        return None


# --------------------------------------------------------------------------- trader core
class Trader:
    def __init__(self, broker, log: Logger, live: bool = False, state_path: Path = STATE,
                 kill_path: Path = KILL, cfg: dict = None, allow_delayed_quotes: bool = False,
                 sleep=time.sleep, clock=now_ct, signals_log=None):
        self.b, self.log, self.live = broker, log, live
        self.state_path, self.kill_path = Path(state_path), Path(kill_path)
        self.cfg = {**CFG, **(cfg or {})}
        self.allow_delayed = allow_delayed_quotes
        self.sleep, self.clock = sleep, clock
        self.contract_cache = {}
        self.state = self._load()
        self.signals_log = Path(signals_log) if signals_log else None
        self._day_regime = None
        if self.signals_log and not self.state.get("side_hist"):
            self.seed_side_hist(self.signals_log)

    # ---- state
    def _fresh(self, day: str) -> dict:
        return {"day": day, "buys": 0, "attempts": 0, "position": None, "pending_buy": None,
                "last_bar_t": None, "prev_macdh": None, "done": False, "closed": [], "rth_closes": {}, "regime_hist": [], "side_hist": []}

    def _load(self) -> dict:
        day = self.clock().date().isoformat()
        try:
            s = json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            return self._fresh(day)
        if s.get("day") == day:
            return s
        # A new session drops the book. Paper keeps the override block so Monday
        # still has the keys set on Friday. Live state is rebuilt with no override.
        fresh = self._fresh(day)
        if not self.live and s.get("override"):
            fresh["override"] = s["override"]
        return fresh

    def save(self):
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, default=str))
        os.replace(tmp, self.state_path)

    def roll_day(self, now: datetime):
        if self.state.get("day") != now.date().isoformat():
            carry = None if self.live else self.state.get("override")
            self.state = self._fresh(now.date().isoformat())
            if carry:
                self.state["override"] = carry
            self.contract_cache = {}
            self.save()

    # ---- kill switch
    def kill(self) -> Optional[str]:
        if self.kill_path.exists():
            try:
                txt = self.kill_path.read_text().strip().upper()
            except OSError:
                txt = ""
            return "FLATTEN" if "FLATTEN" in txt else "STOP"
        return None

    # ---- entry filters (pure)
    @staticmethod
    def is_alt_doji_demand(rec: dict) -> bool:
        """Any doji alt (bias-aware, Xavier 2026-10-22): doji_demand_bb[_ct], doji_supply[_ct]."""
        return any(rec.get(k) in ALT_REASONS for k in ("reason", "alt_reason", "entry_source"))

    def promote_alt_signal(self, rec: dict) -> dict:
        """If Config C is NONE but alt_signal is CALL/PUT, promote it for entry."""
        if rec.get("signal") in ("CALL", "PUT"):
            return rec
        alt = rec.get("alt_signal")
        if alt in ("CALL", "PUT"):
            src = rec.get("alt_reason") if rec.get("alt_reason") in ALT_REASONS else "doji_demand_bb"
            return {**rec, "signal": alt, "reason": src, "entry_source": src}
        return rec

    def entry_block_reason(self, rec: dict, now: datetime) -> Optional[str]:
        c = self.cfg
        sig = rec.get("signal")
        if sig not in ("CALL", "PUT"):
            return f"signal={sig}"
        if self.kill():
            return "kill_switch"
        ov = self.state.get("override") or {}
        if not self.live and self.state.get("done"):
            return "done"
        if self.state["buys"] >= int(ov.get("max_buys", 1)):
            return "max_1_buy_per_day" if not ov else "max_buys_override"
        if ov.get("side_only") and sig != ov["side_only"]:
            return f"side_only={ov['side_only']}"
        if self.state["attempts"] >= max(c["max_attempts"], int(ov.get("max_buys", 1))):
            return "max_attempts"
        if self.state.get("position") or self.state.get("pending_buy"):
            return "already_in_trade"
        bar_t = datetime.fromisoformat(rec["t"]).astimezone(CT)
        cd = self.reentry_cooldown_block(bar_t)
        if cd:
            return cd
        if bar_t.date() != now.date():
            return "bar_not_today"
        age = (now - (bar_t + timedelta(minutes=1))).total_seconds()
        if age > c["max_bar_age_s"]:
            return f"stale_bar age={age:.0f}s"
        if not (c["rth_open"] <= now.time() < c["no_entry_after"]):
            return f"time {now.strftime('%H:%M')} outside 08:30-14:35 entry window"
        if self.regime_mode_on():
            if not (DAY_WINDOW_LO <= bar_t.time() <= DAY_WINDOW_HI):
                return "outside_0845_1200"
            # The VWAP fade sits on VWAP, often far from the EMA band. Config C chase / RSI
            # would throw it out. TREND keeps those filters below.
            if (self._day_regime or {}).get("label") == "CHOP":
                return None
        close, ema, vwap, rsi = (fnum(rec.get(k)) for k in ("close", "ema20", "vwap", "rsi14"))
        if None in (close, ema, vwap, rsi):
            return "missing_indicator"
        alt = self.is_alt_doji_demand(rec)
        # Alt CALL (demand bounce) often prints RSI < 30; still block overbought CALL / oversold PUT.
        if sig == "CALL" and rsi > c["rsi_call_max"]:
            return f"call_rsi {rsi:.1f}>70"
        if sig == "PUT" and rsi < c["rsi_put_min"]:
            return f"put_rsi {rsi:.1f}<30"
        # Config C chase from broken band; alt doji_demand_bb skips (already at BB lower / demand).
        if not alt:
            band = fnum(rec.get("ema_high" if sig == "CALL" else "ema_low"))
            ref = band if band is not None else ema
            if abs(close - ref) > c["max_ema_dist"] + 1e-9:
                return f"ema_dist {abs(close - ref):.2f}>0.80"
        vlim = float(ov.get("max_vwap_dist", c["max_vwap_dist"])) if not self.live else c["max_vwap_dist"]
        if abs(close - vwap) > vlim + 1e-9:
            return f"vwap_dist {abs(close - vwap):.2f}>{vlim:.2f}"
        fh = self.first_hour_dual_ema_block(rec, sig, ema)
        if fh:
            return fh
        # Alt is a counter-trend bounce by design — flip-skip would usually block it.
        if alt:
            return None
        # Paper retest_trend: Config C opposite signals are ignored, so flip-skip doesn't apply (Xavier OK 10:22).
        # regime_mode TREND is that same retest.
        if not self.live and (
            (self.state.get("override") or {}).get("entry_mode") == "retest_trend"
            or (self.regime_mode_on() and (self._day_regime or {}).get("label") == "TREND")
        ):
            return None
        return self.flip_skip_block(rec, sig)

    # ---- 5-bar side-flip skip (config B, locked by Xavier 2026-10-13, effective 10-14)
    # Raw side per bar, before any filter: HA green & close > EMA20 -> CALL; HA red & close < EMA20
    # -> PUT; else NONE. Premarket bars count. A CALL/PUT signal is skipped if any of the previous
    # N bars (by minute, t-N..t-1) had the opposite raw side.
    @staticmethod
    def raw_side(color, close, ema) -> str:
        if close is None or ema is None:
            return "NONE"
        if color == "green" and close > ema:
            return "CALL"
        if color == "red" and close < ema:
            return "PUT"
        return "NONE"

    def record_side(self, rec: dict):
        t = rec.get("t")
        if not t or rec.get("signal") in ("HALT_STALE_FEED", "HALT_FEED_ERROR"):
            return
        side = self.raw_side(rec.get("ha_color"), fnum(rec.get("close")), fnum(rec.get("ema20")))
        h = [x for x in self.state.setdefault("side_hist", []) if x[0] != t]
        h.append([t, side])
        h.sort(key=lambda x: x[0])
        self.state["side_hist"] = h[-1500:]

    def bars_since_opposite(self, rec: dict, sig: str) -> Optional[int]:
        if sig not in ("CALL", "PUT"):
            return None
        opp = "PUT" if sig == "CALL" else "CALL"
        t = datetime.fromisoformat(rec["t"])
        best = None
        for ts, side in self.state.get("side_hist", []):
            n = round((t - datetime.fromisoformat(ts)).total_seconds() / 60)
            if side == opp and n >= 1 and (best is None or n < best):
                best = n
        return best

    def flip_skip_block(self, rec: dict, sig: str) -> Optional[str]:
        n = self.bars_since_opposite(rec, sig)
        k = int(self.cfg.get("flip_skip_bars", 0) or 0)
        if k and n is not None and n <= k:
            opp = "PUT" if sig == "CALL" else "CALL"
            return f"BLOCKED flip_skip: {sig}, opposite {opp} {n} bars ago"
        return None

    def seed_side_hist(self, path: Path):
        """Load today's raw sides from signals.log so a late start still sees premarket bars."""
        import re
        pat = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) CT \| \S+ ([\d.]+) \| HA (\w+) .*?\| EMA20 ([\d.]+)")
        today = self.clock().date().isoformat()
        try:
            lines = path.read_text().splitlines()
        except OSError:
            return
        for ln in lines:
            m = pat.match(ln)
            if not m or not m.group(1).startswith(today):
                continue
            t = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=CT).isoformat()
            self.record_side({"t": t, "ha_color": m.group(3), "close": m.group(2), "ema20": m.group(4)})

    # ---- first-hour dual-EMA filter (locked by Xavier 2026-10-13)
    # 08:30-09:30 CT (by bar open time): CALL needs HA close > EMA20(ext, incl. premarket) AND
    # > EMA20(RTH-only bars); PUT needs below both. RTH EMA20 is computed by the trader from the
    # raw closes of today's RTH bars it has seen (persisted in state["rth_closes"]). Seeding:
    # SMA of the first min(20, n) RTH closes, then standard EMA(alpha=2/21) over the rest. So with
    # <20 RTH bars it's the SMA of all available RTH closes (no RTH bars -> block, can't verify).
    @staticmethod
    def ema_rth_of(closes: list) -> Optional[float]:
        if not closes:
            return None
        n = min(20, len(closes))
        e = sum(closes[:n]) / n
        k = 2 / 21
        for x in closes[n:]:
            e = x * k + e * (1 - k)
        return e

    def record_rth_close(self, rec: dict):
        t, close = rec.get("t"), fnum(rec.get("close"))
        if not t or close is None:
            return
        try:
            bt = datetime.fromisoformat(t).astimezone(CT)
        except Exception:
            return
        if bt.date().isoformat() == self.state.get("day") and dtime(8, 30) <= bt.time() < dtime(15, 0):
            self.state.setdefault("rth_closes", {})[t] = close

    def rth_ema(self) -> Optional[float]:
        d = self.state.get("rth_closes") or {}
        return self.ema_rth_of([d[k] for k in sorted(d, key=lambda x: datetime.fromisoformat(x))])

    def first_hour_dual_ema_block(self, rec: dict, sig: str, ema_ext: float) -> Optional[str]:
        if not self.cfg.get("first_hour_dual_ema", False):
            return None
        bt = datetime.fromisoformat(rec["t"]).astimezone(CT)
        if not (dtime(8, 30) <= bt.time() < dtime(9, 30)):
            return None
        hc = fnum(rec.get("ha_close"))
        if hc is None:
            hc = fnum(rec.get("close"))
        er = self.rth_ema()
        ok = er is not None and ((sig == "CALL" and hc > ema_ext and hc > er) or
                                 (sig == "PUT" and hc < ema_ext and hc < er))
        if ok:
            return None
        n = len(self.state.get("rth_closes") or {})
        ers = "n/a" if er is None else f"{er:.2f}"
        msg = (f"BLOCKED first_hour_dual_ema: {sig} ha_close {hc:.2f}, ema_ext {ema_ext:.2f}, "
               f"ema_rth {ers} (rth_bars={n})")
        self.log("first_hour_dual_ema_blocked", bar=rec["t"], line=msg)
        return msg

    # ---- regime (locked by Xavier 2026-10-13, effective 2026-10-14)
    # CHOPPY if EMA20 flat: |EMA20[now] - EMA20[10 bars ago]| / 10 < chop_slope (0.03 $/bar)
    #     OR raw close crossed EMA20 >= chop_crosses (3) times across the last 15 bars.
    # Needs >= 11 bars of history; less -> "TRENDING?" (unknown, treated as trending = old rules).
    # CHOPPY: take profit at +10% (chop_tp) until the +20% latch arms; once latched, latch rules govern.
    def record_regime_bar(self, rec: dict):
        c, e = fnum(rec.get("close")), fnum(rec.get("ema20"))
        if c is None or e is None:
            return
        h = self.state.setdefault("regime_hist", [])
        if h and h[-1][0] == rec.get("t"):
            return
        h.append([rec.get("t"), c, e])
        del h[:-20]

    def regime(self) -> dict:
        h = self.state.get("regime_hist") or []
        if len(h) < 11:
            return {"regime": "TRENDING?", "slope": None, "crosses": None, "bars": len(h)}
        slope = (h[-1][2] - h[-11][2]) / 10
        w = h[-15:]
        signs = [1 if c > e else -1 if c < e else 0 for _, c, e in w]
        crosses, last = 0, 0
        for sg in signs:
            if sg == 0:
                continue
            if last and sg != last:
                crosses += 1
            last = sg
        chop = abs(slope) < self.cfg["chop_slope"] or crosses >= self.cfg["chop_crosses"]
        return {"regime": "CHOPPY" if chop else "TRENDING", "slope": round(slope, 4),
                "crosses": crosses, "bars": len(h)}

    def check_chop_tp(self, gain, m, src) -> bool:
        p = self.state["position"]
        ct = str(p.get("entry_source") or "").endswith("_ct") or bool((self.state.get("override") or {}).get("quick_tp"))
        if p.get("profit_mode") or (p.get("regime") != "CHOPPY" and not ct):
            return False
        if gain >= self.cfg["chop_tp"] - 1e-9:
            if ct and p.get("regime") != "CHOPPY":
                self.log("exit_signal", why="countertrend +10% take-profit", gain=round(gain, 3), mark=m,
                         mark_src=src, entry_source=p.get("entry_source"))
                self.sell(f"countertrend +10% take-profit (gain {gain:.0%})")
                return True
            self.log("exit_signal", why="choppy regime +10% take-profit", gain=round(gain, 3), mark=m,
                     mark_src=src, regime=p.get("regime_info"))
            self.sell(f"choppy +10% take-profit (gain {gain:.0%})")
            return True
        return False

    # ---- contract selection
    def pick_contract(self, side: str, spot: float, expiry: str):
        self.last_closer = None
        key = (side, expiry)
        if key not in self.contract_cache or not self.contract_cache[key]:
            self.contract_cache[key] = self.b.contracts(expiry, side, spot)
        allc = self.contract_cache[key]
        otm = [c for c in allc if (c["strike"] > spot if side == "CALL" else c["strike"] < spot)]
        otm.sort(key=lambda c: abs(c["strike"] - spot))
        pov = (self.state.get("override") or {}) if not self.live else {}
        if self.regime_mode_on():
            max_ask = float(pov.get("paper_max_ask", 0.60))
            min_ask = float(pov.get("paper_min_ask", 0.30))
        else:
            max_ask = float(pov.get("paper_max_ask", self.cfg["max_ask"]))
            min_ask = float(pov.get("paper_min_ask", self.cfg["min_ask"]))
        max_spread = float(pov.get("paper_max_spread", self.cfg["max_spread"]))
        cands = otm[: int(pov.get("paper_max_strikes", self.cfg["max_strikes"]))]
        if not cands:
            self.log("no_contracts", side=side, spot=spot, expiry=expiry, listed=len(allc))
            return None, None
        quotes = self.b.quotes(expiry, {c["symbol"]: (side, c["strike"]) for c in cands})
        table = []
        for c in cands:
            q = quotes.get(c["symbol"])
            row = {"symbol": c["symbol"], "strike": c["strike"],
                   "bid": q.bid if q else None, "ask": q.ask if q else None,
                   "src": q.source if q else None}
            table.append(row)
            if not q or q.ask is None:
                row["skip"] = "no_quote"; continue
            bid = q.bid or 0.0
            if (not self.live and getattr(self, "last_entry_source", None) == "retest_trend"
                    and q.ask >= 0.50 - 1e-9 and abs(c["strike"] - spot) > 5.0 + 1e-9):
                row["skip"] = "retest: ask>=0.50 and >5 OTM"; continue
            if q.ask > max_ask + 1e-9:
                row["skip"] = f"ask>{max_ask:.2f}"; continue
            if q.ask < min_ask - 1e-9:
                row["skip"] = f"ask<{min_ask:.2f}"; continue
            if q.ask - bid > max_spread + 1e-9:
                row["skip"] = "spread>0.02"; continue
            self.log("strike_scan", side=side, spot=spot, rows=table)
            self.last_closer = table[-2] if len(table) >= 2 else None
            return c, q
        self.log("strike_scan", side=side, spot=spot, rows=table, result="none_qualified")
        return None, None

    # ---- order helpers
    def wait_order(self, cid: str, timeout: float) -> dict:
        t0 = time.monotonic()
        st = {"status": "UNKNOWN"}
        while True:
            st = self.b.order_status(cid)
            if st["status"] in ("FILLED", "CANCELLED", "FAILED"):
                return st
            if time.monotonic() - t0 >= timeout:
                return st
            self.sleep(self.cfg["poll_s"])

    def cancel_and_confirm(self, cid: str) -> dict:
        r = self.b.cancel(cid)
        self.log("cancel_sent", cid=cid, resp=r)
        st = {"status": "UNKNOWN"}
        for _ in range(4):
            st = self.b.order_status(cid)
            if st["status"] in ("FILLED", "CANCELLED", "FAILED"):
                break
            self.sleep(self.cfg["poll_s"])
        self.log("cancel_result", cid=cid, status=st)
        return st

    # ---- entry
    def try_entry(self, rec: dict, now: datetime):
        side, spot = rec["signal"], float(rec["close"])
        expiry = now.date().isoformat()
        c, q = self.pick_contract(side, spot, expiry)
        if not c:
            self.log("entry_skip", reason="no_strike_meets_ask_spread", side=side, spot=spot)
            return
        if self.live and not q.realtime and not self.allow_delayed:
            self.log("entry_skip", reason="quote_not_realtime", src=q.source, strike=c["strike"],
                     hint="subscribe Webull OpenAPI US_OPTION quotes, or run with --allow-delayed-quotes")
            return
        ask = round(q.ask, 2)
        rg = self.regime()
        self.last_regime = rg
        self.log("entry_context", bar=rec["t"], side=side, strike=c["strike"], ask=ask, regime=rg,
                 bar_lag_s=self.bar_lag_s(rec, now), next_closer=getattr(self, "last_closer", None),
                 target_plus20_qqq=self.target_qqq(side, spot, c, q, getattr(self, "last_closer", None)))
        order = build_order(side, c["strike"], expiry, "BUY", "LIMIT", limit_price=ask)
        check_one_contract(order)
        self.state["attempts"] += 1
        self.save()
        if not self.live:
            pst, pbody = self.b.preview(order)
            self.log("DRYRUN_buy", bar=rec["t"], side=side, strike=c["strike"], symbol=c["symbol"],
                     bid=q.bid, ask=q.ask, quote_src=q.source, preview_status=pst, preview=pbody,
                     payload=order, stop_would_be=stop_price_for(ask))
            if pst != 200:
                self.log("entry_skip", reason="preview_failed")
                return
            self._open_position(side, c, expiry, ask, order["client_order_id"], stop_cid=None, simulated=True)
            if self.cursor_exit_on() and self.state.get("position"):
                pos = self.state["position"]
                pos["entry_qqq"] = spot
                if self.regime_mode_on() and pos.get("entry_source") == "vwap_fade":
                    dist = fade_stop_dist(side, spot, fnum(rec.get("high")), fnum(rec.get("low")))
                    pos["qqq_stop_dist"] = dist
                    pos["qqq_stop_level"] = round(spot - dist if side == "CALL" else spot + dist, 2)
                    pos["tp_pct"] = 0.25
                    pos["time_exit_min"] = 10
                elif self.regime_mode_on() and (self._day_regime or {}).get("label") == "TREND":
                    self._arm_trend_ride(pos, side, spot)
                else:
                    qs = float(self.paper_mode("qqq_stop") or 0.30)
                    pos["qqq_stop_level"] = round(spot + qs if side == "PUT" else spot - qs, 2)
                    tp = self.paper_mode("tp_pct")
                    pos["tp_pct"] = float(tp if tp is not None else 0.12)
                    pos["time_exit_min"] = float(self.paper_mode("time_exit_min") or 5)
                self.log("cursor_exit_armed", entry_qqq=spot, qqq_stop_level=pos["qqq_stop_level"],
                         exit_style=pos.get("exit_style"), tp_pct=pos.get("tp_pct"), tp_on="bid",
                         tp_min_hold_s=self.tp_min_hold_s(), time_exit_min=pos.get("time_exit_min"),
                         trend_latch_pct=pos.get("trend_latch_pct"), trend_ema_buf=pos.get("trend_ema_buf"),
                         option_backstop=pos["stop"], **self._regime_fields())
                self.save()
            return
        # live
        self.state["pending_buy"] = {"cid": order["client_order_id"], "side": side, "strike": c["strike"],
                                     "expiry": expiry, "limit": ask}
        self.save()
        st, body = self.b.place(order)
        self.log("LIVE_buy_sent", bar=rec["t"], side=side, strike=c["strike"], symbol=c["symbol"],
                 bid=q.bid, ask=q.ask, quote_src=q.source, http=st, resp=body, payload=order)
        if st != 200:
            self.state["pending_buy"] = None; self.save()
            return
        os_ = self.wait_order(order["client_order_id"], self.cfg["fill_timeout_s"])
        if os_["status"] != "FILLED":
            os_ = self.cancel_and_confirm(order["client_order_id"])
        if os_["status"] == "FILLED":
            fill = os_.get("filled_price") or ask
            self.log("LIVE_buy_filled", cid=order["client_order_id"], fill=fill)
            self.state["pending_buy"] = None
            self._open_position(side, c, expiry, fill, order["client_order_id"], stop_cid=None, simulated=False)
        else:
            self.log("LIVE_buy_not_filled", cid=order["client_order_id"], status=os_)
            if os_["status"] in ("CANCELLED", "FAILED"):
                self.state["pending_buy"] = None
            self.save()

    @staticmethod
    def bar_lag_s(rec, now):
        try:
            t = datetime.fromisoformat(rec["t"])
            return round((now - t).total_seconds() - 60.0, 1)
        except Exception:  # noqa: BLE001
            return None

    def target_qqq(self, side, spot, c, q, closer):
        """Approx QQQ price for +20% on the mark: delta ~ premium diff between adjacent strikes."""
        try:
            mid = (q.bid + q.ask) / 2
            cm = (closer["bid"] + closer["ask"]) / 2
            delta = abs(cm - mid) / abs(closer["strike"] - c["strike"])
            if delta <= 0:
                return None
            move = self.cfg["arm_gain"] * q.ask / delta
            return round(spot + move if side == "CALL" else spot - move, 2)
        except Exception:  # noqa: BLE001
            return None

    def _open_position(self, side, c, expiry, fill, cid, stop_cid, simulated):
        stop = stop_price_for(fill, self.cfg["stop_frac"])
        self.state["buys"] += 1
        self.state["position"] = {"side": side, "strike": c["strike"], "symbol": c["symbol"], "expiry": expiry,
                                  "fill": fill, "buy_cid": cid, "stop": stop, "stop_cid": None,
                                  "simulated": simulated, "peak_gain": 0.0, "profit_mode": False, "opened": self.clock().isoformat()}
        rg = getattr(self, "last_regime", None) or self.regime()
        self.state["position"]["regime"], self.state["position"]["regime_info"] = rg["regime"], rg
        self.state["position"]["entry_source"] = getattr(self, "last_entry_source", None) or "config_c"
        self.log("position_opened", side=side, strike=c["strike"], symbol=c["symbol"], fill=fill,
                 simulated=simulated, entry_source=self.state["position"]["entry_source"], stop=stop)
        self.save()
        stop_order = build_order(side, c["strike"], expiry, "SELL", "STOP_LOSS", stop_price=stop)
        if simulated:
            pst, pbody = self.b.preview(stop_order)
            self.log("DRYRUN_stop", stop=stop, fill=fill, preview_status=pst, preview=pbody, payload=stop_order)
        else:
            st, body = self.b.place(stop_order)
            self.log("LIVE_stop_sent", stop=stop, fill=fill, http=st, resp=body, payload=stop_order)
            if st == 200:
                self.state["position"]["stop_cid"] = stop_order["client_order_id"]
            else:
                self.log("ALERT_stop_not_placed", note="script will market-sell itself if mark <= stop")
            self.save()

    # ---- exits
    def mark(self) -> tuple[Optional[float], str]:
        p = self.state["position"]
        q = self.b.quotes(p["expiry"], {p["symbol"]: (p["side"], p["strike"])}).get(p["symbol"])
        if q and q.realtime and q.bid is not None and q.ask is not None:
            return round((q.bid + q.ask) / 2, 3), "webull_mid"
        if not p["simulated"]:
            m = self.b.position_mark(p["side"], p["strike"], p["expiry"])
            if m is not None:
                return m, "position_last"
        if q and q.bid is not None and q.ask is not None:
            return round((q.bid + q.ask) / 2, 3), f"{q.source}_mid"
        return None, "none"

    def momentum_lost(self, rec: dict) -> Optional[str]:
        side = self.state["position"]["side"]
        ha = rec.get("ha_color")
        h, ph = fnum(rec.get("macd_hist")), fnum(self.state.get("prev_macdh"))
        if side == "CALL":
            if ha == "red":
                return "HA red"
            if h is not None and ph is not None and h < ph:
                return f"MACDh down {ph:.3f}->{h:.3f}"
        else:
            if ha == "green":
                return "HA green"
            if h is not None and ph is not None and h > ph:
                return f"MACDh up {ph:.3f}->{h:.3f}"
        return None

    def check_stop(self):
        """Between bars: did the -50% stop trigger?"""
        p = self.state.get("position")
        if not p:
            return
        if p["simulated"]:
            m, src = self.mark()
            if m is not None and m <= p["stop"]:
                self._close("stop", m, src)
            return
        if p.get("stop_cid"):
            st = self.b.order_status(p["stop_cid"])
            if st["status"] == "FILLED":
                self._close("stop", st.get("filled_price"), "broker_stop", already_sold=True)
        else:   # no broker stop: enforce it ourselves
            m, src = self.mark()
            if m is not None and m <= p["stop"]:
                self.sell(f"stop (self-enforced) mark {m}")

    def manage(self, rec: dict, now: datetime):
        p = self.state["position"]
        m, src = self.mark()
        if m is None:
            self.log("hold", reason="no_mark_available", bar=rec["t"], **self._regime_fields())
            return
        rg = self.regime()
        p["regime"], p["regime_info"] = rg["regime"], rg
        gain = (m - p["fill"]) / p["fill"]
        p["peak_gain"] = max(p.get("peak_gain", 0.0), gain)
        if p["simulated"] and m <= p["stop"]:
            self._close("stop", m, src); return
        if self.cursor_exit_on() and p.get("simulated"):
            if not self.cursor_exit_check(rec):
                self.log("hold", reason="cursor5m_no_exit", gain=round(gain, 3), mark=m, mark_src=src,
                         bar_high=rec.get("high"), bar_low=rec.get("low"), qqq_stop_level=p.get("qqq_stop_level"),
                         **self._regime_fields())
                self.save()
            return
        if self.paper_mode("exit_mode") == "ema_break":
            if p.get("regime") == "CHOPPY" and self.check_chop_tp(gain, m, src):
                return
            why = self.ema_break_exit(rec)
            if why:
                self.log("exit_signal", why=why, gain=round(gain, 3), mark=m, mark_src=src)
                self.sell(f"ema_break at {gain:+.0%}: {why}")
                return
            self.log("hold", reason="ema_break_mode_no_break", gain=round(gain, 3), mark=m, mark_src=src)
            self.save(); return
        if self.latch(gain, m, src):
            return
        if self.check_chop_tp(gain, m, src):
            return
        if p.get("profit_mode"):
            why = self.momentum_lost(rec)
            if why:
                self.log("exit_signal", why=why, gain=round(gain, 3), mark=m, mark_src=src)
                self.sell(f"momentum lost at +{gain:.0%}: {why}")
                return
            self.log("hold", reason="above_+20%_momentum_strong", gain=round(gain, 3), mark=m, mark_src=src, regime=rg)
        else:
            self.log("hold", reason="below_+20%_only_stop_exits", gain=round(gain, 3), mark=m, mark_src=src, regime=rg)
        self.save()

    def latch(self, gain, m, src) -> bool:
        """Locked rule 2026-10-12: at +20% latch profit mode; once latched, gain <= +20% sells. True if sold."""
        p = self.state["position"]
        arm = self.cfg["arm_gain"]
        if not p.get("profit_mode"):
            if gain >= arm - 1e-9:
                p["profit_mode"] = True
                p["profit_mode_at"] = self.clock().isoformat()
                self.log("profit_mode_latched", gain=round(gain, 3), mark=m, mark_src=src)
                self.save()
            return False
        if gain <= arm + 1e-9 and p.get("peak_gain", 0.0) > arm + 1e-9:
            self.log("exit_signal", why="gave back to +20%", gain=round(gain, 3), mark=m, mark_src=src)
            self.sell(f"giveback to +20% lock (gain {gain:.0%})")
            return True
        return False

    def check_giveback(self):
        """Every poll: if latched and gain fell to +20% or below, sell now."""
        p = self.state.get("position")
        if self.cursor_exit_on() and p and p.get("simulated"):
            self.cursor_exit_check(None)
            return
        if self.paper_mode("exit_mode") == "ema_break":
            if p and p.get("regime") == "CHOPPY" and not p.get("profit_mode"):
                m, src = self.mark()
                if m is not None:
                    gain = (m - p["fill"]) / p["fill"]
                    p["peak_gain"] = max(p.get("peak_gain", 0.0), gain)
                    self.check_chop_tp(gain, m, src)
            return
        if not p or not (p.get("profit_mode") or p.get("regime") == "CHOPPY"
                         or str(p.get("entry_source") or "").endswith("_ct")
                         or bool((self.state.get("override") or {}).get("quick_tp"))):
            return
        m, src = self.mark()
        if m is None:
            return
        gain = (m - p["fill"]) / p["fill"]
        p["peak_gain"] = max(p.get("peak_gain", 0.0), gain)
        if not self.latch(gain, m, src) and self.state.get("position"):
            self.check_chop_tp(gain, m, src)

    def sell(self, reason: str):
        p = self.state["position"]
        q = self.b.quotes(p["expiry"], {p["symbol"]: (p["side"], p["strike"])}).get(p["symbol"])
        bid = q.bid if (q and q.realtime and q.bid) else None
        order = (build_order(p["side"], p["strike"], p["expiry"], "SELL", "LIMIT", limit_price=bid)
                 if bid else build_order(p["side"], p["strike"], p["expiry"], "SELL", "MARKET"))
        if p["simulated"]:
            pst, pbody = self.b.preview(order)
            m, src = self.mark()
            self.log("DRYRUN_sell", reason=reason, payload=order, preview_status=pst, preview=pbody)
            self._close(reason, bid or m, src)
            return
        if p.get("stop_cid"):
            cst = self.cancel_and_confirm(p["stop_cid"])
            if cst["status"] == "FILLED":
                self._close("stop", cst.get("filled_price"), "broker_stop", already_sold=True); return
        st, body = self.b.place(order)
        self.log("LIVE_sell_sent", reason=reason, http=st, resp=body, payload=order)
        os_ = self.wait_order(order["client_order_id"], self.cfg["sell_timeout_s"]) if st == 200 else {"status": "FAILED"}
        if os_["status"] != "FILLED" and order["order_type"] == "LIMIT":
            if st == 200:
                os_ = self.cancel_and_confirm(order["client_order_id"])
            if os_["status"] != "FILLED":
                mo = build_order(p["side"], p["strike"], p["expiry"], "SELL", "MARKET")
                st2, body2 = self.b.place(mo)
                self.log("LIVE_sell_market_sent", http=st2, resp=body2, payload=mo)
                os_ = self.wait_order(mo["client_order_id"], self.cfg["sell_timeout_s"]) if st2 == 200 else {"status": "FAILED"}
        if os_["status"] == "FILLED":
            self._close(reason, os_.get("filled_price"), "broker_fill", already_sold=True)
        else:
            self.log("ALERT_sell_not_confirmed", status=os_, note="position may still be open; check Webull")
            self.save()

    def _close(self, reason, price, src, already_sold=False):
        p = self.state["position"]
        pnl = None if price is None else round((price - p["fill"]) * 100, 2)
        self.log("position_closed", reason=reason, exit=price, exit_src=src, fill=p["fill"], pnl_usd=pnl,
                 simulated=p["simulated"], side=p.get("side"), strike=p.get("strike"),
                 entry_source=p.get("entry_source"))
        self.state["closed"].append({**p, "exit": price, "reason": reason, "pnl_usd": pnl,
                                     **({} if self.live else {"closed_at": self.clock().isoformat()})})
        if not self.live:
            self.state["last_exit_at"] = self.clock().isoformat()
        self.state["position"] = None
        if self.live:
            self.state["done"] = True
        else:
            cap = int((self.state.get("override") or {}).get("max_buys", 1))
            if self.state["buys"] >= cap:
                self.state["done"] = True
        self.save()

    def flatten(self, why: str):
        pb = self.state.get("pending_buy")
        if pb and self.live:
            st = self.cancel_and_confirm(pb["cid"])
            self.state["pending_buy"] = None
            if st["status"] == "FILLED" and not self.state.get("position"):
                c = {"symbol": occ("QQQ", pb["expiry"], pb["side"], pb["strike"]), "strike": pb["strike"]}
                self._open_position(pb["side"], c, pb["expiry"], st.get("filled_price") or pb["limit"], pb["cid"], None, False)
            self.save()
        if self.state.get("position"):
            self.log("flatten", why=why)
            self.sell(f"flatten: {why}")

    # ---- main hooks
    def on_bar(self, rec: dict, now: Optional[datetime] = None):
        now = now or self.clock()
        self.roll_day(now)
        if rec.get("t") == self.state.get("last_bar_t"):
            return
        self.log_bar_gap(rec)
        self.state["last_bar_t"] = rec.get("t")
        self.record_rth_close(rec)
        self.record_regime_bar(rec)
        self.record_side(rec)
        if self.regime_mode_on():
            self.record_day_regime(rec)
            self._day_regime = self.current_day_regime(rec)
        else:
            self._day_regime = None
        k = self.kill()
        if self.state.get("position"):
            if k == "FLATTEN":
                self.flatten("kill switch FLATTEN")
            elif now.time() >= self.cfg["flatten_at"]:
                self.flatten("14:45 CT flatten")
            else:
                self.manage(rec, now)
        else:
            if self.regime_mode_on():
                rec = self.regime_entry_signal(rec)
            elif self.paper_mode("entry_mode") == "retest_trend":
                rec = self.retest_trend_signal(rec)
            else:
                rec = self.apply_override(rec)
                rec = self.promote_alt_signal(rec)
            why = self.entry_block_reason(rec, now)
            fields = self._regime_fields()
            if why is None:
                self.log("entry_signal", bar=rec["t"], side=rec["signal"], close=rec["close"],
                         ema20=rec.get("ema20"), rsi=rec.get("rsi14"), vwap=rec.get("vwap"),
                         bars_since_opposite=self.bars_since_opposite(rec, rec["signal"]),
                         entry_source=rec.get("entry_source") or "config_c", **fields)
                self.last_entry_source = rec.get("entry_source") or "config_c"
                self.try_entry(rec, now)
            elif rec.get("signal") in ("CALL", "PUT"):
                self.log("entry_blocked", bar=rec["t"], side=rec["signal"], reason=why,
                         bars_since_opposite=self.bars_since_opposite(rec, rec["signal"]), **fields)
            else:
                if self._day_regime:
                    fields = {**fields, "reason": rec.get("reason")}
                self.log("no_entry", bar=rec.get("t"), signal=rec.get("signal"), close=rec.get("close"), **fields)
        self.record_retest_hist(rec)
        self.state["prev_macdh"] = rec.get("macd_hist")
        self.save()

    def log_bar_gap(self, rec: dict):
        """No 1m history is available to backfill (latest.json holds one bar), so log skipped bars."""
        try:
            prev = datetime.fromisoformat(self.state.get("last_bar_t"))
            cur = datetime.fromisoformat(rec.get("t"))
        except (TypeError, ValueError):
            return
        gap = int((cur - prev).total_seconds() // 60) - 1
        if 0 < gap < 60 and prev.date() == cur.date():
            missing = [(prev + timedelta(minutes=i + 1)).isoformat() for i in range(gap)]
            self.log("bar_gap", prev=prev.isoformat(), cur=cur.isoformat(), missing=missing, backfilled=False)

    # ---- paper-only override modes (Xavier 2026-10-22 10:19 CT); never active when live
    def paper_mode(self, key: str):
        if self.live:
            return None
        return (self.state.get("override") or {}).get(key)

    def regime_mode_on(self) -> bool:
        return bool(self.paper_mode("regime_mode"))

    def regime_trend_enabled(self) -> bool:
        """Paper only. Missing key stays on. Live never reaches the trend gate."""
        if not self.regime_mode_on():
            return True
        ov = self.state.get("override") or {}
        if "regime_trend_enabled" not in ov:
            return True
        return bool(self.paper_mode("regime_trend_enabled"))

    def _regime_fields(self) -> dict:
        lab = getattr(self, "_day_regime", None)
        if not lab:
            return {}
        return {"day_regime": lab["label"], "day_regime_dir": lab["direction"],
                "day_crosses": lab["crosses"], "day_slope15": lab["slope15"]}

    def record_day_regime(self, rec: dict):
        """Paper-only history for the day label. Live never calls this."""
        c, e, v = fnum(rec.get("close")), fnum(rec.get("ema20")), fnum(rec.get("vwap"))
        hi, lo = fnum(rec.get("high")), fnum(rec.get("low"))
        if None in (c, e, v):
            return
        try:
            bt = datetime.fromisoformat(rec["t"]).astimezone(CT)
        except (TypeError, ValueError, KeyError):
            return
        if bt.time() < DAY_WINDOW_LO and None not in (hi, lo):
            self.state["or_hi"] = hi if self.state.get("or_hi") is None else max(self.state["or_hi"], hi)
            self.state["or_lo"] = lo if self.state.get("or_lo") is None else min(self.state["or_lo"], lo)
        h = self.state.setdefault("day_regime_hist", [])
        if h and h[-1][0] == rec.get("t"):
            return
        h.append([rec.get("t"), c, e, v])
        del h[:-40]

    def current_day_regime(self, rec: dict) -> dict:
        h = self.state.get("day_regime_hist") or []
        try:
            when = datetime.fromisoformat(rec["t"]).astimezone(CT).time()
        except (TypeError, ValueError, KeyError):
            when = dtime(0, 0)
        triples = [(row[1], row[2], row[3]) for row in h if len(row) >= 4]
        return classify_day_regime(triples, self.state.get("or_hi"), self.state.get("or_lo"), when)

    def _paper_float(self, key: str, default: float) -> float:
        v = self.paper_mode(key)
        return default if v is None else float(v)

    def _arm_trend_ride(self, pos: dict, side: str, spot: float):
        """Trend book only. Chop tp_pct / time_exit_min / qqq_stop are not read here."""
        qs = self._paper_float("trend_qqq_stop", 0.30)
        latch = self._paper_float("trend_latch_pct", 0.20)
        hard = self._paper_float("trend_tp_pct", 0.0)
        clock = self._paper_float("trend_time_exit_min", 0.0)
        buf = self._paper_float("trend_ema_buf", 0.0)
        pos["exit_style"] = "trend_ride"
        pos["qqq_stop_dist"] = qs
        pos["qqq_stop_level"] = round(spot + qs if side == "PUT" else spot - qs, 2)
        pos["trend_latch_pct"] = latch
        pos["trend_ema_buf"] = buf
        pos["latch_armed"] = False
        pos["tp_pct"] = hard if hard > 0 else None
        pos["time_exit_min"] = clock

    def regime_entry_signal(self, rec: dict) -> dict:
        """TREND retest, or a with-trend EMA pullback when trend_entry is pullback.
        CHOP fades VWAP. MIXED and WARMUP stay flat."""
        label = (self._day_regime or {}).get("label")
        if label == "TREND":
            if self.paper_mode("trend_entry") == "pullback":
                rec = self.pullback_trend_signal(rec)
            else:
                rec = self.retest_trend_signal(rec)
            if not self.regime_trend_enabled():
                return {**rec, "signal": "NONE", "reason": "trend_disabled", "entry_source": None}
            return rec
        if label == "CHOP":
            side = vwap_fade_side(rec.get("ha_color"), fnum(rec.get("high")), fnum(rec.get("low")),
                                  fnum(rec.get("close")), fnum(rec.get("vwap")))
            if side:
                return {**rec, "signal": side, "reason": "vwap_fade", "entry_source": "vwap_fade"}
            return {**rec, "signal": "NONE", "reason": "no_vwap_fade", "entry_source": None}
        return {**rec, "signal": "NONE", "reason": f"day_regime_{label}", "entry_source": None}

    TOUCH = 0.15

    def retest_touch(self, rec: dict) -> tuple:
        """(put_touch, call_touch): bar high reached within 0.15 of EMA20/EMAl from below; low mirror."""
        hi, lo, ema, el, eh = (fnum(rec.get(k)) for k in ("high", "low", "ema20", "ema_low", "ema_high"))
        pt = None not in (hi, ema, el) and hi >= min(ema, el) - self.TOUCH
        ctch = None not in (lo, ema, eh) and lo <= max(ema, eh) + self.TOUCH
        return bool(pt), bool(ctch)

    def record_retest_hist(self, rec: dict):
        h = self.state.setdefault("retest_hist", [])
        pt, ctch = self.retest_touch(rec)
        h.append([rec.get("t"), rec.get("ha_color"), fnum(rec.get("ema20")), pt, ctch,
                  fnum(rec.get("close")), fnum(rec.get("low")), fnum(rec.get("high"))])
        del h[:-12]

    PULLBACK, BODY, STALL = 0.60, 0.10, 0.25

    def retest_tight_block(self, rec: dict, side: str) -> Optional[str]:
        """2026-10-22 11:19 tighten: real pullback in last 10 bars, confirm closes through prior
        bar's low/high with body >= 0.10, and no flat stall (prior 3 closes within 0.25 of EMA20)."""
        h = self.state.get("retest_hist") or []
        rows = [x for x in h[-10:] if len(x) >= 8 and x[5] is not None and x[2] is not None]
        if len(rows) < 3:
            return "tight_warmup"
        sgn = -1 if side == "PUT" else 1
        if not any(sgn * (x[5] - x[2]) >= self.PULLBACK - 1e-9 for x in rows):
            return "no_pullback_0.60"
        c, o = fnum(rec.get("close")), fnum(rec.get("open"))
        prev = rows[-1]
        ref = prev[6] if side == "PUT" else prev[7]
        if c is None or o is None or ref is None:
            return "no_ohlc"
        if (side == "PUT" and not (c < ref and o - c >= self.BODY - 1e-9)) or \
           (side == "CALL" and not (c > ref and c - o >= self.BODY - 1e-9)):
            return "weak_confirm"
        if all(abs(x[5] - x[2]) <= self.STALL + 1e-9 for x in rows[-3:]):
            return "flat_stall"
        return None

    def retest_trend_signal(self, rec: dict) -> dict:
        """Paper retest entry (2026-10-22 rev2). Bias = VWAP side only (close<VWAP bear, >VWAP bull).
        Bounce = an opposite-colour HA bar in the prior 3 bars. A touch (high within 0.15 of EMA20/EMAl
        for puts) arms the retest for this bar + 2 more; entry = red HA close with close < EMA20.
        Also fires on a red HA close within 0.15 of EMA20/EMAl (replay_tune sig_C). CALL mirror."""
        c, vwap, ema, el, eh, hc = (fnum(rec.get(k)) for k in ("close", "vwap", "ema20", "ema_low", "ema_high", "ha_close"))
        h = self.state.get("retest_hist") or []
        sig, why = "NONE", "no_retest"
        if None in (c, vwap, ema, el, eh, hc) or len(h) < 3:
            why = "retest_warmup"
        else:
            pt, ctch = self.retest_touch(rec)
            prior = [x[1] for x in h[-3:]]
            armed_put = pt or any(len(x) > 3 and x[3] for x in h[-2:])
            armed_call = ctch or any(len(x) > 4 and x[4] for x in h[-2:])
            red, green = rec.get("ha_color") == "red", rec.get("ha_color") == "green"
            near_put = min(abs(hc - ema), abs(hc - el)) <= self.TOUCH
            near_call = min(abs(hc - ema), abs(hc - eh)) <= self.TOUCH
            if self.paper_mode("retest_near_only"):      # PR #8: HA close within 0.15 of EMA20/EMAl(h) only
                armed_put = armed_call = False
            if c < vwap and red and "green" in prior and c < ema and (armed_put or near_put):
                sig, why = "PUT", "retest_trend_put" + ("_armed" if armed_put else "")
            elif c > vwap and green and "red" in prior and c > ema and (armed_call or near_call):
                sig, why = "CALL", "retest_trend_call" + ("_armed" if armed_call else "")
        if sig != "NONE" and self.paper_mode("retest_trend_only"):
            blk = self.cursor_trend_block(rec, sig)
            if blk:
                sig, why = "NONE", f"{why}_blocked:{blk}"
        if sig != "NONE" and self.paper_mode("retest_tight"):
            blk = self.retest_tight_block(rec, sig)
            if blk:
                sig, why = "NONE", f"{why}_blocked:{blk}"
        self.log("retest_check", bar=rec.get("t"), signal=sig, why=why, **self._regime_fields())
        return {**rec, "signal": sig, "reason": why, "entry_source": "retest_trend" if sig != "NONE" else None}

    PULLBACK_TAG = 0.40

    def pullback_trend_signal(self, rec: dict) -> dict:
        """With-trend EMA20 tag that closes back through EMA. Day direction only.
        A call needs the low in [EMA-low − 0.40, max(EMA, EMA-high) + 0.15]. Put is the mirror.
        This does not require the $0.15 HA kiss the retest uses."""
        c, vwap, ema, el, eh, hi, lo = (fnum(rec.get(k)) for k in
                                        ("close", "vwap", "ema20", "ema_low", "ema_high", "high", "low"))
        sig, why = "NONE", "no_pullback"
        rg = self.pr8_regime()
        direc = (self._day_regime or {}).get("direction") or 0
        if None in (c, vwap, ema, el, eh, hi, lo) or rg.get("slope5") is None:
            why = "pullback_warmup"
        elif direc > 0:
            tagged = (el - self.PULLBACK_TAG) <= lo <= max(ema, eh) + self.TOUCH
            if (tagged and rg["regime"] == "TRENDING" and rg["slope5"] > 0
                    and rec.get("ha_color") == "green" and c > ema and c > vwap):
                sig, why = "CALL", "pullback_ema_call"
        elif direc < 0:
            tagged = min(ema, el) - self.TOUCH <= hi <= eh + self.PULLBACK_TAG
            if (tagged and rg["regime"] == "TRENDING" and rg["slope5"] < 0
                    and rec.get("ha_color") == "red" and c < ema and c < vwap):
                sig, why = "PUT", "pullback_ema_put"
        if sig != "NONE":
            blk = self.cursor_trend_block(rec, sig)
            if blk:
                sig, why = "NONE", f"{why}_blocked:{blk}"
        self.log("pullback_check", bar=rec.get("t"), signal=sig, why=why, **self._regime_fields())
        return {**rec, "signal": sig, "reason": why, "entry_source": "pullback_ema" if sig != "NONE" else None}

    EMA_BREAK_BUF = 0.15

    def ema_break_exit(self, rec: dict) -> Optional[str]:
        """HA close beyond EMA20 by >= 0.15, or beyond EMAh (puts) / EMAl (calls)."""
        side = self.state["position"]["side"]
        hc, ema = fnum(rec.get("ha_close")), fnum(rec.get("ema20"))
        eh, el = fnum(rec.get("ema_high")), fnum(rec.get("ema_low"))
        if hc is None or ema is None:
            return None
        buf = self.EMA_BREAK_BUF
        if side == "PUT" and (hc >= ema + buf - 1e-9 or (eh is not None and hc > eh)):
            return f"HA close {hc:.2f} above EMA20 {ema:.2f}+{buf} / EMAh {eh}"
        if side == "CALL" and (hc <= ema - buf + 1e-9 or (el is not None and hc < el)):
            return f"HA close {hc:.2f} below EMA20 {ema:.2f}-{buf} / EMAl {el}"
        return None
        if side == "PUT" and hc > ema:
            return f"HA close {hc:.2f} above EMA20 {ema:.2f}"
        if side == "CALL" and hc < ema:
            return f"HA close {hc:.2f} below EMA20 {ema:.2f}"
        return None

    # ---- paper-only Cursor PR #8 rules (Xavier 2026-10-22 ~11:35 CT); every key ignored when live
    def reentry_cooldown_block(self, bar_t: datetime) -> Optional[str]:
        """No new paper entry until >= N full bars have closed after the last exit."""
        n = self.paper_mode("reentry_cooldown_bars")
        la = self.state.get("last_exit_at")
        if not n or not la:
            return None
        ex = datetime.fromisoformat(la).astimezone(CT).replace(second=0, microsecond=0)
        if bar_t < ex + timedelta(minutes=int(n)):
            return f"reentry_cooldown exit={la[11:19]} need_bar>={(ex + timedelta(minutes=int(n))).strftime('%H:%M')}"
        return None

    def pr8_regime(self) -> dict:
        """PR #8 regime: CHOPPY if close crosses EMA20 >= 4 times in last 20 bars; slope = EMA20 - EMA20[5 bars ago]."""
        h = self.state.get("regime_hist") or []
        if len(h) < 6:
            return {"regime": "WARMUP", "slope5": None, "crosses": None, "bars": len(h)}
        signs = [1 if c > e else -1 if c < e else 0 for _, c, e in h[-20:]]
        crosses, last = 0, 0
        for sg in signs:
            if sg == 0:
                continue
            if last and sg != last:
                crosses += 1
            last = sg
        return {"regime": "CHOPPY" if crosses >= 4 else "TRENDING", "slope5": round(h[-1][2] - h[-6][2], 4),
                "crosses": crosses, "bars": len(h)}

    def cursor_trend_block(self, rec: dict, side: str) -> Optional[str]:
        rg = self.pr8_regime()
        if rg["regime"] != "TRENDING":
            return f"regime_{rg['regime']}(crosses={rg['crosses']})"
        if side == "PUT" and not (rg["slope5"] < 0):
            return f"bias_not_BEAR(slope5={rg['slope5']})"
        if side == "CALL" and not (rg["slope5"] > 0):
            return f"bias_not_BULL(slope5={rg['slope5']})"
        try:
            bt = datetime.fromisoformat(rec["t"]).astimezone(CT).time()
            if not (dtime(8, 45) <= bt <= dtime(12, 0)):
                return "outside_0845_1200"
        except (KeyError, TypeError, ValueError):
            pass
        return None

    def cursor_exit_on(self) -> bool:
        if self.paper_mode("tp_pct"):
            return True
        return self.regime_mode_on()

    def tp_min_hold_s(self) -> float:
        return float(self.paper_mode("tp_min_hold_s") or 10)

    def cursor_exit_check(self, rec: Optional[dict]) -> bool:
        """QQQ stop first. A trend ride then latches, gives back, or exits on structure.
        Anything else is +tp on the bid after the min hold, then the time exit."""
        p = self.state.get("position")
        if not p:
            return False
        now = self.clock()
        held = (now - datetime.fromisoformat(p["opened"])).total_seconds()
        lvl = p.get("qqq_stop_level")
        if rec is not None and lvl is not None:
            hi, lo, cl = fnum(rec.get("high")), fnum(rec.get("low")), fnum(rec.get("close"))
            hit = (p["side"] == "PUT" and hi is not None and hi >= lvl - 1e-9) or \
                  (p["side"] == "CALL" and lo is not None and lo <= lvl + 1e-9)
            if hit:
                self.log("exit_signal", why="qqq_stop", qqq_stop_level=lvl, bar_high=hi, bar_low=lo, close=cl,
                         held_s=round(held, 1), **self._regime_fields())
                if p.get("qqq_stop_dist") is not None:
                    label = f"{float(p['qqq_stop_dist']):.2f}"
                else:
                    label = f"{float(self.paper_mode('qqq_stop') or 0.30):.2f}"
                self.sell(f"QQQ ${label} stop (level {lvl})")
                return True
        if p.get("exit_style") == "trend_ride":
            return self.trend_ride_exit(rec, p, held)
        q = self.b.quotes(p["expiry"], {p["symbol"]: (p["side"], p["strike"])}).get(p["symbol"])
        bid = q.bid if q and q.bid else None
        tp = float(p.get("tp_pct") or self.paper_mode("tp_pct"))
        if bid is not None:
            g = (bid - p["fill"]) / p["fill"]
            p["peak_gain"] = max(p.get("peak_gain", 0.0), g)
            if g >= tp - 1e-9:
                if held >= self.tp_min_hold_s():
                    self.log("exit_signal", why=f"+{tp:.0%} TP on bid", bid=bid, gain=round(g, 3), held_s=round(held, 1),
                             **self._regime_fields())
                    self.sell(f"+{tp:.0%} TP on bid (gain {g:.0%}, held {held:.0f}s)")
                    return True
                self.log("tp_too_soon", bid=bid, gain=round(g, 3), held_s=round(held, 1), need_s=self.tp_min_hold_s())
        if held >= float(p.get("time_exit_min") or self.paper_mode("time_exit_min") or 5) * 60:
            self.log("exit_signal", why="time_exit", bid=bid, held_s=round(held, 1), **self._regime_fields())
            self.sell(f"time exit {held / 60:.1f}m")
            return True
        return False

    def trend_momentum_against(self, rec: dict, side: str) -> Optional[str]:
        """Weakening momentum after the latch: an HA bar against the trade."""
        ha = rec.get("ha_color")
        if side == "CALL" and ha == "red":
            return "HA red"
        if side == "PUT" and ha == "green":
            return "HA green"
        return None

    def trend_structure_exit(self, rec: dict, side: str, buf: float) -> Optional[str]:
        """HA close through EMA20. Used only before the latch is armed."""
        hc, ema = fnum(rec.get("ha_close")), fnum(rec.get("ema20"))
        if hc is None or ema is None:
            return None
        if side == "CALL" and hc < ema - buf:
            return f"HA close {hc:.2f} through EMA20 {ema:.2f}"
        if side == "PUT" and hc > ema + buf:
            return f"HA close {hc:.2f} through EMA20 {ema:.2f}"
        return None

    def trend_ride_exit(self, rec: Optional[dict], p: dict, held: float) -> bool:
        """Latch on the option bid. Give back to the latch, or an HA bar against the trade, sells.
        Before the latch: HA close through EMA20, or a hard bid target if trend_tp_pct is set.
        A clock runs only when trend_time_exit_min is above 0. The QQQ stop already ran."""
        latch = float(p.get("trend_latch_pct") if p.get("trend_latch_pct") is not None else 0.20)
        buf = float(p.get("trend_ema_buf") if p.get("trend_ema_buf") is not None else 0.0)
        hard = float(p.get("tp_pct") or 0.0)
        clock = float(p.get("time_exit_min") or 0.0)
        q = self.b.quotes(p["expiry"], {p["symbol"]: (p["side"], p["strike"])}).get(p["symbol"])
        bid = q.bid if q and q.bid else None
        g = None
        if bid is not None and p.get("fill"):
            g = (bid - p["fill"]) / p["fill"]
            p["peak_gain"] = max(p.get("peak_gain", 0.0), g)
        if hard > 0 and g is not None and g >= hard - 1e-9 and held >= self.tp_min_hold_s():
            self.log("exit_signal", why=f"+{hard:.0%} TP on bid", bid=bid, gain=round(g, 3),
                     held_s=round(held, 1), **self._regime_fields())
            self.sell(f"+{hard:.0%} TP on bid (gain {g:.0%}, held {held:.0f}s)")
            return True
        armed = bool(p.get("latch_armed"))
        if armed and g is not None and g <= latch + 1e-9:
            self.log("exit_signal", why="trend_latch_giveback", bid=bid, gain=round(g, 3),
                     latch_pct=latch, held_s=round(held, 1), **self._regime_fields())
            self.sell(f"trend latch giveback (gain {g:.0%} back to {latch:.0%})")
            return True
        if armed and rec is not None:
            why = self.trend_momentum_against(rec, p["side"])
            if why:
                self.log("exit_signal", why="trend_momentum", detail=why, bid=bid,
                         gain=None if g is None else round(g, 3), held_s=round(held, 1),
                         **self._regime_fields())
                self.sell(f"trend momentum: {why}")
                return True
        if (not armed) and g is not None and g >= latch - 1e-9:
            p["latch_armed"] = True
            self.log("trend_latch_armed", bid=bid, gain=round(g, 3), latch_pct=latch,
                     held_s=round(held, 1), **self._regime_fields())
            self.save()
            if rec is not None:
                why = self.trend_momentum_against(rec, p["side"])
                if why:
                    self.log("exit_signal", why="trend_momentum", detail=why, bid=bid,
                             gain=round(g, 3), held_s=round(held, 1), **self._regime_fields())
                    self.sell(f"trend momentum: {why}")
                    return True
            return False
        if (not p.get("latch_armed")) and rec is not None:
            why = self.trend_structure_exit(rec, p["side"], buf)
            if why:
                self.log("exit_signal", why="trend_ema", detail=why, bid=bid,
                         gain=None if g is None else round(g, 3), held_s=round(held, 1),
                         **self._regime_fields())
                self.sell(f"trend EMA: {why}")
                return True
        if clock > 0 and held >= clock * 60:
            self.log("exit_signal", why="time_exit", bid=bid, held_s=round(held, 1), **self._regime_fields())
            self.sell(f"time exit {held / 60:.1f}m")
            return True
        return False

    def apply_override(self, rec: dict) -> dict:
        """Xavier 2026-10-13: extra buy(s) via state["override"] (max_buys, side_only=CALL,
        entry_mode=ema_bounce). Active only once the normal buy is used. Bounce = low dipped to
        within touch of EMA20 (this bar or prior bar) while close held above VWAP, then a green HA
        close back above EMA20."""
        ov = self.state.get("override") or {}
        if ov.get("entry_mode") != "ema_bounce" or self.state["buys"] < 1:
            return rec
        low, ema, vwap = (fnum(rec.get(k)) for k in ("low", "ema20", "vwap"))
        hc, ho = fnum(rec.get("ha_close")), fnum(rec.get("ha_open"))
        if None in (low, ema, vwap, hc, ho):
            return {**rec, "signal": "NONE"}
        tol = float(ov.get("touch", 0.15))
        touch_now = low <= ema + tol
        touch_prev = self.state.get("bounce_touch_prev", False)
        self.state["bounce_touch_prev"] = touch_now
        close = fnum(rec.get("close"))
        ok = (touch_now or touch_prev) and hc > ho and hc > ema and close > ema and close > vwap and low > vwap - tol
        sig = "CALL" if ok else "NONE"
        self.log("bounce_check", bar=rec.get("t"), touch_now=touch_now, touch_prev=touch_prev,
                 low=low, ema20=round(ema, 3), vwap=round(vwap, 3), ha_green=hc > ho, signal=sig)
        return {**rec, "signal": sig, "reason": "ema20_bounce" if ok else "no_bounce"}

    def on_tick(self, now: Optional[datetime] = None):
        now = now or self.clock()
        self.roll_day(now)
        pb = self.state.get("pending_buy")
        if pb and self.live and not self.state.get("position"):
            st = self.b.order_status(pb["cid"])
            self.log("pending_buy_check", cid=pb["cid"], status=st)
            if st["status"] == "FILLED":
                self.state["pending_buy"] = None
                c = {"symbol": occ("QQQ", pb["expiry"], pb["side"], pb["strike"]), "strike": pb["strike"]}
                self._open_position(pb["side"], c, pb["expiry"], st.get("filled_price") or pb["limit"], pb["cid"], None, False)
            elif st["status"] in ("CANCELLED", "FAILED"):
                self.state["pending_buy"] = None
                self.save()
            else:
                self.cancel_and_confirm(pb["cid"])
        if self.state.get("position") or self.state.get("pending_buy"):
            if now.time() >= self.cfg["flatten_at"]:
                self.flatten("14:45 CT flatten")
            elif self.kill() == "FLATTEN":
                self.flatten("kill switch FLATTEN")
            else:
                self.check_stop()
                self.check_giveback()


# --------------------------------------------------------------------------- runners
def read_latest(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def run_live_loop(tr: Trader, latest: Path, stop_check_s: float = 3.0, until: Optional[dtime] = None):
    tr.log("start", live=tr.live, latest=str(latest), state=tr.state)
    last_t, last_check = None, 0.0
    until = until or dtime(15, 0)
    while True:
        now = tr.clock()
        if now.time() >= until and not (tr.state.get("position") or tr.state.get("pending_buy")):
            tr.log("exit_loop", reason=f"past {until}"); return
        rec = read_latest(latest)
        try:
            if rec and rec.get("t") != last_t:
                last_t = rec.get("t")
                tr.on_bar(rec)
                last_check = time.monotonic()
            elif time.monotonic() - last_check >= stop_check_s:
                tr.on_tick()
                last_check = time.monotonic()
        except Exception as e:  # noqa: BLE001  never die silently with a position on
            tr.log("ERROR", err=repr(e)[:500])
        time.sleep(0.25)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="default: preview only, never place orders")
    g.add_argument("--live", action="store_true", help="REAL orders on account 5JT43423")
    ap.add_argument("--allow-delayed-quotes", action="store_true",
                    help="live only: allow entries priced off the delayed nasdaq.com chain when Webull option quotes are unavailable")
    ap.add_argument("--no-nasdaq", action="store_true", help="disable the delayed nasdaq.com quote fallback")
    ap.add_argument("--latest", default=str(LATEST))
    ap.add_argument("--state", default=None)
    ap.add_argument("--log", default=None)
    ap.add_argument("--once", action="store_true", help="process the current latest.json once and exit")
    ap.add_argument("--force-time", default=None,
                    help='dry-run only: pretend now is "YYYY-MM-DD HH:MM" CT (or "HH:MM" today) so previews can be tested after hours')
    a = ap.parse_args(argv)
    live = bool(a.live)
    mode = "LIVE" if live else "DRYRUN"
    state = Path(a.state) if a.state else HERE / ("trader_state.json" if live else "trader_state.dryrun.json")
    logp = Path(a.log) if a.log else HERE / ("trader.log" if live else "trader.dryrun.log")
    log = Logger(logp, mode)
    clock = now_ct
    if a.force_time:
        if live:
            sys.exit("--force-time is dry-run only")
        base = now_ct()
        if " " in a.force_time:
            target = datetime.strptime(a.force_time, "%Y-%m-%d %H:%M").replace(tzinfo=CT, second=1)
        else:
            hh, mm = map(int, a.force_time.split(":"))
            target = base.replace(hour=hh, minute=mm, second=1, microsecond=0)
        off = target - base
        clock = lambda: now_ct() + off  # noqa: E731
    broker = WebullBroker(live=live, log=log, use_nasdaq=not a.no_nasdaq)
    tr = Trader(broker, log, live=live, state_path=state, allow_delayed_quotes=a.allow_delayed_quotes, clock=clock, signals_log=SIGNALS_LOG)
    if a.once:
        rec = read_latest(Path(a.latest))
        if a.force_time and rec:
            n = clock()
            rec = {**rec, "t": (n.replace(second=0, microsecond=0) - timedelta(minutes=1)).isoformat()}
        tr.state["last_bar_t"] = None
        tr.on_bar(rec, clock()) if rec else log("no_latest")
        return
    run_live_loop(tr, Path(a.latest))


if __name__ == "__main__":
    main()
