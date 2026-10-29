#!/usr/bin/env python3
"""Research only: QQQ 0DTE MACD-only entries vs the paper regime book.

Does not import or modify the paper/live trader. The day label, VWAP fade,
and EMA20 retest below are a transcription of the paper rules in trader.py
(regime_mode, as of the 2026-10-29 dry-run state) so both books can be
scored on the same bars.

A follow-up grid (kind "macd_rsi") scores MACD signal-line crosses plus RSI
only: RSI>50/<50 as a confirm, and an RSI 30/70 reclaim confirmed by a MACD
cross within 3 or 5 bars. No EMA, VWAP, Heikin Ashi, or day label on those
entries. The 24 names and the 8-name decision list (RSI_REFERENCE) are fixed
in this file.

A second follow-up (kind "curve") enters on a signal-line cross after the
MACD line hooks, and exits when the line curls the other way. No fixed
target and no time stop. CURVE_REFERENCE is the four slope cells on
regular closes. Histogram-shrink and Heikin Ashi rows are the checks.

A third follow-up (kind "quick") enters on the slope turn itself and exits
on a small option target, an optional favorable HA bar, a 2- or 3-minute
clock, and a $0.30 stop. QUICK_REFERENCE is the eight morning slope cells.

A fourth follow-up (kind "bband") requires a Bollinger touch within N bars
of a MACD slope turn or signal-line cross. BB_REFERENCE is the four morning
12/26/9 cells.

Run from the repo root:

    python3 research/macd_only_backtest.py

Data files (all local, no network on a normal run):

    testdata/qqq_1m_yahoo_prepost.csv     Yahoo Finance 1m, pre+post, 2026-09-30 .. 2026-10-29
    testdata/qqq_bars_20261026_29.json    Webull-style bars used by the paper feed, Oct 26-29
    testdata/qqq_1m_20261022.csv          same feed, Oct 21-22

Prices come from Yahoo (the Oct 29 11:58 EMA20 matches the paper state).
Where the attached feed has a bar, its volume replaces Yahoo's volume,
because Yahoo 1m volume has occasional prints in the tens of millions that
wreck session VWAP. Leftover Yahoo RTH volume is winsorized (see
clean_yahoo_volume). Session VWAP is hlc3 * volume from 08:30 CT, same as
bar_signal.SessionVWAP when the provider does not send a per-bar VWAP.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
ROOT = Path(__file__).resolve().parents[1]
TESTDATA = ROOT / "testdata"
OUT_JSON = ROOT / "research" / "macd_backtest_results.json"

# Option proxy. Premium is the middle of the paper band ($0.30-$0.60).
# Delta is the rough effective delta on the 2026-10-29 paper stop-outs
# (about 0.18-0.24 per $1 of QQQ). Fees are $0.65 per contract per side.
PREMIUM = 0.50
DELTA = 0.22
FEE_RT = 0.65 * 2
MAX_BUYS = 12
ENTRY_LO = dtime(8, 30)
ENTRY_HI = dtime(12, 0)
FOCUS_LO = "2026-10-26"
FOCUS_HI = "2026-10-29"

# Paper state checks from trader_state.dryrun.json at the 11:58 CT bar.
CHECK_T = "2026-10-29T11:58:00-05:00"
CHECK_EMA = 715.3596048088497
CHECK_VWAP = 715.0085698565689
CHECK_MACD_HIST = 0.09777566589911282


# --------------------------------------------------------------------------- indicators (same seeding as bar_signal.py)
class EMA:
    def __init__(self, period: int):
        self.period = period
        self.k = 2.0 / (period + 1)
        self.value = None
        self._n = 0
        self._sum = 0.0

    def update(self, x: float):
        if self.value is None:
            self._n += 1
            self._sum += x
            if self._n == self.period:
                self.value = self._sum / self.period
        else:
            self.value = x * self.k + self.value * (1 - self.k)
        return self.value


class RSI:
    def __init__(self, period: int = 14):
        self.period = period
        self.prev = None
        self.avg_gain = None
        self.avg_loss = None
        self._gains = []
        self._losses = []
        self.value = None

    def update(self, close: float):
        if self.prev is None:
            self.prev = close
            return None
        ch = close - self.prev
        self.prev = close
        gain, loss = max(ch, 0.0), max(-ch, 0.0)
        n = self.period
        if self.avg_gain is None:
            self._gains.append(gain)
            self._losses.append(loss)
            if len(self._gains) == n:
                self.avg_gain = sum(self._gains) / n
                self.avg_loss = sum(self._losses) / n
            else:
                return None
        else:
            self.avg_gain = (self.avg_gain * (n - 1) + gain) / n
            self.avg_loss = (self.avg_loss * (n - 1) + loss) / n
        if self.avg_loss == 0:
            self.value = 100.0 if self.avg_gain > 0 else 50.0
        else:
            rs = self.avg_gain / self.avg_loss
            self.value = 100.0 - 100.0 / (1.0 + rs)
        return self.value


class MACD:
    def __init__(self, fast=12, slow=26, signal=9):
        self.f, self.s, self.sig = EMA(fast), EMA(slow), EMA(signal)
        self.line = None
        self.signal = None
        self.hist = None

    def update(self, close: float):
        f, s = self.f.update(close), self.s.update(close)
        if f is None or s is None:
            return None
        self.line = f - s
        self.signal = self.sig.update(self.line)
        self.hist = None if self.signal is None else self.line - self.signal
        return self.hist


@dataclass
class Bar:
    t: datetime  # minute open, CT
    o: float
    h: float
    l: float
    c: float
    v: float
    vol_source: str  # yahoo | feed


def parse_ts(s: str) -> datetime:
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=CT)
    return t.astimezone(CT).replace(second=0, microsecond=0)


def rth(t: datetime) -> bool:
    return t.weekday() < 5 and dtime(8, 30) <= t.time() < dtime(15, 0)


def in_entry_window(t: datetime) -> bool:
    return t.weekday() < 5 and ENTRY_LO <= t.time() <= ENTRY_HI


def load_yahoo() -> dict[datetime, Bar]:
    path = TESTDATA / "qqq_1m_yahoo_prepost.csv"
    out = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            t = parse_ts(row["time"])
            out[t] = Bar(t, float(row["open"]), float(row["high"]), float(row["low"]),
                         float(row["close"]), float(row["volume"]), "yahoo")
    return out


def overlay_feed_volume(bars: dict[datetime, Bar]) -> int:
    """Replace Yahoo volume with the attached feed's volume when we have it."""
    n = 0
    raw = json.loads((TESTDATA / "qqq_bars_20261026_29.json").read_text())
    for t, _o, _h, _l, _c, v in raw:
        bt = parse_ts(t)
        if bt in bars:
            bars[bt].v = float(v)
            bars[bt].vol_source = "feed"
            n += 1
    with (TESTDATA / "qqq_1m_20261022.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            bt = parse_ts(row["time"])
            # Premarket prints in this file are real volume. Yahoo's premarket
            # volume is 0, so the overlay has to cover extended hours too.
            if bt in bars:
                bars[bt].v = float(row["volume"])
                bars[bt].vol_source = "feed"
                n += 1
    return n


def clean_yahoo_volume(ordered: list[Bar]) -> None:
    """Cap Yahoo-only RTH volume so a few bad prints don't dominate VWAP.

    Chosen against the attached feed's own VWAP on Oct 27-29, before any
    strategy result was looked at: the 08:30 bar is capped at 5x the session
    median, and any other bar above 8x the median is replaced with the median.
    Feed volume is left alone. Median prefers feed prints when a session has
    at least 30 of them.
    """
    by_day = defaultdict(list)
    for b in ordered:
        if rth(b.t):
            by_day[b.t.date()].append(b)
    for group in by_day.values():
        trusted = [b.v for b in group if b.vol_source == "feed" and b.v > 0]
        pool = trusted if len(trusted) >= 30 else [b.v for b in group if 0 < b.v < 1_000_000]
        if not pool:
            pool = [b.v for b in group if b.v > 0]
        if not pool:
            continue
        med = statistics.median(pool)
        for b in group:
            if b.vol_source == "feed":
                continue
            if b.t.time() == dtime(8, 30):
                b.v = min(b.v, 5 * med)
            elif b.v > 8 * med:
                b.v = med


def assert_extended_hours(ordered: list[Bar]) -> dict:
    """EMA, MACD, RSI, Heikin Ashi, and Bollinger walk this full list.

    A session with no premarket would mean those indicators were regular-hours
    only. Fail loud rather than publish that by accident.
    """
    pre = defaultdict(int)
    post = defaultdict(int)
    for b in ordered:
        if b.t.weekday() >= 5:
            continue
        if dtime(3, 0) <= b.t.time() < dtime(8, 30):
            pre[b.t.date()] += 1
        elif b.t.time() >= dtime(15, 0):
            post[b.t.date()] += 1
    if not pre or min(pre.values()) < 100:
        raise SystemExit(f"extended-hours tape is missing premarket bars: {dict(pre)}")
    thin = [d.isoformat() for d, n in sorted(post.items()) if n < 30]
    return {
        "sessions_with_premarket": len(pre),
        "premarket_bars_min": min(pre.values()),
        "premarket_bars_max": max(pre.values()),
        "thin_postmarket_days": thin,
    }


def load_bars() -> list[Bar]:
    bars = load_yahoo()
    overlay_feed_volume(bars)
    ordered = [bars[k] for k in sorted(bars)]
    clean_yahoo_volume(ordered)
    return ordered


# --------------------------------------------------------------------------- paper day label (trader.classify_day_regime)
def classify_day_regime(hist, or_hi, or_lo, when: dtime) -> dict:
    blank = {"label": "WARMUP", "direction": 0, "crosses": None, "slope15": None, "side_frac": None}
    if when < dtime(9, 0) or len(hist) < 21:
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


def count_crosses(rows) -> int:
    crosses, last = 0, 0
    for close, ema in rows:
        sg = 1 if close > ema else (-1 if close < ema else 0)
        if sg == 0:
            continue
        if last and sg != last:
            crosses += 1
        last = sg
    return crosses


def vwap_fade_side(color, high, low, close, vwap):
    if None in (high, low, close, vwap) or color not in ("green", "red"):
        return None
    if color == "green" and low <= vwap - 0.25 and close > vwap:
        return "CALL"
    if color == "red" and high >= vwap + 0.25 and close < vwap:
        return "PUT"
    return None


def fade_stop_dist(side, entry, high, low):
    if side == "CALL":
        dist = entry - (low - 0.05)
    else:
        dist = (high + 0.05) - entry
    if dist != dist:
        return None
    return min(1.0, max(0.15, dist))


def pr8_block(side: str, regime: list, when: dtime):
    """Paper retest_trend_only gate. None means the retest is allowed."""
    if len(regime) < 6:
        return "retest_warmup"
    crosses = count_crosses(regime[-20:])
    if crosses >= 4:
        return f"regime_CHOPPY(crosses={crosses})"
    slope5 = regime[-1][1] - regime[-6][1]
    if side == "PUT" and not (slope5 < 0):
        return f"bias_not_BEAR(slope5={slope5:.4f})"
    if side == "CALL" and not (slope5 > 0):
        return f"bias_not_BULL(slope5={slope5:.4f})"
    if not (ENTRY_LO <= when <= ENTRY_HI):
        return "outside_window"
    return None


def trend_filters(side, close, ema, ema_h, ema_l, vwap, rsi):
    if None in (close, ema, vwap, rsi):
        return "missing_indicator"
    if side == "CALL" and rsi > 70:
        return f"call_rsi {rsi:.1f}"
    if side == "PUT" and rsi < 30:
        return f"put_rsi {rsi:.1f}"
    band = ema_h if side == "CALL" else ema_l
    ref = band if band is not None else ema
    if abs(close - ref) > 0.80 + 1e-9:
        return f"ema_dist {abs(close - ref):.2f}"
    if abs(close - vwap) > 6.0 + 1e-9:
        return f"vwap_dist {abs(close - vwap):.2f}"
    return None


TOUCH = 0.15


def retest_side(color, close, vwap, ema, ema_l, ema_h, ha_c, prior_colors):
    """retest_near_only path: HA close within $0.15 of EMA20 / the near band."""
    if None in (close, vwap, ema, ema_l, ema_h, ha_c) or len(prior_colors) < 3:
        return None
    near_put = min(abs(ha_c - ema), abs(ha_c - ema_l)) <= TOUCH
    near_call = min(abs(ha_c - ema), abs(ha_c - ema_h)) <= TOUCH
    if close < vwap and color == "red" and "green" in prior_colors and close < ema and near_put:
        return "PUT"
    if close > vwap and color == "green" and "red" in prior_colors and close > ema and near_call:
        return "CALL"
    return None


# --------------------------------------------------------------------------- annotate every bar once
MACD_SPECS = ((12, 26, 9), (6, 13, 5))


def prepare(ordered: list[Bar]) -> list[dict]:
    ha_o = ha_c = None
    ema, ema_h, ema_l = EMA(20), EMA(20), EMA(20)
    rsi = RSI(14)
    rsi_fast = RSI(7)
    prev_rsi14 = None
    prev_rsi7 = None
    macds = {}
    for fast, slow, sig in MACD_SPECS:
        macds[("close", fast, slow, sig)] = MACD(fast, slow, sig)
        macds[("ha", fast, slow, sig)] = MACD(fast, slow, sig)
    prev_macd = {k: {"hist": None, "hist2": None, "line": None} for k in macds}

    day = None
    pv = vv = 0.0
    vwap = None
    or_hi = or_lo = None
    regime: list = []
    day_hist: list = []
    retest: list = []
    out = []

    for b in ordered:
        d = b.t.date()
        if d != day:
            day = d
            pv = vv = 0.0
            vwap = None
            or_hi = or_lo = None
            regime = []
            day_hist = []
            retest = []

        # Every bar, including premarket and postmarket. EMA20, MACD, RSI, and
        # Heikin Ashi are the extended-hours series. Session VWAP is not:
        # it starts at 08:30. Bollinger, built later, uses this same full list.
        new_c = (b.o + b.h + b.l + b.c) / 4.0
        new_o = (b.o + b.c) / 2.0 if ha_o is None else (ha_o + ha_c) / 2.0
        ha_o, ha_c = new_o, new_c
        if ha_c > ha_o:
            color = "green"
        elif ha_c < ha_o:
            color = "red"
        else:
            color = "doji"

        ema_v = ema.update(b.c)
        eh = ema_h.update(b.h)
        el = ema_l.update(b.l)
        rsi_v = rsi.update(b.c)
        rsi7_v = rsi_fast.update(b.c)

        macd_now = {}
        for key, ind in macds.items():
            series, fast, slow, sig = key
            px = ha_c if series == "ha" else b.c
            ind.update(px)
            prev = prev_macd[key]
            macd_now[key] = {
                "line": ind.line,
                "hist": ind.hist,
                "prev_hist": prev["hist"],
                "prev2_hist": prev["hist2"],
                "prev_line": prev["line"],
            }
            prev_macd[key] = {"hist": ind.hist, "hist2": prev["hist"], "line": ind.line}

        is_rth = rth(b.t)
        if is_rth and b.v > 0:
            typical = (b.h + b.l + b.c) / 3.0
            pv += typical * b.v
            vv += b.v
            vwap = pv / vv
        if is_rth and b.t.time() < dtime(8, 45):
            or_hi = b.h if or_hi is None else max(or_hi, b.h)
            or_lo = b.l if or_lo is None else min(or_lo, b.l)

        label = {"label": "WARMUP", "direction": 0, "crosses": None, "slope15": None}
        base_side = None
        base_source = None
        if is_rth and ema_v is not None and vwap is not None:
            regime.append((b.c, ema_v))
            day_hist.append((b.c, ema_v, vwap))
            label = classify_day_regime(day_hist, or_hi, or_lo, b.t.time())
            prior = [row[0] for row in retest[-3:]]
            if label["label"] == "CHOP":
                side = vwap_fade_side(color, b.h, b.l, b.c, vwap)
                if side:
                    base_side, base_source = side, "vwap_fade"
            elif label["label"] == "TREND":
                side = retest_side(color, b.c, vwap, ema_v, el, eh, ha_c, prior)
                if side:
                    blk = pr8_block(side, regime, b.t.time())
                    if blk is None:
                        blk = trend_filters(side, b.c, ema_v, eh, el, vwap, rsi_v)
                    if blk is None:
                        base_side, base_source = side, "retest_trend"
            # retest history is recorded after the entry decision, matching on_bar.
            pt = eh is not None and el is not None and b.h >= min(ema_v, el) - TOUCH
            ctch = eh is not None and el is not None and b.l <= max(ema_v, eh) + TOUCH
            retest.append((color, ema_v, bool(pt), bool(ctch), b.c, b.l, b.h))
            del retest[:-12]

        out.append({
            "t": b.t,
            "o": b.o, "h": b.h, "l": b.l, "c": b.c, "v": b.v,
            "ha_o": ha_o, "ha_c": ha_c, "color": color,
            "ema": ema_v, "ema_h": eh, "ema_l": el, "rsi": rsi_v, "vwap": vwap,
            "rsi14": rsi_v, "rsi14_prev": prev_rsi14,
            "rsi7": rsi7_v, "rsi7_prev": prev_rsi7,
            "label": label["label"],
            "day_dir": label.get("direction"),
            "base_side": base_side,
            "base_source": base_source,
            "macd": macd_now,
            "rth": is_rth,
        })
        prev_rsi14 = rsi_v
        prev_rsi7 = rsi7_v
    return out


def find_bar(recs, iso_local: str):
    target = datetime.fromisoformat(iso_local)
    for rec in recs:
        if rec["t"] == target:
            return rec
    return None


def indicator_checks(recs) -> dict:
    rec = find_bar(recs, CHECK_T)
    if rec is None:
        raise SystemExit(f"missing check bar {CHECK_T}")
    st = rec["macd"][("close", 12, 26, 9)]
    checks = {
        "t": CHECK_T,
        "close": rec["c"],
        "ema": rec["ema"],
        "ema_err": None if rec["ema"] is None else rec["ema"] - CHECK_EMA,
        "vwap": rec["vwap"],
        "vwap_err": None if rec["vwap"] is None else rec["vwap"] - CHECK_VWAP,
        "macd_hist": st["hist"],
        "macd_hist_err": None if st["hist"] is None else st["hist"] - CHECK_MACD_HIST,
        "label": rec["label"],
    }
    if checks["ema_err"] is None or abs(checks["ema_err"]) > 0.02:
        raise SystemExit(f"EMA check failed: {checks}")
    if checks["vwap_err"] is None or abs(checks["vwap_err"]) > 0.05:
        raise SystemExit(f"VWAP check failed: {checks}")
    if checks["macd_hist_err"] is None or abs(checks["macd_hist_err"]) > 0.02:
        raise SystemExit(f"MACD check failed: {checks}")
    return checks


# --------------------------------------------------------------------------- exits and simulation
def tp_points(tp_pct: float, delta: float, premium: float = PREMIUM) -> float:
    return (tp_pct * premium) / delta


def opt_dollars(points: float, delta: float) -> tuple[float, float]:
    gross = points * delta * 100.0
    return gross, gross - FEE_RT


def open_position(rec, side: str, style: str, delta: float):
    entry = rec["c"]
    if style == "chop":
        dist = fade_stop_dist(side, entry, rec["h"], rec["l"])
        if dist is None:
            return None
        level = round(entry - dist if side == "CALL" else entry + dist, 2)
        dist = abs(entry - level)
        tp = tp_points(0.25, delta)
        mins = 10
    elif style == "trend":
        dist = 0.30
        level = round(entry - dist if side == "CALL" else entry + dist, 2)
        dist = abs(entry - level)
        tp = tp_points(0.12, delta)
        mins = 5
    else:
        raise ValueError(style)
    return {
        "side": side,
        "style": style,
        "entry": entry,
        "entry_t": rec["t"],
        "stop_dist": dist,
        "stop_level": level,
        "tp_dist": tp,
        "tp_level": entry + tp if side == "CALL" else entry - tp,
        "deadline": rec["t"] + timedelta(minutes=mins),
        "label": rec["label"],
        "source": rec.get("_source"),
    }


def resolve_bar(pos, rec, path: str):
    side = pos["side"]
    stop_hit = rec["l"] <= pos["stop_level"] if side == "CALL" else rec["h"] >= pos["stop_level"]
    tp_hit = rec["h"] >= pos["tp_level"] if side == "CALL" else rec["l"] <= pos["tp_level"]
    if stop_hit or tp_hit:
        if stop_hit and tp_hit:
            if path == "stop_first":
                take_stop = True
            else:
                take_stop = abs(rec["o"] - pos["stop_level"]) <= abs(rec["o"] - pos["tp_level"])
        else:
            take_stop = stop_hit
        if take_stop:
            return "stop", -pos["stop_dist"]
        return "tp", pos["tp_dist"]
    if rec["t"] >= pos["deadline"]:
        direction = 1 if side == "CALL" else -1
        return "time", (rec["c"] - pos["entry"]) * direction
    return None


def macd_trigger(state, trigger: str):
    hist, prev, prev2 = state["hist"], state["prev_hist"], state["prev2_hist"]
    line, prev_line = state["line"], state["prev_line"]
    if trigger == "signal_cross":
        if prev is None or hist is None:
            return None
        if prev <= 0 < hist:
            return "CALL"
        if prev >= 0 > hist:
            return "PUT"
    elif trigger == "zero_cross":
        if prev_line is None or line is None:
            return None
        if prev_line <= 0 < line:
            return "CALL"
        if prev_line >= 0 > line:
            return "PUT"
    elif trigger == "hist_hook":
        if None in (hist, prev, prev2):
            return None
        # Trough below zero -> CALL. Peak above zero -> PUT.
        # `hist > prev <= prev2` is (hist > prev) and (prev <= prev2).
        if hist > prev <= prev2 and prev < 0:
            return "CALL"
        if hist < prev >= prev2 and prev > 0:
            return "PUT"
    else:
        raise ValueError(trigger)
    return None


def trend_ok(rec, side: str, use_filter: bool) -> bool:
    if not use_filter:
        return True
    ema = rec["ema"]
    if ema is None:
        return False
    if side == "CALL":
        return rec["c"] > ema
    return rec["c"] < ema


def fresh_mrsi_memory() -> dict:
    """Last bar index of each MACD signal-line cross and each RSI 30/70 reclaim."""
    mem = {
        "macd": {(fast, slow, sig): {"CALL": None, "PUT": None} for fast, slow, sig in MACD_SPECS},
        "rsi": {period: {"CALL": None, "PUT": None} for period in (7, 14)},
    }
    return mem


def update_mrsi_memory(i: int, rec, mem) -> None:
    """Record events on the whole tape, including while a position is open."""
    for fast, slow, sig in MACD_SPECS:
        state = rec["macd"][("close", fast, slow, sig)]
        side = macd_trigger(state, "signal_cross")
        if side:
            mem["macd"][(fast, slow, sig)][side] = i
    for period in (7, 14):
        prev, cur = rec[f"rsi{period}_prev"], rec[f"rsi{period}"]
        if prev is None or cur is None:
            continue
        # Reclaim: was at or through the band, now back inside.
        if prev <= 30.0 < cur:
            mem["rsi"][period]["CALL"] = i
        if prev >= 70.0 > cur:
            mem["rsi"][period]["PUT"] = i


def mrsi_side(i: int, rec, spec, mem):
    """MACD + RSI on regular closes. No EMA, VWAP, Heikin Ashi, or day label.

    confirm: enter on the MACD signal-line cross if RSI is already >50 (call)
    or <50 (put).

    reversal: RSI crosses back above 30 (call) or back below 70 (put), and a
    same-side MACD signal-line cross lands on that bar or within the previous
    N tape bars. If the MACD cross comes second, enter on the MACD bar instead.
    One entry, on the later event. N counts bars on this tape, so a cross a
    few minutes before 08:30 can confirm the open.
    """
    key = (spec["fast"], spec["slow"], spec["sig"])
    period = spec["rsi_n"]
    state = rec["macd"][("close", *key)]
    macd_side = macd_trigger(state, "signal_cross")
    prev, cur = rec[f"rsi{period}_prev"], rec[f"rsi{period}"]
    if spec["mode"] == "confirm":
        if macd_side is None or cur is None:
            return None
        if macd_side == "CALL" and cur > 50.0:
            return "CALL"
        if macd_side == "PUT" and cur < 50.0:
            return "PUT"
        return None
    rsi_side = None
    if prev is not None and cur is not None:
        if prev <= 30.0 < cur:
            rsi_side = "CALL"
        elif prev >= 70.0 > cur:
            rsi_side = "PUT"
    n = spec["n"]
    if macd_side and rsi_side:
        return macd_side if macd_side == rsi_side else None
    if rsi_side:
        last = mem["macd"][key][rsi_side]
        if last is not None and last < i and i - last <= n:
            return rsi_side
        return None
    if macd_side:
        last = mem["rsi"][period][macd_side]
        if last is not None and last < i and i - last <= n:
            return macd_side
    return None


def desired_side(rec, spec) -> tuple[str | None, str | None]:
    """Return (side, exit style) or (None, None)."""
    kind = spec["kind"]
    if kind == "baseline":
        if rec["base_side"]:
            style = "chop" if rec["base_source"] == "vwap_fade" else "trend"
            return rec["base_side"], style
        return None, None
    key = (spec["series"], spec["fast"], spec["slow"], spec["sig"])
    state = rec["macd"][key]
    if kind == "filter":
        if not rec["base_side"] or state["hist"] is None:
            return None, None
        agree = (rec["base_side"] == "CALL" and state["hist"] > 0) or (
            rec["base_side"] == "PUT" and state["hist"] < 0)
        if not agree:
            return None, None
        style = "chop" if rec["base_source"] == "vwap_fade" else "trend"
        return rec["base_side"], style
    side = macd_trigger(state, spec["trigger"])
    if side is None or not trend_ok(rec, side, spec["trend_filter"]):
        return None, None
    if kind == "macd":
        return side, spec["exit"]
    if kind == "gated":
        if rec["label"] == "CHOP":
            return side, "chop"
        if rec["label"] == "TREND":
            return side, "trend"
        return None, None
    raise ValueError(kind)


def simulate(recs, spec, delta: float, path: str) -> list[dict]:
    trades = []
    pos = None
    next_ok = None
    buys = 0
    day = None
    last_pre_noon = None
    mem = fresh_mrsi_memory()
    for i, rec in enumerate(recs):
        d = rec["t"].date()
        if d != day:
            if pos is not None:
                # Should not happen: time stops are 5-10 minutes and RTH continues.
                direction = 1 if pos["side"] == "CALL" else -1
                pts = (rec["c"] - pos["entry"]) * direction
                trades.append(finish(pos, rec, "day_roll", pts, delta))
                pos = None
            day = d
            buys = 0
            next_ok = None
        if spec["kind"] == "macd_rsi":
            # Events during a hold still count as confirmation for the next entry.
            update_mrsi_memory(i, rec, mem)
        if pos is not None and spec.get("window") == "am1130" and rec["t"].time() >= dtime(12, 0) and rec["t"].date() == pos["entry_t"].date():
            if last_pre_noon is not None and last_pre_noon["t"] >= pos["entry_t"]:
                direction = 1 if pos["side"] == "CALL" else -1
                trades.append(finish(pos, last_pre_noon, "noon", (last_pre_noon["c"] - pos["entry"]) * direction, delta))
                pos = None
                next_ok = rec["t"] + timedelta(minutes=2)
            continue
        if rec["rth"] and rec["t"].time() < dtime(12, 0):
            last_pre_noon = rec
        if pos is not None:
            hit = resolve_bar(pos, rec, path)
            if hit:
                trades.append(finish(pos, rec, hit[0], hit[1], delta))
                pos = None
                next_ok = rec["t"] + timedelta(minutes=2)
            continue
        if spec.get("window") == "am1130":
            if not allows_quick_entry(rec["t"], "am1130"):
                continue
        elif not in_entry_window(rec["t"]):
            continue
        if next_ok is not None and rec["t"] < next_ok:
            continue
        if buys >= MAX_BUYS:
            continue
        if spec["kind"] == "macd_rsi":
            side = mrsi_side(i, rec, spec, mem)
            style = spec["exit"] if side else None
        else:
            side, style = desired_side(rec, spec)
        if side is None:
            continue
        if spec["kind"] == "macd_rsi":
            rec["_source"] = spec["mode"]
        elif spec["kind"] in ("baseline", "filter"):
            rec["_source"] = rec["base_source"]
        else:
            rec["_source"] = spec["trigger"]
        opened = open_position(rec, side, style, delta)
        if opened is None:
            continue
        pos = opened
        buys += 1
    return trades


def curve_turns(lines, hists, mode: str) -> tuple[bool, bool]:
    """Bullish turn, bearish turn. The cross is separate.

    slope: the MACD line's own slope flips. That is the hook in Xavier's words.
    hist1: the histogram changes direction for one bar (white bar above zero,
    pink bar below zero on his photo).
    hist2: the histogram has shrunk for two bars in a row, starting from a turn.
    """
    if mode == "slope":
        if len(lines) < 3 or None in lines[-3:]:
            return False, False
        d0 = lines[-2] - lines[-3]
        d1 = lines[-1] - lines[-2]
        return d1 > 0 and d0 <= 0, d1 < 0 and d0 >= 0
    if mode == "hist1":
        if len(hists) < 3 or None in hists[-3:]:
            return False, False
        turn_up = hists[-1] > hists[-2] and hists[-2] <= hists[-3]
        turn_down = hists[-1] < hists[-2] and hists[-2] >= hists[-3]
        return turn_up, turn_down
    if mode == "hist2":
        if len(hists) < 4 or None in hists[-4:]:
            return False, False
        turn_up = hists[-1] > hists[-2] > hists[-3] and hists[-3] <= hists[-4]
        turn_down = hists[-1] < hists[-2] < hists[-3] and hists[-3] >= hists[-4]
        return turn_up, turn_down
    raise ValueError(mode)


def simulate_curve(recs, spec, delta: float) -> list[dict]:
    """Entry is a signal-line cross after a MACD turn. Exit is the turn back.

    No fixed target and no time stop. A disaster stop, if set, is $0.50 of QQQ
    and is filled when that bar's high/low trades through it, ahead of the
    close-based curve exit. Anything still open on the last regular-session
    bar of the day is marked there. One position. No 12-trade cap: this rule
    is not the paper override. No same-bar reversal.
    """
    key = (spec["series"], spec["fast"], spec["slow"], spec["sig"])
    mode = spec["curve"]
    stop = spec["disaster"]
    lines: list[float] = []
    hists: list[float] = []
    armed = {"CALL": False, "PUT": False}
    trades = []
    pos = None
    last_rth = None

    def shut(bar, reason, points):
        nonlocal pos
        trades.append(finish(pos, bar, reason, points, delta))
        pos = None

    for rec in recs:
        if pos is not None and last_rth is not None and rec["t"].date() != last_rth["t"].date():
            direction = 1 if pos["side"] == "CALL" else -1
            shut(last_rth, "session", (last_rth["c"] - pos["entry"]) * direction)
        st = rec["macd"][key]
        if st["line"] is not None:
            lines.append(st["line"])
            del lines[:-4]
        if st["hist"] is not None:
            hists.append(st["hist"])
            del hists[:-4]
        turn_up, turn_down = curve_turns(lines, hists, mode)
        prev_hist, hist = st["prev_hist"], st["hist"]
        bull_cross = prev_hist is not None and hist is not None and prev_hist <= 0 < hist
        bear_cross = prev_hist is not None and hist is not None and prev_hist >= 0 > hist
        if turn_up:
            armed["CALL"] = True
            armed["PUT"] = False
        if turn_down:
            armed["PUT"] = True
            armed["CALL"] = False
        if rec["rth"]:
            last_rth = rec
        if pos is not None and rec["rth"] and rec["t"] > pos["entry_t"] and rec["t"].date() == pos["entry_t"].date():
            if stop is not None:
                hit = rec["l"] <= pos["stop_level"] if pos["side"] == "CALL" else rec["h"] >= pos["stop_level"]
                if hit:
                    shut(rec, "stop", -pos["stop_dist"])
                    continue
            adverse = (pos["side"] == "CALL" and turn_down) or (pos["side"] == "PUT" and turn_up)
            if adverse:
                direction = 1 if pos["side"] == "CALL" else -1
                shut(rec, "curve", (rec["c"] - pos["entry"]) * direction)
                continue
        if pos is None and in_entry_window(rec["t"]):
            side = None
            if bull_cross and armed["CALL"]:
                side = "CALL"
            elif bear_cross and armed["PUT"]:
                side = "PUT"
            if side is None:
                continue
            armed[side] = False
            entry = rec["c"]
            if stop is None:
                level, dist = None, None
            else:
                level = round(entry - stop if side == "CALL" else entry + stop, 2)
                dist = abs(entry - level)
            pos = {
                "side": side, "style": "curve", "entry": entry, "entry_t": rec["t"],
                "stop_dist": dist, "stop_level": level, "label": rec["label"],
                "source": mode,
            }
    if pos is not None and last_rth is not None:
        direction = 1 if pos["side"] == "CALL" else -1
        shut(last_rth, "session", (last_rth["c"] - pos["entry"]) * direction)
    return trades


def allows_quick_entry(t: datetime, window: str) -> bool:
    if t.weekday() >= 5:
        return False
    if window == "am1130":
        # Entries through the 11:30 bar. Exits may run until the noon flat.
        return ENTRY_LO <= t.time() <= dtime(11, 30)
    if window == "morning":
        return ENTRY_LO <= t.time() <= ENTRY_HI
    return ENTRY_LO <= t.time() < dtime(15, 0)


def macd_extreme(lines: list[float], side: str) -> bool:
    """Bottom/top 25% of the last 30 MACD-line values, and on the correct side of zero."""
    if len(lines) < 30:
        return False
    window = lines[-30:]
    cur = window[-1]
    rank = sum(1 for x in window if x <= cur) / 30.0
    if side == "CALL":
        return cur < 0 and rank <= 0.25
    return cur > 0 and rank >= 0.75


def price_extended(rec, side: str) -> bool:
    ema, vwap, close = rec["ema"], rec["vwap"], rec["c"]
    if ema is None or vwap is None:
        return False
    if side == "CALL":
        return close < vwap and close < ema
    return close > vwap and close > ema


def quick_resolve(pos, rec, spec):
    """Stop and target on the bar's range; color and the clock at the close.

    If the $0.30 stop and the small target both print, the level closer to
    the open is filled. A tie is the stop.
    """
    side = pos["side"]
    stop_hit = rec["l"] <= pos["stop_level"] if side == "CALL" else rec["h"] >= pos["stop_level"]
    tp_hit = rec["h"] >= pos["tp_level"] if side == "CALL" else rec["l"] <= pos["tp_level"]
    if stop_hit or tp_hit:
        if stop_hit and tp_hit:
            take_stop = abs(rec["o"] - pos["stop_level"]) <= abs(rec["o"] - pos["tp_level"])
        else:
            take_stop = stop_hit
        if take_stop:
            return "stop", -pos["stop_dist"]
        return "tp", pos["tp_dist"]
    if spec["color_exit"]:
        want = "green" if side == "CALL" else "red"
        if rec["color"] == want:
            direction = 1 if side == "CALL" else -1
            return "color", (rec["c"] - pos["entry"]) * direction
    if rec["t"] >= pos["deadline"]:
        direction = 1 if side == "CALL" else -1
        return "time", (rec["c"] - pos["entry"]) * direction
    return None


def simulate_quick(recs, spec, delta: float) -> list[dict]:
    """Enter the moment the MACD curls. Do not wait for the signal line.

    Exit is a small option target, optionally the first HA bar in the trade's
    direction, a 2- or 3-minute clock, and a $0.30 QQQ disaster stop. One
    position. No 12-trade cap. No same-bar re-entry.
    """
    key = (spec["series"], spec["fast"], spec["slow"], spec["sig"])
    mode = spec["curve"]
    lines: list[float] = []
    hists: list[float] = []
    trades = []
    pos = None
    last_rth = None

    def shut(bar, reason, points):
        nonlocal pos
        trades.append(finish(pos, bar, reason, points, delta))
        pos = None

    for rec in recs:
        if pos is not None and last_rth is not None and rec["t"].date() != last_rth["t"].date():
            direction = 1 if pos["side"] == "CALL" else -1
            shut(last_rth, "session", (last_rth["c"] - pos["entry"]) * direction)
        st = rec["macd"][key]
        if st["line"] is not None:
            lines.append(st["line"])
        if st["hist"] is not None:
            hists.append(st["hist"])
        turn_up, turn_down = curve_turns(lines, hists, mode)
        if rec["rth"]:
            last_rth = rec
        if pos is not None and rec["rth"] and rec["t"] > pos["entry_t"] and rec["t"].date() == pos["entry_t"].date():
            hit = quick_resolve(pos, rec, spec)
            if hit:
                shut(rec, hit[0], hit[1])
                continue
        if pos is None and allows_quick_entry(rec["t"], spec["window"]):
            side = "CALL" if turn_up else ("PUT" if turn_down else None)
            if side is None:
                continue
            if spec["context"] and not (macd_extreme(lines, side) and price_extended(rec, side)):
                continue
            entry = rec["c"]
            level = round(entry - 0.30 if side == "CALL" else entry + 0.30, 2)
            dist = abs(entry - level)
            tp = tp_points(spec["tp"], delta)
            pos = {
                "side": side, "style": "quick", "entry": entry, "entry_t": rec["t"],
                "stop_dist": dist, "stop_level": level,
                "tp_dist": tp, "tp_level": entry + tp if side == "CALL" else entry - tp,
                "deadline": rec["t"] + timedelta(minutes=spec["time_min"]),
                "label": rec["label"], "source": mode,
            }
    if pos is not None and last_rth is not None:
        direction = 1 if pos["side"] == "CALL" else -1
        shut(last_rth, "session", (last_rth["c"] - pos["entry"]) * direction)
    return trades


def bollinger(closes: list[float], nstd: float):
    """SMA(20) ± nstd * population stdev, same construction as bar_signal.Bollinger."""
    if len(closes) < 20:
        return None
    w = closes[-20:]
    mid = sum(w) / 20.0
    var = sum((x - mid) ** 2 for x in w) / 20.0
    sd = var ** 0.5
    return mid, mid + nstd * sd, mid - nstd * sd


def wick_ok(bar, side: str) -> bool:
    """Rejection wick at least half the bar. Lower wick for a call, upper for a put."""
    rng = bar["h"] - bar["l"]
    if rng <= 1e-9:
        return False
    if side == "CALL":
        wick = min(bar["o"], bar["c"]) - bar["l"]
    else:
        wick = bar["h"] - max(bar["o"], bar["c"])
    return wick / rng >= 0.50


def vol_spike(recent: list[dict], pos: int, mult: float) -> bool:
    """Touch-bar volume vs the prior 20 bars on the extended-hours tape.

    Yahoo premarket volume is 0, so those minutes are skipped. The average
    needs 10 positive prints. Attached-feed volume is used when we have it,
    including premarket from the Oct 21-22 file.
    """
    if pos < 20:
        return False
    prior = [recent[j]["v"] for j in range(pos - 20, pos) if recent[j]["v"] > 0]
    if len(prior) < 10:
        return False
    avg = sum(prior) / len(prior)
    return avg > 0 and recent[pos]["v"] >= mult * avg


def consecutive_pierce(recent: list[dict], touch_n: int, side: str) -> bool:
    window = recent[-(touch_n + 1):]
    key = "touch_lo" if side == "CALL" else "touch_hi"
    flags = [b[key] for b in window]
    return any(flags[j] and flags[j + 1] for j in range(len(flags) - 1))


def far_extended(rec, side: str) -> bool:
    """Close at least $0.50 beyond both EMA20 and VWAP."""
    ema, vwap, close = rec["ema"], rec["vwap"], rec["c"]
    if ema is None or vwap is None:
        return False
    if side == "CALL":
        return close <= ema - 0.50 and close <= vwap - 0.50
    return close >= ema + 0.50 and close >= vwap + 0.50


def simulate_bband(recs, spec, delta: float) -> list[dict]:
    """Bollinger touch plus a MACD turn or signal-line cross.

    A call needs the low through the lower band on this bar or within the
    previous N bars, and the MACD trigger. Puts mirror off the upper band.
    Entries only inside the window. A hold can last until the last regular
    bar of that day. One position. No 12-trade cap. No same-bar re-entry.
    """
    key = (spec["series"], spec["fast"], spec["slow"], spec["sig"])
    closes: list[float] = []
    lines: list[float] = []
    hists: list[float] = []
    last_lower = None  # (bar index, low of the touch bar)
    last_upper = None
    recent: list[dict] = []
    trades = []
    pos = None
    last_rth = None
    last_pre_noon = None
    i = -1

    def shut(bar, reason, points):
        nonlocal pos
        trades.append(finish(pos, bar, reason, points, delta))
        pos = None

    for rec in recs:
        i += 1
        if pos is not None and last_rth is not None and rec["t"].date() != last_rth["t"].date():
            direction = 1 if pos["side"] == "CALL" else -1
            shut(last_rth, "session", (last_rth["c"] - pos["entry"]) * direction)
        closes.append(rec["c"])
        st = rec["macd"][key]
        if st["line"] is not None:
            lines.append(st["line"])
        if st["hist"] is not None:
            hists.append(st["hist"])
        band = bollinger(closes, spec["nstd"])
        if band is not None:
            mid, upper, lower = band
            if rec["l"] <= lower:
                last_lower = (i, rec["l"])
            if rec["h"] >= upper:
                last_upper = (i, rec["h"])
            touch_lo = rec["l"] <= lower
            touch_hi = rec["h"] >= upper
        else:
            mid = upper = lower = None
            touch_lo = touch_hi = False
        recent.append({
            "v": rec["v"], "o": rec["o"], "h": rec["h"], "l": rec["l"], "c": rec["c"],
            "touch_lo": touch_lo, "touch_hi": touch_hi,
        })
        if len(recent) > 80:
            # Keep indexes aligned with `i` by not dropping the front. 80 is
            # enough for a 20-bar volume average plus the touch window, and
            # spike() uses positions inside this list. Rebuild positions from
            # the tail only, so trim is safe if we recompute positions from
            # the tail rather than from `i`.
            del recent[:-80]
        turn_up, turn_down = curve_turns(lines, hists, "slope")
        prev_hist, hist = st["prev_hist"], st["hist"]
        bull_cross = prev_hist is not None and hist is not None and prev_hist <= 0 < hist
        bear_cross = prev_hist is not None and hist is not None and prev_hist >= 0 > hist
        if rec["rth"]:
            last_rth = rec
        if rec["rth"] and rec["t"].time() < dtime(12, 0):
            last_pre_noon = rec
        if (spec.get("window") == "am1130" and pos is not None and rec["t"].time() >= dtime(12, 0)
                and rec["t"].date() == pos["entry_t"].date()):
            if last_pre_noon is not None and last_pre_noon["t"] >= pos["entry_t"]:
                direction = 1 if pos["side"] == "CALL" else -1
                shut(last_pre_noon, "noon", (last_pre_noon["c"] - pos["entry"]) * direction)
            continue
        if pos is not None and rec["rth"] and rec["t"] > pos["entry_t"] and rec["t"].date() == pos["entry_t"].date():
            against = (pos["side"] == "CALL" and turn_down) or (pos["side"] == "PUT" and turn_up)
            stop_hit = rec["l"] <= pos["stop_level"] if pos["side"] == "CALL" else rec["h"] >= pos["stop_level"]
            mode = spec["bb_exit"]
            target_hit = False
            target_pts = None
            if mode == "mid" and mid is not None:
                if pos["side"] == "CALL" and mid > pos["entry"] and rec["h"] >= mid:
                    target_hit, target_pts = True, mid - pos["entry"]
                elif pos["side"] == "PUT" and mid < pos["entry"] and rec["l"] <= mid:
                    target_hit, target_pts = True, pos["entry"] - mid
            elif mode == "opp" and upper is not None:
                if pos["side"] == "CALL" and upper > pos["entry"] and rec["h"] >= upper:
                    target_hit, target_pts = True, upper - pos["entry"]
                elif pos["side"] == "PUT" and lower < pos["entry"] and rec["l"] <= lower:
                    target_hit, target_pts = True, pos["entry"] - lower
            elif mode == "latch20":
                fav = (rec["h"] - pos["entry"]) if pos["side"] == "CALL" else (pos["entry"] - rec["l"])
                if fav >= pos["tp_dist"]:
                    pos["latched"] = True
            if stop_hit and (mode in ("curl", "latch20") or not target_hit):
                shut(rec, "stop", -pos["stop_dist"])
                continue
            if stop_hit and target_hit:
                tlevel = pos["entry"] + target_pts if pos["side"] == "CALL" else pos["entry"] - target_pts
                if abs(rec["o"] - pos["stop_level"]) <= abs(rec["o"] - tlevel):
                    shut(rec, "stop", -pos["stop_dist"])
                else:
                    shut(rec, mode, target_pts)
                continue
            if target_hit:
                shut(rec, mode, target_pts)
                continue
            if mode == "curl" and against:
                direction = 1 if pos["side"] == "CALL" else -1
                shut(rec, "curl", (rec["c"] - pos["entry"]) * direction)
                continue
            if mode == "latch20" and pos.get("latched") and against:
                direction = 1 if pos["side"] == "CALL" else -1
                shut(rec, "fade", (rec["c"] - pos["entry"]) * direction)
                continue
        if pos is None and allows_quick_entry(rec["t"], spec["window"]) and band is not None:
            if spec["trigger_mode"] == "slope":
                side = "CALL" if turn_up else ("PUT" if turn_down else None)
            else:
                side = "CALL" if bull_cross else ("PUT" if bear_cross else None)
            if side is None:
                continue
            touched = last_lower if side == "CALL" else last_upper
            if touched is None or i - touched[0] > spec["touch_n"]:
                continue
            macd_line = lines[-1] if lines else None
            if spec["need_zero"] and macd_line is not None:
                if side == "CALL" and not macd_line < 0:
                    continue
                if side == "PUT" and not macd_line > 0:
                    continue
            if spec["need_zero"] and macd_line is None:
                continue
            # Ingredient filters. Positions are into `recent`, whose tail is
            # the touch window. Volume uses the cleaned tape (attached feed
            # where we have it, winsorized Yahoo elsewhere).
            window = recent[-(spec["touch_n"] + 1):]
            base = len(recent) - len(window)
            key_touch = "touch_lo" if side == "CALL" else "touch_hi"
            pierces = [base + j for j, b in enumerate(window) if b[key_touch]]
            if spec.get("vol_mult") and not any(vol_spike(recent, p, spec["vol_mult"]) for p in pierces):
                continue
            if spec.get("wick") and not any(wick_ok(recent[p], side) for p in pierces):
                continue
            if spec.get("deep") and not macd_extreme(lines, side):
                continue
            if spec.get("stretch") and not (far_extended(rec, side) or consecutive_pierce(recent, spec["touch_n"], side)):
                continue
            entry = rec["c"]
            stop = spec["disaster"]
            if stop == "bar":
                # $0.05 past the touch bar. Never closer than $0.15, so the
                # stop cannot sit on the fill or on the wrong side of it.
                if side == "CALL":
                    level = round(min(touched[1] - 0.05, entry - 0.15), 2)
                else:
                    level = round(max(touched[1] + 0.05, entry + 0.15), 2)
            else:
                level = round(entry - stop if side == "CALL" else entry + stop, 2)
            pos = {
                "side": side, "style": "bband", "entry": entry, "entry_t": rec["t"],
                "stop_dist": abs(entry - level), "stop_level": level,
                "tp_dist": tp_points(0.20, delta), "latched": False,
                "label": rec["label"], "source": spec["trigger_mode"],
            }
    if pos is not None and last_rth is not None:
        direction = 1 if pos["side"] == "CALL" else -1
        shut(last_rth, "session", (last_rth["c"] - pos["entry"]) * direction)
    return trades


def finish(pos, rec, reason, points, delta) -> dict:
    gross, net = opt_dollars(points, delta)
    return {
        "day": pos["entry_t"].date().isoformat(),
        "entry_t": pos["entry_t"].isoformat(),
        "exit_t": rec["t"].isoformat(),
        "side": pos["side"],
        "style": pos["style"],
        "source": pos["source"],
        "label": pos["label"],
        "entry": round(pos["entry"], 4),
        "exit_reason": reason,
        "stop_dist": None if pos.get("stop_dist") is None else round(pos["stop_dist"], 3),
        "qqq_points": round(points, 4),
        "opt_gross": round(gross, 2),
        "opt_net": round(net, 2),
        "win": net > 1e-9,
    }


def wilson_lower(wins: int, n: int, z: float = 1.96) -> float | None:
    if n <= 0:
        return None
    p = wins / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / den


def summarize(trades: list[dict], sessions: list[str]) -> dict:
    by = defaultdict(list)
    for tr in trades:
        by[tr["day"]].append(tr)
    days = []
    days_above = 0
    no_trade = 0
    for day in sessions:
        rows = by.get(day, [])
        n = len(rows)
        wins = sum(1 for r in rows if r["win"])
        gross_wins = sum(1 for r in rows if r["opt_gross"] > 1e-9)
        point_wins = sum(1 for r in rows if r["qqq_points"] > 1e-9)
        wr = (wins / n) if n else None
        if n == 0:
            no_trade += 1
        elif wr > 0.70:
            days_above += 1
        days.append({
            "day": day,
            "trades": n,
            "wins": wins,
            "win_rate": None if wr is None else round(wr, 4),
            "gross_win_rate": None if n == 0 else round(gross_wins / n, 4),
            "point_win_rate": None if n == 0 else round(point_wins / n, 4),
            "net": round(sum(r["opt_net"] for r in rows), 2),
            "qqq_points": round(sum(r["qqq_points"] for r in rows), 3),
            "above_70": bool(n and wr > 0.70),
        })
    n = len(trades)
    wins = sum(1 for r in trades if r["win"])
    gainers = [r["opt_net"] for r in trades if r["win"]]
    losers = [r["opt_net"] for r in trades if not r["win"]]
    reasons = defaultdict(int)
    for r in trades:
        reasons[r["exit_reason"]] += 1
    return {
        "trades": n,
        "wins": wins,
        "win_rate": None if n == 0 else round(wins / n, 4),
        "wilson95_low": None if n == 0 else round(wilson_lower(wins, n), 4),
        "gross_win_rate": None if n == 0 else round(sum(1 for r in trades if r["opt_gross"] > 1e-9) / n, 4),
        "point_win_rate": None if n == 0 else round(sum(1 for r in trades if r["qqq_points"] > 1e-9) / n, 4),
        "avg_win": None if not gainers else round(sum(gainers) / len(gainers), 2),
        "avg_loss": None if not losers else round(sum(losers) / len(losers), 2),
        "net": round(sum(r["opt_net"] for r in trades), 2),
        "gross": round(sum(r["opt_gross"] for r in trades), 2),
        "qqq_points": round(sum(r["qqq_points"] for r in trades), 3),
        "avg_stop": None if not any(r.get("stop_dist") for r in trades) else round(
            sum(r["stop_dist"] for r in trades if r.get("stop_dist")) /
            sum(1 for r in trades if r.get("stop_dist")), 3),
        "exits": dict(reasons),
        "sessions": len(sessions),
        "days_above_70": days_above,
        "days_no_trade": no_trade,
        "days_traded": len(sessions) - no_trade,
        "days": days,
    }


def sessions_of(recs) -> list[str]:
    seen = []
    have = set()
    for rec in recs:
        if not rth(rec["t"]):
            continue
        key = rec["t"].date().isoformat()
        if key not in have:
            have.add(key)
            seen.append(key)
    return seen


def slice_summary(summary: dict, lo: str | None, hi: str | None) -> dict:
    days = [d for d in summary["days"]
            if (lo is None or d["day"] >= lo) and (hi is None or d["day"] <= hi)]
    # Rebuild a thin overall from the day rows. Wins aren't stored as a list of
    # trades here, so use the day win counts.
    trades = sum(d["trades"] for d in days)
    wins = sum(d["wins"] for d in days)
    return {
        "sessions": len(days),
        "trades": trades,
        "wins": wins,
        "win_rate": None if trades == 0 else round(wins / trades, 4),
        "net": round(sum(d["net"] for d in days), 2),
        "qqq_points": round(sum(d["qqq_points"] for d in days), 3),
        "days_above_70": sum(1 for d in days if d["above_70"]),
        "days_no_trade": sum(1 for d in days if d["trades"] == 0),
        "days": [{k: d[k] for k in ("day", "trades", "wins", "win_rate", "net", "above_70")} for d in days],
    }


def build_specs() -> list[dict]:
    specs = [{"name": "current_rules", "kind": "baseline"}]
    for fast, slow, sig in MACD_SPECS:
        for series in ("close", "ha"):
            for trigger in ("signal_cross", "hist_hook", "zero_cross"):
                for filt in (False, True):
                    for exit_style in ("chop", "trend"):
                        filt_name = "ema20" if filt else "none"
                        name = f"macd_{fast}_{slow}_{sig}_{series}_{trigger}_{filt_name}_{exit_style}"
                        specs.append({
                            "name": name, "kind": "macd", "fast": fast, "slow": slow, "sig": sig,
                            "series": series, "trigger": trigger, "trend_filter": filt, "exit": exit_style,
                        })
    for fast, slow, sig in MACD_SPECS:
        specs.append({
            "name": f"filter_hist_{fast}_{slow}_{sig}",
            "kind": "filter", "fast": fast, "slow": slow, "sig": sig, "series": "close",
            "trigger": "hist_sign", "trend_filter": False, "exit": "native",
        })
    for fast, slow, sig, series, trigger, filt in (
        (12, 26, 9, "close", "signal_cross", False),
        (6, 13, 5, "close", "signal_cross", False),
        (12, 26, 9, "close", "signal_cross", True),
        (12, 26, 9, "close", "zero_cross", False),
        (12, 26, 9, "close", "hist_hook", False),
    ):
        filt_name = "ema20" if filt else "none"
        specs.append({
            "name": f"gated_{fast}_{slow}_{sig}_{series}_{trigger}_{filt_name}",
            "kind": "gated", "fast": fast, "slow": slow, "sig": sig, "series": series,
            "trigger": trigger, "trend_filter": filt, "exit": "native",
        })
    # MACD + RSI only. Listed in full before any of these cells are scored.
    # 2 speeds x 2 RSI lengths x 2 exits x (1 confirm + 2 reversal windows) = 24.
    for fast, slow, sig in MACD_SPECS:
        for rsi_n in (14, 7):
            for exit_style in ("chop", "trend"):
                specs.append({
                    "name": f"mrsi_{fast}_{slow}_{sig}_rsi{rsi_n}_confirm50_{exit_style}",
                    "kind": "macd_rsi", "fast": fast, "slow": slow, "sig": sig,
                    "series": "close", "trigger": "signal_cross", "trend_filter": False,
                    "exit": exit_style, "mode": "confirm", "rsi_n": rsi_n, "n": None,
                })
                for n in (3, 5):
                    specs.append({
                        "name": f"mrsi_{fast}_{slow}_{sig}_rsi{rsi_n}_rev_n{n}_{exit_style}",
                        "kind": "macd_rsi", "fast": fast, "slow": slow, "sig": sig,
                        "series": "close", "trigger": "signal_cross", "trend_filter": False,
                        "exit": exit_style, "mode": "reversal", "rsi_n": rsi_n, "n": n,
                    })
    # MACD curve rule from Xavier's chart. Listed before this run.
    # Decision cells are the four slope rows on regular closes (his words:
    # hook, then signal cross; exit when the MACD line curls the other way).
    # Histogram rows are the white/pink bars. HA is a check on the slope rule
    # at 12/26/9 only. Not every combination: 12 cells, not 2x2x3x2.
    curve_rows = [
        (12, 26, 9, "close", "slope", None),
        (12, 26, 9, "close", "slope", 0.50),
        (6, 13, 5, "close", "slope", None),
        (6, 13, 5, "close", "slope", 0.50),
        (12, 26, 9, "close", "hist1", None),
        (12, 26, 9, "close", "hist1", 0.50),
        (12, 26, 9, "close", "hist2", None),
        (12, 26, 9, "close", "hist2", 0.50),
        (6, 13, 5, "close", "hist1", None),
        (6, 13, 5, "close", "hist1", 0.50),
        (12, 26, 9, "ha", "slope", None),
        (12, 26, 9, "ha", "slope", 0.50),
    ]
    for fast, slow, sig, series, curve, disaster in curve_rows:
        stop_name = "nostop" if disaster is None else "stop50"
        specs.append({
            "name": f"curve_{fast}_{slow}_{sig}_{series}_{curve}_{stop_name}",
            "kind": "curve", "fast": fast, "slow": slow, "sig": sig, "series": series,
            "trigger": "signal_cross", "trend_filter": False, "exit": "curve",
            "curve": curve, "disaster": disaster,
        })
    # In-and-out curl. Listed before this run. Enter on the turn itself.
    # Decision cells are the eight unfiltered slope rows in the morning.
    # tp is the option percent. color_exit takes the first HA bar with the trade.
    # context is the photo: MACD in the outer 25% of its last 30 bars and beyond
    # zero, and price beyond both VWAP and EMA20.
    quick_rows = []
    for fast, slow, sig in ((12, 26, 9), (6, 13, 5)):
        for tp, minutes, color in ((0.10, 3, False), (0.10, 3, True), (0.05, 2, False), (0.15, 3, False)):
            quick_rows.append((fast, slow, sig, "slope", tp, minutes, color, False, "morning"))
    quick_rows.extend([
        (12, 26, 9, "hist1", 0.10, 3, True, False, "morning"),
        (12, 26, 9, "slope", 0.10, 3, True, True, "morning"),
        (12, 26, 9, "slope", 0.10, 3, True, True, "rth"),
        (12, 26, 9, "slope", 0.10, 3, True, False, "rth"),
        (6, 13, 5, "slope", 0.10, 3, True, True, "morning"),
    ])
    for fast, slow, sig, curve, tp, minutes, color, context, window in quick_rows:
        color_name = "color" if color else "nocolor"
        ctx_name = "ctx" if context else "raw"
        tp_name = f"tp{int(tp * 100)}"
        specs.append({
            "name": f"quick_{fast}_{slow}_{sig}_{curve}_{tp_name}_{minutes}m_{color_name}_{ctx_name}_{window}",
            "kind": "quick", "fast": fast, "slow": slow, "sig": sig, "series": "close",
            "trigger": "slope_turn", "trend_filter": False, "exit": "quick",
            "curve": curve, "tp": tp, "time_min": minutes, "color_exit": color,
            "context": context, "window": window,
        })
    # Bollinger touch plus MACD. Listed before this run.
    # Decision cells are the first four: 12/26/9, band 20/2, touch within 2
    # bars, morning, $0.50 stop, no zero filter, four exits.
    # Touch is the low through the lower band, or the high through the upper.
    bb_rows = [
        (12, 26, 9, "slope", 2.0, 2, False, "curl", 0.50, "morning"),
        (12, 26, 9, "cross", 2.0, 2, False, "curl", 0.50, "morning"),
        (12, 26, 9, "slope", 2.0, 2, False, "mid", 0.50, "morning"),
        (12, 26, 9, "slope", 2.0, 2, False, "latch20", 0.50, "morning"),
        (6, 13, 5, "slope", 2.0, 2, False, "curl", 0.50, "morning"),
        (12, 26, 9, "slope", 2.5, 2, False, "curl", 0.50, "morning"),
        (12, 26, 9, "slope", 2.0, 0, False, "curl", 0.50, "morning"),
        (12, 26, 9, "slope", 2.0, 2, True, "curl", 0.50, "morning"),
        (12, 26, 9, "slope", 2.0, 2, False, "curl", 0.50, "rth"),
        (12, 26, 9, "slope", 2.0, 2, False, "mid", 0.50, "rth"),
        (12, 26, 9, "slope", 2.0, 2, False, "opp", 0.50, "morning"),
        (12, 26, 9, "slope", 2.0, 2, False, "curl", 0.30, "morning"),
        (12, 26, 9, "slope", 2.0, 2, False, "latch20", 0.50, "rth"),
        # $0.30 on the other two decision exits, and a stop $0.05 past the
        # touch bar. Every Bollinger cell has a stop. There is no no-stop row.
        (12, 26, 9, "slope", 2.0, 2, False, "mid", 0.30, "morning"),
        (12, 26, 9, "slope", 2.0, 2, False, "latch20", 0.30, "morning"),
        (12, 26, 9, "slope", 2.0, 2, False, "curl", "bar", "morning"),
        (12, 26, 9, "slope", 2.0, 2, False, "latch20", "bar", "morning"),
        (12, 26, 9, "slope", 2.0, 2, False, "mid", "bar", "morning"),
        (12, 26, 9, "slope", 2.0, 2, False, "curl", "bar", "rth"),
    ]
    # Chart ingredients, named before this run. Each filter alone at $0.50,
    # then the stack, then the same stack at the touch-bar stop and at $1.
    # Full session is the stack plus a $1 check on the plain curl. Filters
    # do not remove the stop.
    ingredient_rows = []
    for tag, vol, wick, deep, stretch in (
        ("vol15", 1.5, False, False, False),
        ("vol20", 2.0, False, False, False),
        ("wick", None, True, False, False),
        ("deep", None, False, True, False),
        ("stretch", None, False, False, True),
        ("stack", 1.5, True, True, True),
    ):
        for stop, window in ((0.50, "morning"), ("bar", "morning")):
            ingredient_rows.append((tag, vol, wick, deep, stretch, stop, window))
    ingredient_rows.extend([
        ("stack", 1.5, True, True, True, 1.00, "morning"),
        ("stack", 1.5, True, True, True, 0.50, "rth"),
        ("stack", 1.5, True, True, True, "bar", "rth"),
        ("stack", 1.5, True, True, True, 1.00, "rth"),
        ("any", None, False, False, False, 1.00, "morning"),
        ("any", None, False, False, False, 1.00, "rth"),
    ])
    for tag, vol, wick, deep, stretch, stop, window in ingredient_rows:
        sname = "bar" if stop == "bar" else str(int(round(float(stop) * 100)))
        specs.append({
            "name": f"bb_12_26_9_slope_k20_n2_{tag}_curl_s{sname}_{window}",
            "kind": "bband", "fast": 12, "slow": 26, "sig": 9, "series": "close",
            "trigger": "slope", "trend_filter": False, "exit": "curl",
            "trigger_mode": "slope", "nstd": 2.0, "touch_n": 2,
            "need_zero": False, "bb_exit": "curl", "disaster": stop, "window": window,
            "vol_mult": vol, "wick": wick, "deep": deep, "stretch": stretch,
        })
    for fast, slow, sig, trig, nstd, touch_n, need_zero, bb_exit, stop, window in bb_rows:
        kname = str(nstd).replace(".", "")
        zname = "zero" if need_zero else "any"
        sname = "bar" if stop == "bar" else str(int(round(stop * 100)))
        specs.append({
            "name": f"bb_{fast}_{slow}_{sig}_{trig}_k{kname}_n{touch_n}_{zname}_{bb_exit}_s{sname}_{window}",
            "kind": "bband", "fast": fast, "slow": slow, "sig": sig, "series": "close",
            "trigger": trig, "trend_filter": False, "exit": bb_exit,
            "trigger_mode": trig, "nstd": nstd, "touch_n": touch_n,
            "need_zero": need_zero, "bb_exit": bb_exit, "disaster": stop, "window": window,
        })
    # 08:30-11:30 entries, flat by noon. Indicators stay on extended hours.
    specs.append({"name": "current_rules_1130", "kind": "baseline", "window": "am1130"})
    for tag, vol, wick, deep, stretch, stop, bb_exit in (
        ("any", None, False, False, False, 0.50, "curl"),
        ("deep", None, False, True, False, 0.50, "curl"),
        ("any", None, False, False, False, "bar", "curl"),
        ("any", None, False, False, False, "bar", "latch20"),
        ("any", None, False, False, False, 0.50, "opp"),
    ):
        sname = "bar" if stop == "bar" else str(int(round(float(stop) * 100)))
        specs.append({
            "name": f"bb_12_26_9_slope_k20_n2_{tag}_{bb_exit}_s{sname}_am1130",
            "kind": "bband", "fast": 12, "slow": 26, "sig": 9, "series": "close",
            "trigger": "slope", "trend_filter": False, "exit": bb_exit,
            "trigger_mode": "slope", "nstd": 2.0, "touch_n": 2,
            "need_zero": False, "bb_exit": bb_exit, "disaster": stop, "window": "am1130",
            "vol_mult": vol, "wick": wick, "deep": deep, "stretch": stretch,
        })
    return specs


# These names were listed in the script before the run. The note treats them
# as the decision set. The rest of the MACD grid is a sensitivity sweep.
REFERENCE = [
    "macd_12_26_9_close_signal_cross_none_chop",
    "macd_12_26_9_close_signal_cross_none_trend",
    "macd_12_26_9_close_signal_cross_ema20_chop",
    "macd_12_26_9_close_signal_cross_ema20_trend",
    "macd_6_13_5_close_signal_cross_none_chop",
    "macd_6_13_5_close_signal_cross_none_trend",
    "macd_12_26_9_close_zero_cross_none_trend",
    "macd_12_26_9_close_hist_hook_none_chop",
    "macd_12_26_9_ha_signal_cross_none_chop",
    "macd_12_26_9_ha_signal_cross_none_trend",
]

# Decision set for the MACD+RSI follow-up, named before that run. The other
# 16 cells in the 24 are the same ideas with the other RSI length or the
# other N, reported as a sweep and not used to crown a winner.
RSI_REFERENCE = [
    "mrsi_12_26_9_rsi14_confirm50_chop",
    "mrsi_12_26_9_rsi14_confirm50_trend",
    "mrsi_6_13_5_rsi14_confirm50_chop",
    "mrsi_6_13_5_rsi14_confirm50_trend",
    "mrsi_12_26_9_rsi14_rev_n5_chop",
    "mrsi_12_26_9_rsi14_rev_n5_trend",
    "mrsi_6_13_5_rsi7_confirm50_chop",
    "mrsi_12_26_9_rsi7_rev_n3_chop",
]

# Decision set for the curve rule: MACD-line slope, regular closes, both
# speeds, with and without the $0.50 disaster stop. Named before that run.
CURVE_REFERENCE = [
    "curve_12_26_9_close_slope_nostop",
    "curve_12_26_9_close_slope_stop50",
    "curve_6_13_5_close_slope_nostop",
    "curve_6_13_5_close_slope_stop50",
]

# Decision set for the in-and-out curl: slope turn, no context filter,
# morning window, both speeds, the four exit packages. Named before that run.
QUICK_REFERENCE = [
    "quick_12_26_9_slope_tp10_3m_nocolor_raw_morning",
    "quick_12_26_9_slope_tp10_3m_color_raw_morning",
    "quick_12_26_9_slope_tp5_2m_nocolor_raw_morning",
    "quick_12_26_9_slope_tp15_3m_nocolor_raw_morning",
    "quick_6_13_5_slope_tp10_3m_nocolor_raw_morning",
    "quick_6_13_5_slope_tp10_3m_color_raw_morning",
    "quick_6_13_5_slope_tp5_2m_nocolor_raw_morning",
    "quick_6_13_5_slope_tp15_3m_nocolor_raw_morning",
]

# Decision set for Bollinger plus MACD. Named before that run.
BB_REFERENCE = [
    "bb_12_26_9_slope_k20_n2_any_curl_s50_morning",
    "bb_12_26_9_cross_k20_n2_any_curl_s50_morning",
    "bb_12_26_9_slope_k20_n2_any_mid_s50_morning",
    "bb_12_26_9_slope_k20_n2_any_latch20_s50_morning",
]

AM1130 = [
    "current_rules_1130",
    "bb_12_26_9_slope_k20_n2_any_curl_s50_am1130",
    "bb_12_26_9_slope_k20_n2_deep_curl_s50_am1130",
    "bb_12_26_9_slope_k20_n2_any_curl_sbar_am1130",
    "bb_12_26_9_slope_k20_n2_any_latch20_sbar_am1130",
    "bb_12_26_9_slope_k20_n2_any_opp_s50_am1130",
]

# MACD signal-line cross, regular close, no trend filter. The pair to beat
# when asking whether RSI adds anything.
MACD_ONLY_CROSS = [
    "macd_12_26_9_close_signal_cross_none_chop",
    "macd_12_26_9_close_signal_cross_none_trend",
    "macd_6_13_5_close_signal_cross_none_chop",
    "macd_6_13_5_close_signal_cross_none_trend",
]


def regime_minutes(recs) -> dict:
    """Count 09:00-12:00 CT bars by day label. One label per minute, not a daily tag."""
    out = {}
    for rec in recs:
        if not (dtime(9, 0) <= rec["t"].time() <= ENTRY_HI):
            continue
        day = rec["t"].date().isoformat()
        bucket = out.setdefault(day, defaultdict(int))
        bucket[rec["label"]] += 1
    return {d: dict(v) for d, v in out.items()}


def pack(summary: dict, trades: list[dict] | None, keep_trades: bool) -> dict:
    body = {k: v for k, v in summary.items() if k != "days"}
    body["days"] = summary["days"]
    body["focus_week"] = slice_summary(summary, FOCUS_LO, FOCUS_HI)
    body["before_focus"] = slice_summary(summary, None, "2026-10-23")
    if keep_trades and trades is not None:
        body["trade_list"] = trades
    return body


def oct29_afternoon(recs, trade_bank) -> dict:
    """What the 12/26/9 MACD was doing on Oct 29 from 14:20 to 14:40 CT."""
    bars = []
    prev_line = None
    prev_d = None
    for rec in recs:
        if rec["t"].date().isoformat() != "2026-10-29":
            continue
        st = rec["macd"][("close", 12, 26, 9)]
        line = st["line"]
        d = None if line is None or prev_line is None else line - prev_line
        turn = None
        if d is not None and prev_d is not None:
            if d > 0 and prev_d <= 0:
                turn = "up"
            elif d < 0 and prev_d >= 0:
                turn = "down"
        if dtime(14, 20) <= rec["t"].time() <= dtime(14, 40):
            below = (rec["ema"] is not None and rec["vwap"] is not None
                     and rec["c"] < rec["ema"] and rec["c"] < rec["vwap"])
            above = (rec["ema"] is not None and rec["vwap"] is not None
                     and rec["c"] > rec["ema"] and rec["c"] > rec["vwap"])
            bars.append({
                "t": rec["t"].strftime("%H:%M"),
                "close": round(rec["c"], 2),
                "ha": rec["color"],
                "ema": None if rec["ema"] is None else round(rec["ema"], 2),
                "vwap": None if rec["vwap"] is None else round(rec["vwap"], 2),
                "macd": None if line is None else round(line, 4),
                "hist": None if st["hist"] is None else round(st["hist"], 4),
                "turn": turn,
                "extended_below": below,
                "extended_above": above,
            })
        prev_d = d
        prev_line = line
    fired = []
    for name, trades in trade_bank.items():
        if not str(name).startswith("quick_"):
            continue
        for tr in trades:
            et = datetime.fromisoformat(tr["entry_t"])
            if et.date().isoformat() == "2026-10-29" and dtime(14, 15) <= et.time() <= dtime(14, 45):
                fired.append({
                    "name": name, "t": et.strftime("%H:%M"), "side": tr["side"],
                    "exit": tr["exit_reason"], "pts": tr["qqq_points"], "net": tr["opt_net"],
                    "entry": tr["entry"], "exit_t": tr["exit_t"][11:16],
                })
    return {"bars": bars, "trades": fired}


def oct29_bb_snapshot(recs, trade_bank) -> dict:
    """Bollinger(20, 2) and the 12/26/9 line around 14:10-14:40 CT on Oct 29."""
    closes: list[float] = []
    lines: list[float] = []
    hists: list[float] = []
    bars = []
    for rec in recs:
        if rec["t"].date().isoformat() != "2026-10-29":
            continue
        closes.append(rec["c"])
        st = rec["macd"][("close", 12, 26, 9)]
        if st["line"] is not None:
            lines.append(st["line"])
        if st["hist"] is not None:
            hists.append(st["hist"])
        turn_up, turn_down = curve_turns(lines, hists, "slope")
        prev_hist, hist = st["prev_hist"], st["hist"]
        bull = prev_hist is not None and hist is not None and prev_hist <= 0 < hist
        band = bollinger(closes, 2.0)
        band25 = bollinger(closes, 2.5)
        if not (dtime(14, 10) <= rec["t"].time() <= dtime(14, 40)):
            continue
        row = {
            "t": rec["t"].strftime("%H:%M"),
            "close": round(rec["c"], 2),
            "low": round(rec["l"], 2),
            "high": round(rec["h"], 2),
            "ha": rec["color"],
            "macd": None if st["line"] is None else round(st["line"], 4),
            "hist": None if hist is None else round(hist, 4),
            "turn_up": turn_up,
            "turn_down": turn_down,
            "bull_cross": bull,
        }
        if band is not None:
            mid, upper, lower = band
            row.update({
                "mid": round(mid, 2), "upper": round(upper, 2), "lower": round(lower, 2),
                "touch_lower": rec["l"] <= lower, "touch_upper": rec["h"] >= upper,
            })
        if band25 is not None:
            row["lower25"] = round(band25[2], 2)
            row["touch_lower25"] = rec["l"] <= band25[2]
        bars.append(row)
    fired = []
    for name, trades in trade_bank.items():
        if not str(name).startswith("bb_"):
            continue
        for tr in trades:
            et = datetime.fromisoformat(tr["entry_t"])
            if et.date().isoformat() == "2026-10-29" and dtime(14, 10) <= et.time() <= dtime(14, 45):
                fired.append({
                    "name": name, "t": et.strftime("%H:%M"), "side": tr["side"],
                    "exit": tr["exit_reason"], "pts": tr["qqq_points"], "net": tr["opt_net"],
                    "entry": tr["entry"], "exit_t": tr["exit_t"][11:16],
                })
    return {"bars": bars, "trades": fired}


def oct29_ingredients(recs) -> dict:
    """Which chart ingredients the 14:17 CT hook would have passed."""
    closes: list[float] = []
    lines: list[float] = []
    hists: list[float] = []
    recent: list[dict] = []
    for rec in recs:
        if rec["t"].date().isoformat() != "2026-10-29":
            continue
        closes.append(rec["c"])
        st = rec["macd"][("close", 12, 26, 9)]
        if st["line"] is not None:
            lines.append(st["line"])
        if st["hist"] is not None:
            hists.append(st["hist"])
        band = bollinger(closes, 2.0)
        touch_lo = bool(band and rec["l"] <= band[2])
        touch_hi = bool(band and rec["h"] >= band[1])
        recent.append({
            "v": rec["v"], "o": rec["o"], "h": rec["h"], "l": rec["l"], "c": rec["c"],
            "touch_lo": touch_lo, "touch_hi": touch_hi,
        })
        if rec["t"].strftime("%H:%M") != "14:17":
            continue
        turn_up, _turn_down = curve_turns(lines, hists, "slope")
        window = recent[-3:]
        base = len(recent) - len(window)
        pierces = [base + j for j, b in enumerate(window) if b["touch_lo"]]
        ratios = []
        wick_fracs = []
        for p in pierces:
            b = recent[p]
            rng = b["h"] - b["l"]
            if rng > 0:
                wick_fracs.append(round((min(b["o"], b["c"]) - b["l"]) / rng, 3))
            if p >= 20:
                prior = [recent[j]["v"] for j in range(p - 20, p) if recent[j]["v"] > 0]
                if prior:
                    ratios.append(round(b["v"] / (sum(prior) / len(prior)), 2))
        return {
            "t": "14:17",
            "close": round(rec["c"], 2),
            "turn_up": turn_up,
            "n_pierces_in_window": len(pierces),
            "wick_fractions": wick_fracs,
            "wick_pass": any(wick_ok(recent[p], "CALL") for p in pierces),
            "vol_ratios": ratios,
            "vol15": any(vol_spike(recent, p, 1.5) for p in pierces),
            "vol20": any(vol_spike(recent, p, 2.0) for p in pierces),
            "deep": macd_extreme(lines, "CALL"),
            "far_050": far_extended(rec, "CALL"),
            "consecutive_pierce": consecutive_pierce(recent, 2, "CALL"),
            "stretch": far_extended(rec, "CALL") or consecutive_pierce(recent, 2, "CALL"),
            "ema": None if rec["ema"] is None else round(rec["ema"], 2),
            "vwap": None if rec["vwap"] is None else round(rec["vwap"], 2),
            "macd": None if not lines else round(lines[-1], 4),
            "volume_note": "afternoon bars are winsorized Yahoo; the attached feed ends near 12:19 CT",
        }
    return {"t": "14:17", "missing": True}


def run() -> dict:
    ordered = load_bars()
    hours = assert_extended_hours(ordered)
    recs = prepare(ordered)
    checks = indicator_checks(recs)
    sess = sessions_of(recs)
    specs = build_specs()
    for spec in specs:
        if spec["kind"] == "bband" and spec.get("disaster") not in (0.30, 0.50, 1.00, "bar"):
            raise SystemExit(f"Bollinger cell missing a stop: {spec['name']}")
    results = []
    trade_bank = {}
    for spec in specs:
        if spec["kind"] == "curve":
            trades = simulate_curve(recs, spec, DELTA)
        elif spec["kind"] == "quick":
            trades = simulate_quick(recs, spec, DELTA)
        elif spec["kind"] == "bband":
            trades = simulate_bband(recs, spec, DELTA)
        else:
            trades = simulate(recs, spec, DELTA, "proximity")
        summary = summarize(trades, sess)
        keep = spec["name"] == "current_rules" or spec["name"] in REFERENCE or spec["kind"] in ("filter", "gated")
        results.append({"name": spec["name"], "kind": spec["kind"], **pack(summary, trades, keep)})
        trade_bank[spec["name"]] = trades

    # Stop-first path on the decision set only, same delta. Asks whether the
    # intrabar tie-break is doing the work.
    stop_first = {}
    for spec in specs:
        if spec["name"] != "current_rules" and spec["name"] not in REFERENCE and spec["name"] not in RSI_REFERENCE and spec["kind"] not in ("filter", "gated"):
            continue
        trades = simulate(recs, spec, DELTA, "stop_first")
        stop_first[spec["name"]] = summarize(trades, sess)["net"], summarize(trades, sess)["win_rate"], summarize(trades, sess)["trades"]

    # Delta sensitivity changes the option target distance, so it is a resim.
    sensitivity = []
    sens_names = ["current_rules", *REFERENCE[:6], "filter_hist_12_26_9", "gated_12_26_9_close_signal_cross_none"]
    spec_by = {s["name"]: s for s in specs}
    for delta in (0.15, 0.22, 0.35):
        for name in sens_names:
            trades = simulate(recs, spec_by[name], delta, "proximity")
            sm = summarize(trades, sess)
            sensitivity.append({
                "name": name, "delta": delta, "trades": sm["trades"],
                "win_rate": sm["win_rate"], "net": sm["net"],
                "days_above_70": sm["days_above_70"], "days_no_trade": sm["days_no_trade"],
                "avg_win": sm["avg_win"], "avg_loss": sm["avg_loss"],
            })

    macd_only = [r for r in results if r["kind"] == "macd"]
    base = next(r for r in results if r["name"] == "current_rules")
    wr_vals = [r["win_rate"] for r in macd_only if r["win_rate"] is not None]
    net_vals = [r["net"] for r in macd_only]
    better_wr = sum(1 for r in macd_only if r["win_rate"] is not None and base["win_rate"] is not None and r["win_rate"] > base["win_rate"])
    better_net = sum(1 for r in macd_only if base["net"] is not None and r["net"] > base["net"])
    better_both = sum(
        1 for r in macd_only
        if r["win_rate"] is not None and base["win_rate"] is not None
        and r["win_rate"] > base["win_rate"] and r["net"] > base["net"]
    )
    ranked = sorted(macd_only, key=lambda r: (
        r["days_above_70"],
        r["win_rate"] if r["win_rate"] is not None else -1,
        r["net"],
    ), reverse=True)
    mrsi = [r for r in results if r["kind"] == "macd_rsi"]
    mrsi_wr = [r["win_rate"] for r in mrsi if r["win_rate"] is not None]
    mrsi_net = [r["net"] for r in mrsi]
    mrsi_ranked = sorted(mrsi, key=lambda r: (
        r["days_above_70"],
        r["win_rate"] if r["win_rate"] is not None else -1,
        r["net"],
    ), reverse=True)
    mrsi_both = sum(
        1 for r in mrsi
        if r["win_rate"] is not None and base["win_rate"] is not None
        and r["win_rate"] > base["win_rate"] and r["net"] > base["net"]
    )
    curves = [r for r in results if r["kind"] == "curve"]
    curve_wr = [r["win_rate"] for r in curves if r["win_rate"] is not None]
    curve_net = [r["net"] for r in curves]
    curve_ranked = sorted(curves, key=lambda r: (
        r["days_above_70"],
        r["win_rate"] if r["win_rate"] is not None else -1,
        r["net"],
    ), reverse=True)
    curve_both = sum(
        1 for r in curves
        if r["win_rate"] is not None and base["win_rate"] is not None
        and r["win_rate"] > base["win_rate"] and r["net"] > base["net"]
    )
    quicks = [r for r in results if r["kind"] == "quick"]
    quick_wr = [r["win_rate"] for r in quicks if r["win_rate"] is not None]
    quick_net = [r["net"] for r in quicks]
    quick_ranked = sorted(quicks, key=lambda r: (
        r["days_above_70"],
        r["win_rate"] if r["win_rate"] is not None else -1,
        r["net"],
    ), reverse=True)
    quick_both = sum(
        1 for r in quicks
        if r["win_rate"] is not None and base["win_rate"] is not None
        and r["win_rate"] > base["win_rate"] and r["net"] > base["net"]
    )
    bands = [r for r in results if r["kind"] == "bband"]
    band_wr = [r["win_rate"] for r in bands if r["win_rate"] is not None]
    band_net = [r["net"] for r in bands]
    band_ranked = sorted(bands, key=lambda r: (
        r["days_above_70"],
        r["win_rate"] if r["win_rate"] is not None else -1,
        r["net"],
    ), reverse=True)
    band_both = sum(
        1 for r in bands
        if r["win_rate"] is not None and base["win_rate"] is not None
        and r["win_rate"] > base["win_rate"] and r["net"] > base["net"]
    )

    payload = {
        "assumptions": {
            "premium": PREMIUM,
            "delta": DELTA,
            "fee_per_side": 0.65,
            "fee_round_trip": FEE_RT,
            "tp_chop_qqq": round(tp_points(0.25, DELTA), 4),
            "tp_trend_qqq": round(tp_points(0.12, DELTA), 4),
            "path": "proximity (if stop and target print on the same 1m bar, the level closer to that bar's open is filled; a tie goes to the stop)",
            "window": "entries 08:30-12:00 CT inclusive, one position, 1-bar cooldown, max 12 buys/day",
            "baseline": "CHOP = VWAP fade, bar stop clamped $0.15-$1.00, +25% option, 10 min. TREND = EMA20 retest (near-only + slope gate), $0.30 stop, +12% option, 5 min. MIXED and WARMUP flat.",
            "win": "option net after $1.30 fees > 0. A day clears 70% only when it has trades and the win rate is strictly above 70%.",
        },
        "checks": checks,
        "sessions": sess,
        "regime_minutes_0900_1200": regime_minutes(recs),
        "baseline": base,
        "distribution": {
            "macd_variants": len(macd_only),
            "win_rate_min": round(min(wr_vals), 4),
            "win_rate_median": round(statistics.median(wr_vals), 4),
            "win_rate_max": round(max(wr_vals), 4),
            "net_min": round(min(net_vals), 2),
            "net_median": round(statistics.median(net_vals), 2),
            "net_max": round(max(net_vals), 2),
            "n_higher_win_rate_than_baseline": better_wr,
            "n_higher_net_than_baseline": better_net,
            "n_higher_win_rate_and_net": better_both,
            "n_any_day_sweep_above_70": sum(1 for r in macd_only if r["days_above_70"] == r["sessions"]),
            "top": [{"name": r["name"], "trades": r["trades"], "win_rate": r["win_rate"], "net": r["net"],
                     "days_above_70": r["days_above_70"], "days_no_trade": r["days_no_trade"]} for r in ranked[:8]],
            "bottom": [{"name": r["name"], "trades": r["trades"], "win_rate": r["win_rate"], "net": r["net"],
                        "days_above_70": r["days_above_70"]} for r in ranked[-3:]],
        },
        "mrsi_distribution": {
            "variants": len(mrsi),
            "predeclared_decision_set": RSI_REFERENCE,
            "win_rate_min": None if not mrsi_wr else round(min(mrsi_wr), 4),
            "win_rate_median": None if not mrsi_wr else round(statistics.median(mrsi_wr), 4),
            "win_rate_max": None if not mrsi_wr else round(max(mrsi_wr), 4),
            "net_min": None if not mrsi_net else round(min(mrsi_net), 2),
            "net_median": None if not mrsi_net else round(statistics.median(mrsi_net), 2),
            "net_max": None if not mrsi_net else round(max(mrsi_net), 2),
            "n_higher_win_rate_than_baseline": sum(1 for r in mrsi if r["win_rate"] is not None and base["win_rate"] is not None and r["win_rate"] > base["win_rate"]),
            "n_higher_net_than_baseline": sum(1 for r in mrsi if r["net"] > base["net"]),
            "n_higher_win_rate_and_net": mrsi_both,
            "n_any_day_sweep_above_70": sum(1 for r in mrsi if r["days_above_70"] == r["sessions"]),
            "max_days_above_70": max((r["days_above_70"] for r in mrsi), default=0),
            "top": [{"name": r["name"], "trades": r["trades"], "win_rate": r["win_rate"], "net": r["net"],
                     "days_above_70": r["days_above_70"], "days_no_trade": r["days_no_trade"]} for r in mrsi_ranked[:5]],
        },
        "curve_distribution": {
            "variants": len(curves),
            "predeclared_decision_set": CURVE_REFERENCE,
            "win_rate_min": None if not curve_wr else round(min(curve_wr), 4),
            "win_rate_median": None if not curve_wr else round(statistics.median(curve_wr), 4),
            "win_rate_max": None if not curve_wr else round(max(curve_wr), 4),
            "net_min": None if not curve_net else round(min(curve_net), 2),
            "net_median": None if not curve_net else round(statistics.median(curve_net), 2),
            "net_max": None if not curve_net else round(max(curve_net), 2),
            "n_higher_win_rate_than_baseline": sum(1 for r in curves if r["win_rate"] is not None and base["win_rate"] is not None and r["win_rate"] > base["win_rate"]),
            "n_higher_net_than_baseline": sum(1 for r in curves if r["net"] > base["net"]),
            "n_higher_win_rate_and_net": curve_both,
            "n_any_day_sweep_above_70": sum(1 for r in curves if r["days_above_70"] == r["sessions"]),
            "max_days_above_70": max((r["days_above_70"] for r in curves), default=0),
            "top": [{"name": r["name"], "trades": r["trades"], "win_rate": r["win_rate"], "net": r["net"],
                     "avg_win": r["avg_win"], "avg_loss": r["avg_loss"],
                     "days_above_70": r["days_above_70"], "days_no_trade": r["days_no_trade"],
                     "exits": r["exits"]} for r in curve_ranked[:5]],
        },
        "quick_distribution": {
            "variants": len(quicks),
            "predeclared_decision_set": QUICK_REFERENCE,
            "win_rate_min": None if not quick_wr else round(min(quick_wr), 4),
            "win_rate_median": None if not quick_wr else round(statistics.median(quick_wr), 4),
            "win_rate_max": None if not quick_wr else round(max(quick_wr), 4),
            "net_min": None if not quick_net else round(min(quick_net), 2),
            "net_median": None if not quick_net else round(statistics.median(quick_net), 2),
            "net_max": None if not quick_net else round(max(quick_net), 2),
            "n_higher_win_rate_than_baseline": sum(1 for r in quicks if r["win_rate"] is not None and base["win_rate"] is not None and r["win_rate"] > base["win_rate"]),
            "n_higher_net_than_baseline": sum(1 for r in quicks if r["net"] > base["net"]),
            "n_higher_win_rate_and_net": quick_both,
            "n_any_day_sweep_above_70": sum(1 for r in quicks if r["days_above_70"] == r["sessions"]),
            "max_days_above_70": max((r["days_above_70"] for r in quicks), default=0),
            "top": [{"name": r["name"], "trades": r["trades"], "win_rate": r["win_rate"], "net": r["net"],
                     "avg_win": r["avg_win"], "avg_loss": r["avg_loss"], "gross": r["gross"],
                     "days_above_70": r["days_above_70"], "days_no_trade": r["days_no_trade"],
                     "exits": r["exits"]} for r in quick_ranked[:5]],
        },
        "bb_distribution": {
            "variants": len(bands),
            "predeclared_decision_set": BB_REFERENCE,
            "win_rate_min": None if not band_wr else round(min(band_wr), 4),
            "win_rate_median": None if not band_wr else round(statistics.median(band_wr), 4),
            "win_rate_max": None if not band_wr else round(max(band_wr), 4),
            "net_min": None if not band_net else round(min(band_net), 2),
            "net_median": None if not band_net else round(statistics.median(band_net), 2),
            "net_max": None if not band_net else round(max(band_net), 2),
            "n_higher_win_rate_than_baseline": sum(1 for r in bands if r["win_rate"] is not None and base["win_rate"] is not None and r["win_rate"] > base["win_rate"]),
            "n_higher_net_than_baseline": sum(1 for r in bands if r["net"] > base["net"]),
            "n_higher_win_rate_and_net": band_both,
            "n_any_day_sweep_above_70": sum(1 for r in bands if r["days_above_70"] == r["sessions"]),
            "max_days_above_70": max((r["days_above_70"] for r in bands), default=0),
            "top": [{"name": r["name"], "trades": r["trades"], "win_rate": r["win_rate"], "net": r["net"],
                     "avg_win": r["avg_win"], "avg_loss": r["avg_loss"], "gross": r["gross"],
                     "days_above_70": r["days_above_70"], "days_no_trade": r["days_no_trade"],
                     "exits": r["exits"]} for r in band_ranked[:5]],
        },
        "oct29_afternoon": oct29_afternoon(recs, trade_bank),
        "oct29_bb": oct29_bb_snapshot(recs, trade_bank),
        "oct29_ingredients": oct29_ingredients(recs),
        "extended_hours": hours,
        "stop_first": {k: {"net": v[0], "win_rate": v[1], "trades": v[2]} for k, v in stop_first.items()},
        "sensitivity": sensitivity,
    }
    # Per-day rows for every variant. Full trade lists only for the book and the
    # filter/gated tests — those are the rows the note discusses trade by trade.
    slim = []
    for r in results:
        item = {k: v for k, v in r.items() if k != "trade_list"}
        if r["name"] == "current_rules" or r["kind"] in ("filter", "gated"):
            item["trade_list"] = r.get("trade_list", [])
        slim.append(item)
    payload["results"] = slim
    payload["baseline"] = next(r for r in slim if r["name"] == "current_rules")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str))
    return payload


def fmt_wr(x):
    return "  n/a" if x is None else f"{x*100:5.1f}%"


def fmt_money(x):
    return f"{x:8.2f}"


def print_report(payload: dict) -> None:
    a = payload["assumptions"]
    c = payload["checks"]
    eh = payload.get("extended_hours") or {}
    print(f"Sessions: {len(payload['sessions'])}  {payload['sessions'][0]} .. {payload['sessions'][-1]}")
    if eh:
        print(f"Extended hours in the indicator tape: premarket {eh['premarket_bars_min']}-{eh['premarket_bars_max']} bars/session "
              f"across {eh['sessions_with_premarket']} sessions. Thin postmarket days: {eh['thin_postmarket_days'] or 'none'}")
    print(f"Check 11:58 CT  EMA err {c['ema_err']:+.5f}  VWAP err {c['vwap_err']:+.5f}  MACD hist err {c['macd_hist_err']:+.5f}  label {c['label']}")
    print(f"Proxy: premium ${a['premium']:.2f}  delta {a['delta']}  fee ${a['fee_round_trip']:.2f} RT")
    print(f"Option target in QQQ points: chop +25% -> ${a['tp_chop_qqq']}   trend +12% -> ${a['tp_trend_qqq']}")
    print()
    base = payload["baseline"]
    print(f"CURRENT RULES  trades {base['trades']:3d}  win {fmt_wr(base['win_rate'])}  "
          f"wilson95 {fmt_wr(base['wilson95_low'])}  net ${fmt_money(base['net'])}  "
          f"pts {base['qqq_points']}  days>70% {base['days_above_70']}/{base['sessions']}  "
          f"no-trade {base['days_no_trade']}  avgW {base['avg_win']} avgL {base['avg_loss']}  exits {base['exits']}")
    print("  per day:")
    for d in base["days"]:
        mark = "PASS" if d["above_70"] else ("flat" if d["trades"] == 0 else "fail")
        print(f"    {d['day']}  {d['wins']:2d}/{d['trades']:<2d}  {fmt_wr(d['win_rate'])}  ${d['net']:8.2f}  {mark}")
    print()
    dist = payload["distribution"]
    print(f"MACD-ONLY GRID  n={dist['macd_variants']}  win {dist['win_rate_min']*100:.1f}/{dist['win_rate_median']*100:.1f}/{dist['win_rate_max']*100:.1f}% min/med/max")
    print(f"  net ${dist['net_min']:.0f} / ${dist['net_median']:.0f} / ${dist['net_max']:.0f} min/med/max")
    print(f"  higher win rate than rules: {dist['n_higher_win_rate_than_baseline']}    higher net: {dist['n_higher_net_than_baseline']}    both: {dist['n_higher_win_rate_and_net']}")
    print(f"  variants that cleared >70% every session: {dist['n_any_day_sweep_above_70']}")
    print("  top by (days>70%, win rate, net) — in-sample, not the decision:")
    for row in dist["top"]:
        print(f"    {row['name']:48s}  n {row['trades']:3d}  {fmt_wr(row['win_rate'])}  ${row['net']:8.2f}  days>70 {row['days_above_70']}  flat {row['days_no_trade']}")
    print()
    by = {r["name"]: r for r in payload["results"]}
    print("REFERENCE (predeclared):")
    for name in ["current_rules", *REFERENCE]:
        r = by[name]
        fw = r["focus_week"]
        print(f"  {name:48s}  n {r['trades']:3d}  {fmt_wr(r['win_rate'])}  ${r['net']:8.2f}  "
              f"days>70 {r['days_above_70']:2d}  flat {r['days_no_trade']:2d}  "
              f"focus {fw['wins']}/{fw['trades']} ${fw['net']:.0f}  avgW {r['avg_win']} avgL {r['avg_loss']}")
    print()
    print("FILTER / GATED:")
    for r in payload["results"]:
        if r["kind"] not in ("filter", "gated"):
            continue
        fw = r["focus_week"]
        print(f"  {r['name']:48s}  n {r['trades']:3d}  {fmt_wr(r['win_rate'])}  ${r['net']:8.2f}  "
              f"days>70 {r['days_above_70']:2d}  flat {r['days_no_trade']:2d}  focus {fw['wins']}/{fw['trades']} ${fw['net']:.0f}")
    print()
    print("FOCUS WEEK current-rules trades:")
    for tr in base.get("trade_list", []):
        if FOCUS_LO <= tr["day"] <= FOCUS_HI:
            print(f"  {tr['entry_t'][5:16]} {tr['side']:4s} {tr['source']:14s} {tr['label']:6s} "
                  f"-> {tr['exit_reason']:4s} pts {tr['qqq_points']:+6.3f} net ${tr['opt_net']:7.2f}")
    print()
    print("Regime minutes 09:00-12:00 on the focus week:")
    for day, counts in payload["regime_minutes_0900_1200"].items():
        if FOCUS_LO <= day <= FOCUS_HI:
            print(f"  {day} {counts}")
    print()
    md = payload["mrsi_distribution"]
    print(f"MACD+RSI GRID  n={md['variants']}  win {md['win_rate_min']*100:.1f}/{md['win_rate_median']*100:.1f}/{md['win_rate_max']*100:.1f}% min/med/max")
    print(f"  net ${md['net_min']:.0f} / ${md['net_median']:.0f} / ${md['net_max']:.0f} min/med/max")
    print(f"  higher win rate than rules: {md['n_higher_win_rate_than_baseline']}    higher net: {md['n_higher_net_than_baseline']}    both: {md['n_higher_win_rate_and_net']}")
    print(f"  cleared >70% every session: {md['n_any_day_sweep_above_70']}    most days>70 in any cell: {md['max_days_above_70']}/{base['sessions']}")
    print("  in-sample top (not the decision):")
    for row in md["top"]:
        print(f"    {row['name']:48s}  n {row['trades']:3d}  {fmt_wr(row['win_rate'])}  ${row['net']:8.2f}  days>70 {row['days_above_70']}  flat {row['days_no_trade']}")
    print("MACD+RSI ALL CELLS:")
    for r in payload["results"]:
        if r["kind"] != "macd_rsi":
            continue
        fw = r["focus_week"]
        mark = " *" if r["name"] in RSI_REFERENCE else ""
        print(f"  {r['name']:48s}  n {r['trades']:3d}  {fmt_wr(r['win_rate'])}  ${r['net']:8.2f}  "
              f"days>70 {r['days_above_70']:2d}  flat {r['days_no_trade']:2d}  "
              f"focus {fw['wins']}/{fw['trades']} ${fw['net']:.0f}{mark}")
    print("MACD+RSI DECISION SET, per day (* = above 70%):")
    for name in RSI_REFERENCE:
        r = by[name]
        bits = []
        for d in r["days"]:
            if d["trades"] == 0:
                bits.append(f"{d['day'][5:]} flat")
            else:
                flag = "*" if d["above_70"] else ""
                bits.append(f"{d['day'][5:]} {d['wins']}/{d['trades']}{flag} ${d['net']:.0f}")
        print(f"  {name}")
        print("    " + " | ".join(bits))
    print()
    cd = payload["curve_distribution"]
    print(f"CURVE GRID  n={cd['variants']}  win {cd['win_rate_min']*100:.1f}/{cd['win_rate_median']*100:.1f}/{cd['win_rate_max']*100:.1f}% min/med/max")
    print(f"  net ${cd['net_min']:.0f} / ${cd['net_median']:.0f} / ${cd['net_max']:.0f}")
    print(f"  higher win rate than rules: {cd['n_higher_win_rate_than_baseline']}  higher net: {cd['n_higher_net_than_baseline']}  both: {cd['n_higher_win_rate_and_net']}")
    print(f"  cleared >70% every session: {cd['n_any_day_sweep_above_70']}  most days>70: {cd['max_days_above_70']}/{base['sessions']}")
    print("CURVE ALL CELLS (* = decision set):")
    for r in payload["results"]:
        if r["kind"] != "curve":
            continue
        fw = r["focus_week"]
        mark = " *" if r["name"] in CURVE_REFERENCE else ""
        print(f"  {r['name']:46s}  n {r['trades']:3d}  {fmt_wr(r['win_rate'])}  ${r['net']:8.2f}  "
              f"avg {r['avg_win']}/{r['avg_loss']}  days>70 {r['days_above_70']:2d}  flat {r['days_no_trade']:2d}  "
              f"focus {fw['wins']}/{fw['trades']} ${fw['net']:.0f}  exits {r['exits']}{mark}")
    print("CURVE DECISION SET, per day (* = above 70%):")
    for name in CURVE_REFERENCE:
        r = by[name]
        bits = []
        for d in r["days"]:
            if d["trades"] == 0:
                bits.append(f"{d['day'][5:]} flat")
            else:
                flag = "*" if d["above_70"] else ""
                bits.append(f"{d['day'][5:]} {d['wins']}/{d['trades']}{flag} ${d['net']:.0f}")
        print(f"  {name}")
        print("    " + " | ".join(bits))
    print()
    qd = payload["quick_distribution"]
    print(f"QUICK CURL  n={qd['variants']}  win {qd['win_rate_min']*100:.1f}/{qd['win_rate_median']*100:.1f}/{qd['win_rate_max']*100:.1f}% min/med/max")
    print(f"  net ${qd['net_min']:.0f} / ${qd['net_median']:.0f} / ${qd['net_max']:.0f}")
    print(f"  higher win rate than rules: {qd['n_higher_win_rate_than_baseline']}  higher net: {qd['n_higher_net_than_baseline']}  both: {qd['n_higher_win_rate_and_net']}")
    print(f"  cleared >70% every session: {qd['n_any_day_sweep_above_70']}  most days>70: {qd['max_days_above_70']}/{base['sessions']}")
    print("QUICK ALL CELLS (* = decision set):")
    for r in payload["results"]:
        if r["kind"] != "quick":
            continue
        fw = r["focus_week"]
        mark = " *" if r["name"] in QUICK_REFERENCE else ""
        fees = r["gross"] - r["net"]
        print(f"  {r['name']:62s}  n {r['trades']:3d}  {fmt_wr(r['win_rate'])}  ${r['net']:8.2f}  "
              f"avg {r['avg_win']}/{r['avg_loss']}  fees ${fees:.0f}  days>70 {r['days_above_70']:2d}  "
              f"focus {fw['wins']}/{fw['trades']} ${fw['net']:.0f}  {r['exits']}{mark}")
    print("QUICK DECISION SET, per day:")
    for name in QUICK_REFERENCE:
        r = by[name]
        bits = []
        for d in r["days"]:
            if d["trades"] == 0:
                bits.append(f"{d['day'][5:]} flat")
            else:
                flag = "*" if d["above_70"] else ""
                bits.append(f"{d['day'][5:]} {d['wins']}/{d['trades']}{flag} ${d['net']:.0f}")
        print(f"  {name}")
        print("    " + " | ".join(bits))
    print("OCT 29 14:20-14:40 CT  12/26/9")
    for bar in payload["oct29_afternoon"]["bars"]:
        print(f"  {bar['t']} c {bar['close']} {bar['ha']:5} macd {bar['macd']} hist {bar['hist']} "
              f"turn {bar['turn']} below {bar['extended_below']} ema {bar['ema']} vwap {bar['vwap']}")
    print("  trades in 14:15-14:45:")
    for tr in payload["oct29_afternoon"]["trades"]:
        print(f"    {tr['t']} {tr['name']} {tr['side']} -> {tr['exit']} pts {tr['pts']} net {tr['net']} exit {tr['exit_t']}")
    print()
    bd = payload["bb_distribution"]
    print(f"BOLLINGER+MACD  n={bd['variants']}  win {bd['win_rate_min']*100:.1f}/{bd['win_rate_median']*100:.1f}/{bd['win_rate_max']*100:.1f}% min/med/max")
    print(f"  net ${bd['net_min']:.0f} / ${bd['net_median']:.0f} / ${bd['net_max']:.0f}")
    print(f"  higher win rate than rules: {bd['n_higher_win_rate_than_baseline']}  higher net: {bd['n_higher_net_than_baseline']}  both: {bd['n_higher_win_rate_and_net']}")
    print(f"  cleared >70% every session: {bd['n_any_day_sweep_above_70']}  most days>70: {bd['max_days_above_70']}/{base['sessions']}")
    print("BB ALL CELLS (* = decision set):")
    for r in payload["results"]:
        if r["kind"] != "bband":
            continue
        fw = r["focus_week"]
        mark = " *" if r["name"] in BB_REFERENCE else ""
        print(f"  {r['name']:62s}  n {r['trades']:3d}  {fmt_wr(r['win_rate'])}  ${r['net']:8.2f}  "
              f"avg {r['avg_win']}/{r['avg_loss']}  stop {r.get('avg_stop')}  days>70 {r['days_above_70']:2d}  "
              f"flat {r['days_no_trade']:2d}  focus {fw['wins']}/{fw['trades']} ${fw['net']:.0f}  {r['exits']}{mark}")
    print("BB DECISION SET, per day:")
    for name in BB_REFERENCE:
        r = by[name]
        bits = []
        for d in r["days"]:
            if d["trades"] == 0:
                bits.append(f"{d['day'][5:]} flat")
            else:
                flag = "*" if d["above_70"] else ""
                bits.append(f"{d['day'][5:]} {d['wins']}/{d['trades']}{flag} ${d['net']:.0f}")
        print(f"  {name}")
        print("    " + " | ".join(bits))
    print("OCT 29 BB 14:10-14:40")
    for bar in payload["oct29_bb"]["bars"]:
        if bar["t"] < "14:14" or bar["t"] > "14:36":
            continue
        print(f"  {bar['t']} c {bar['close']} lo {bar['low']} {bar['ha']:5} macd {bar['macd']} "
              f"up {bar['turn_up']} cross {bar['bull_cross']} lower {bar.get('lower')} touch {bar.get('touch_lower')} "
              f"lower25 {bar.get('lower25')} touch25 {bar.get('touch_lower25')}")
    print("  bb trades 14:10-14:45:")
    for tr in payload["oct29_bb"]["trades"]:
        print(f"    {tr['t']} {tr['name']} {tr['side']} -> {tr['exit']} pts {tr['pts']} net {tr['net']} exit {tr['exit_t']}")
    print("OCT 29 14:17 INGREDIENTS", payload["oct29_ingredients"])
    print()
    print("ENTRIES 08:30-11:30, FLAT BY 12:00")
    for name in AM1130:
        r = by[name]
        fw = r["focus_week"]
        print(f"  {name:62s}  n {r['trades']:3d}  {fmt_wr(r['win_rate'])}  ${r['net']:8.2f}  "
              f"avg {r['avg_win']}/{r['avg_loss']}  days>70 {r['days_above_70']:2d}  flat {r['days_no_trade']:2d}  "
              f"focus {fw['wins']}/{fw['trades']} ${fw['net']:.0f}  {r['exits']}")
    ranked = sorted((by[n] for n in AM1130), key=lambda r: (
        r["win_rate"] if r["win_rate"] is not None else -1, r["net"]), reverse=True)
    best = ranked[0]
    print(f"BEST BY WIN RATE THEN NET: {best['name']}")
    for d in best["days"]:
        wr = "flat" if d["trades"] == 0 else f"{d['wins']}/{d['trades']} {d['win_rate']*100:.0f}% ${d['net']:.2f}"
        flag = " PASS" if d["above_70"] else ""
        print(f"    {d['day']}  {wr}{flag}")


if __name__ == "__main__":
    print_report(run())
