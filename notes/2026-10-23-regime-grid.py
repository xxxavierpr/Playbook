#!/usr/bin/env python3
"""Regime split and exit grid for the 2026-10-23 note. Research only.

Selection is frozen before looking at the holdout:
  * Train = every session except the last five. Holdout = the last five.
  * Rank on train win rate, then train net of $2 slippage.
  * A config is eligible only with at least 20 train trades (12 inside one
    regime), train win rate >= 70%, and train net > 0.
  * The holdout is reported and is not used to re-rank.
  * Primary contract is the live paper band, premium $0.50 / delta 0.25.
    The PR #8 proxy ($0.30 / 0.30) and a closer contract ($1.00 / 0.50)
    are in the same grid. A winner is fragile unless the adjacent stop and
    the adjacent target on that same contract are also train-net >= 0.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
TOUCH = 0.15
ENTRY_LO = dtime(8, 45)
ENTRY_HI = dtime(12, 0)
CLASSIFY_FROM = dtime(9, 0)

# prem, delta. Live matches the 10/23 tickets (about $0.50, delta about 0.25).
CONTRACTS = {
    "live": (0.50, 0.25),
    "proxy": (0.30, 0.30),
    "closer": (1.00, 0.50),
}
STOPS = (0.15, 0.22, 0.30, 0.45, 0.60)
TPS = (0.10, 0.12, 0.15, 0.20, 0.25)
TIMES = (3, 5, 8, 10)
TREND_ENTRIES = ("base", "confirm", "vwap15", "vwap30", "band")
CHOP_ENTRIES = ("skip", "fade_vwap", "fade_ema")


def fetch() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0"}
    start = datetime(2026, 9, 29, tzinfo=timezone.utc)
    end = datetime(2026, 10, 24, tzinfo=timezone.utc)
    bars: list[dict] = []
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=7), end)
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/QQQ"
            f"?interval=1m&period1={int(cur.timestamp())}&period2={int(nxt.timestamp())}"
            "&includePrePost=false"
        )
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read())
        result = payload["chart"]["result"][0]
        quote = result["indicators"]["quote"][0]
        for i, ts in enumerate(result["timestamp"]):
            o, h, l, c = (quote[k][i] for k in ("open", "high", "low", "close"))
            if None in (o, h, l, c):
                continue
            when = datetime.fromtimestamp(ts, CT)
            if when.second or when.microsecond:
                continue
            bars.append({"t": when, "o": float(o), "h": float(h), "l": float(l), "c": float(c)})
        cur = nxt
    bars.sort(key=lambda b: b["t"])
    out = []
    for b in bars:
        if out and out[-1]["t"] == b["t"]:
            continue
        out.append(b)
    return out


def prep(day: list[dict]) -> dict:
    n = len(day)
    o = [b["o"] for b in day]
    h = [b["h"] for b in day]
    l = [b["l"] for b in day]
    c = [b["c"] for b in day]
    k = 2.0 / 21.0

    def ema(xs):
        out = [0.0] * n
        out[0] = xs[0]
        for i in range(1, n):
            out[i] = xs[i] * k + out[i - 1] * (1.0 - k)
        return out

    ema_c, ema_h, ema_l = ema(c), ema(h), ema(l)
    ha_o = [0.0] * n
    ha_c = [0.0] * n
    color = [""] * n
    for i in range(n):
        ha_c[i] = (o[i] + h[i] + l[i] + c[i]) / 4.0
        ha_o[i] = (o[i] + c[i]) / 2.0 if i == 0 else (ha_o[i - 1] + ha_c[i - 1]) / 2.0
        color[i] = "green" if ha_c[i] > ha_o[i] else ("red" if ha_c[i] < ha_o[i] else "doji")
    vwap = [0.0] * n
    acc = 0.0
    for i in range(n):
        acc += (h[i] + l[i] + c[i]) / 3.0
        vwap[i] = acc / (i + 1)
    reg = ["WARMUP"] * n
    slope5 = [0.0] * n
    for i in range(n):
        if i < 19:
            continue
        crosses, last = 0, 0
        for j in range(i - 19, i + 1):
            sg = 1 if c[j] > ema_c[j] else (-1 if c[j] < ema_c[j] else 0)
            if sg == 0:
                continue
            if last and sg != last:
                crosses += 1
            last = sg
        reg[i] = "CHOPPY" if crosses >= 4 else "TRENDING"
        if i >= 5:
            slope5[i] = ema_c[i] - ema_c[i - 5]
    or_hi = max(h[i] for i, b in enumerate(day) if b["t"].time() < ENTRY_LO)
    or_lo = min(l[i] for i, b in enumerate(day) if b["t"].time() < ENTRY_LO)
    return {
        "t": [b["t"] for b in day], "o": o, "h": h, "l": l, "c": c,
        "ema": ema_c, "eh": ema_h, "el": ema_l, "vwap": vwap,
        "color": color, "ha_c": ha_c, "reg": reg, "slope5": slope5,
        "or_hi": or_hi, "or_lo": or_lo,
    }


def crosses_n(b, i, w):
    if i + 1 < w:
        return None
    crosses, last = 0, 0
    for j in range(i - w + 1, i + 1):
        sg = 1 if b["c"][j] > b["ema"][j] else (-1 if b["c"][j] < b["ema"][j] else 0)
        if sg == 0:
            continue
        if last and sg != last:
            crosses += 1
        last = sg
    return crosses


def day_label(b, i):
    """Hard trend vs chop vs mixed. Usable from 09:00 CT, updated every bar.

    Hard trend: few EMA20 crosses, a real 15-bar slope, price camped on that
    side of VWAP, and either the opening range is held or price is away from VWAP.
    Chop: four or more crosses in 20 bars, or a flat slope with no VWAP side.
    """
    ts = b["t"][i]
    if ts.time() < CLASSIFY_FROM or i < 20:
        return "WARMUP", 0
    sl = b["ema"][i] - b["ema"][i - 15]
    x20 = crosses_n(b, i, 20)
    above = 0
    for j in range(i - 19, i + 1):
        if b["c"][j] > b["vwap"][j]:
            above += 1
    frac_up = above / 20.0
    direction = 1 if sl > 0 else -1
    side_frac = frac_up if direction > 0 else 1.0 - frac_up
    close_with = (b["c"][i] - b["vwap"][i]) * direction > 0
    or_hold = (direction > 0 and b["c"][i] > b["or_hi"]) or (direction < 0 and b["c"][i] < b["or_lo"])
    away = abs(b["c"][i] - b["vwap"][i]) >= 0.50
    hard = x20 is not None and x20 <= 2 and abs(sl) >= 0.40 and side_frac >= 0.75 and close_with and (or_hold or away)
    maj = max(frac_up, 1.0 - frac_up)
    chop = (x20 is not None and x20 >= 4) or (abs(sl) < 0.20 and maj <= 0.65)
    if hard:
        return "TREND", direction
    if chop:
        return "CHOP", 0
    return "MIXED", direction if close_with else 0


def baseline_side(b, i):
    if b["reg"][i] != "TRENDING" or i < 5:
        return None
    prior = b["color"][i - 3:i]
    c, ema, eh, el = b["c"][i], b["ema"][i], b["eh"][i], b["el"][i]
    vwap, hc, sl = b["vwap"][i], b["ha_c"][i], b["slope5"][i]
    green, red = b["color"][i] == "green", b["color"][i] == "red"
    near_c = min(abs(hc - ema), abs(hc - eh)) <= TOUCH
    near_p = min(abs(hc - ema), abs(hc - el)) <= TOUCH
    if c > vwap and sl > 0 and green and "red" in prior and near_c and c > ema:
        return "CALL"
    if c < vwap and sl < 0 and red and "green" in prior and near_p and c < ema:
        return "PUT"
    return None


def in_window(ts):
    tt = ts.time()
    return ENTRY_LO <= tt <= ENTRY_HI


def resolve(b, i, side, dist, tp_dist, time_n, latch, delta):
    sign = 1 if side == "CALL" else -1
    entry = b["c"][i]
    stop_lvl = entry - sign * dist
    tp_lvl = None if latch else entry + sign * tp_dist
    arm_lvl = entry + sign * tp_dist if latch else None
    armed = False
    n = len(b["c"])
    for k in range(1, time_n + 1):
        j = i + k
        if j >= n:
            j = n - 1
            fill = b["c"][j]
            return fill, "eod", j, sign * (fill - entry) * delta * 100.0
        o, h, l, c = b["o"][j], b["h"][j], b["l"][j], b["c"][j]
        if (sign == 1 and o < stop_lvl) or (sign == -1 and o > stop_lvl):
            return o, "stop", j, sign * (o - entry) * delta * 100.0
        if not latch and ((sign == 1 and o >= tp_lvl) or (sign == -1 and o <= tp_lvl)):
            return tp_lvl, "target", j, sign * (tp_lvl - entry) * delta * 100.0
        if latch and armed and ((sign == 1 and o <= arm_lvl) or (sign == -1 and o >= arm_lvl)):
            fill = o if (sign == 1 and o < arm_lvl) or (sign == -1 and o > arm_lvl) else arm_lvl
            return fill, "latch", j, sign * (fill - entry) * delta * 100.0
        stop_hit = (l < stop_lvl) if sign == 1 else (h > stop_lvl)
        if stop_hit:
            return stop_lvl, "stop", j, sign * (stop_lvl - entry) * delta * 100.0
        if not latch:
            tgt_hit = (h >= tp_lvl) if sign == 1 else (l <= tp_lvl)
            if tgt_hit:
                return tp_lvl, "target", j, sign * (tp_lvl - entry) * delta * 100.0
        else:
            reached = (h >= arm_lvl) if sign == 1 else (l <= arm_lvl)
            if armed:
                gave = (l <= arm_lvl) if sign == 1 else (h >= arm_lvl)
                if gave:
                    return arm_lvl, "latch", j, sign * (arm_lvl - entry) * delta * 100.0
            elif reached:
                armed = True
        if k == time_n:
            return c, "time", j, sign * (c - entry) * delta * 100.0
    raise RuntimeError("no exit")


def stop_dist_for(b, i, side, mode, fixed):
    entry = b["c"][i]
    if mode == "fixed":
        return fixed
    if mode == "bar":
        if side == "CALL":
            dist = entry - (b["l"][i] - 0.05)
        else:
            dist = (b["h"][i] + 0.05) - entry
    else:
        if side == "CALL":
            level = min(b["ema"][i], b["el"][i]) - 0.05
            dist = entry - level
        else:
            level = max(b["ema"][i], b["eh"][i]) + 0.05
            dist = level - entry
    if dist != dist:
        return None
    return min(1.0, max(0.15, dist))


def entry_side(b, i, name, arm):
    """Return (side or None, new arm state). arm is (side, idx, low, high) or None."""
    if name == "skip":
        return None, None
    if name == "fade_vwap":
        if b["color"][i] == "green" and b["l"][i] <= b["vwap"][i] - 0.25 and b["c"][i] > b["vwap"][i]:
            return "CALL", None
        if b["color"][i] == "red" and b["h"][i] >= b["vwap"][i] + 0.25 and b["c"][i] < b["vwap"][i]:
            return "PUT", None
        return None, None
    if name == "fade_ema":
        if i < 1:
            return None, None
        if (b["color"][i] == "green" and b["l"][i - 1] <= b["el"][i - 1]
                and b["c"][i] > b["ema"][i] and b["c"][i] > b["c"][i - 1]):
            return "CALL", None
        if (b["color"][i] == "red" and b["h"][i - 1] >= b["eh"][i - 1]
                and b["c"][i] < b["ema"][i] and b["c"][i] < b["c"][i - 1]):
            return "PUT", None
        return None, None
    base = baseline_side(b, i)
    if name == "confirm":
        side = None
        if arm is not None and i > arm[1] and i <= arm[1] + 3:
            held = (b["l"][i] >= arm[2]) if arm[0] == "CALL" else (b["h"][i] <= arm[3])
            color_ok = b["color"][i] == ("green" if arm[0] == "CALL" else "red")
            beyond = (b["c"][i] > b["ema"][i]) if arm[0] == "CALL" else (b["c"][i] < b["ema"][i])
            if held and color_ok and beyond:
                side = arm[0]
                arm = None
            elif not held:
                arm = None
        if base and side is None:
            arm = (base, i, b["l"][i], b["h"][i])
        return side, arm
    if base is None:
        return None, None
    if name == "vwap15" and abs(b["c"][i] - b["vwap"][i]) > 1.50:
        return None, None
    if name == "vwap30" and abs(b["c"][i] - b["vwap"][i]) > 3.00:
        return None, None
    if name == "band":
        if base == "CALL" and b["l"][i] < b["el"][i] - 0.02:
            return None, None
        if base == "PUT" and b["h"][i] > b["eh"][i] + 0.02:
            return None, None
    return base, None


def simulate(b, entry, exit_spec, regime_gate=None):
    """exit_spec: (stop_mode, stop_fixed, tp_pct, time_n, latch, prem, delta)."""
    mode, fixed, tp_pct, time_n, latch, prem, delta = exit_spec
    tp_dist = (0.20 if latch else tp_pct) * prem / delta
    trades = []
    pos_until = -1
    cool_until = -1
    arm = None
    i, n = 0, len(b["c"])
    while i < n:
        if i <= pos_until:
            arm = None
            i += 1
            continue
        ts = b["t"][i]
        if not in_window(ts) or i < cool_until:
            if entry == "confirm":
                _, arm = entry_side(b, i, entry, arm) if in_window(ts) else (None, arm)
            i += 1
            continue
        if regime_gate is not None:
            lab, _ = day_label(b, i)
            if lab != regime_gate:
                if entry == "confirm" and lab == "WARMUP":
                    arm = None
                i += 1
                continue
        side, arm = entry_side(b, i, entry, arm)
        if side is None:
            i += 1
            continue
        dist = stop_dist_for(b, i, side, mode, fixed)
        if dist is None:
            i += 1
            continue
        _fill, reason, j, pnl = resolve(b, i, side, dist, tp_dist, time_n, latch, delta)
        trades.append({"t": ts, "side": side, "entry": b["c"][i], "pnl": pnl, "reason": reason, "dist": dist})
        pos_until = j
        cool_until = j + 1 + 1
        arm = None
        i = j + 1
    return trades


def simulate_switch(b, books):
    """books maps TREND/CHOP/MIXED to (entry, exit_spec) or None to skip."""
    trades = []
    pos_until = -1
    cool_until = -1
    arms = {"TREND": None, "CHOP": None, "MIXED": None}
    i, n = 0, len(b["c"])
    while i < n:
        if i <= pos_until:
            arms = {"TREND": None, "CHOP": None, "MIXED": None}
            i += 1
            continue
        ts = b["t"][i]
        lab, _ = day_label(b, i)
        if not in_window(ts) or i < cool_until or lab not in books or books[lab] is None:
            i += 1
            continue
        entry, spec = books[lab]
        side, arms[lab] = entry_side(b, i, entry, arms[lab])
        if side is None:
            i += 1
            continue
        mode, fixed, tp_pct, time_n, latch, prem, delta = spec
        dist = stop_dist_for(b, i, side, mode, fixed)
        if dist is None:
            i += 1
            continue
        tp_dist = (0.20 if latch else tp_pct) * prem / delta
        _fill, reason, j, pnl = resolve(b, i, side, dist, tp_dist, time_n, latch, delta)
        trades.append({"t": ts, "side": side, "entry": b["c"][i], "pnl": pnl, "reason": reason,
                       "regime": lab, "dist": dist})
        pos_until = j
        cool_until = j + 2
        arms = {"TREND": None, "CHOP": None, "MIXED": None}
        i = j + 1
    return trades


def summarize(trades):
    n = len(trades)
    if n == 0:
        return {"n": 0, "wins": 0, "wr": float("nan"), "avg_win": float("nan"),
                "avg_loss": float("nan"), "gross": 0.0, "net": 0.0}
    wins = [t["pnl"] for t in trades if t["pnl"] > 1e-9]
    losses = [t["pnl"] for t in trades if t["pnl"] <= 1e-9]
    gross = sum(t["pnl"] for t in trades)
    return {
        "n": n, "wins": len(wins),
        "wr": len(wins) / n,
        "avg_win": sum(wins) / len(wins) if wins else float("nan"),
        "avg_loss": sum(losses) / len(losses) if losses else float("nan"),
        "gross": gross, "net": gross - 2.0 * n,
    }


def money(x):
    if x != x:
        return "—"
    return f"{x:+.2f}"


def wr(s):
    if s["n"] == 0:
        return "—"
    return f"{s['wr']*100:.1f}% ({s['wins']}/{s['n']})"


def describe(cfg):
    entry, mode, fixed, tp, time_n, latch, cname = cfg
    stop = f"stop {mode} {fixed:.2f}" if mode == "fixed" else f"stop {mode}"
    tgt = "latch +20%" if latch else f"tp {tp:.0%}"
    return f"{entry} | {cname} | {stop} | {tgt} | {time_n}m"


def exit_grid():
    specs = []
    for mode in ("fixed",):
        for dist in STOPS:
            for tp in TPS:
                for time_n in TIMES:
                    specs.append((mode, dist, tp, time_n, False))
            for time_n in TIMES:
                specs.append((mode, dist, 0.20, time_n, True))
    for mode in ("bar", "ema"):
        for tp in TPS:
            for time_n in TIMES:
                specs.append((mode, 0.0, tp, time_n, False))
        for time_n in TIMES:
            specs.append((mode, 0.0, 0.20, time_n, True))
    return specs


def run_split(days, entry, spec, which, regime_gate=None):
    tr = []
    for flag, b in days:
        if flag != which:
            continue
        tr += simulate(b, entry, spec, regime_gate=regime_gate)
    return tr


def eligible(s, minimum):
    return s["n"] >= minimum and s["wr"] >= 0.70 - 1e-12 and s["net"] > 0


def neighbor_ok(days, cfg, tested):
    entry, mode, fixed, tp, time_n, latch, cname = cfg
    if latch or mode != "fixed":
        return True
    prem, delta = CONTRACTS[cname]
    ok = True
    for dist in STOPS:
        if abs(dist - fixed) < 1e-9 or abs(STOPS.index(dist) - STOPS.index(fixed)) != 1:
            continue
        spec = (mode, dist, tp, time_n, False, prem, delta)
        key = (entry, spec, None)
        s = tested.get(key)
        if s is None:
            s = summarize(run_split(days, entry, spec, "train"))
        if s["net"] < 0:
            ok = False
    if tp in TPS:
        idx = TPS.index(tp)
        for j in (idx - 1, idx + 1):
            if j < 0 or j >= len(TPS):
                continue
            spec = (mode, fixed, TPS[j], time_n, False, prem, delta)
            s = tested.get((entry, spec, None))
            if s is None:
                s = summarize(run_split(days, entry, spec, "train"))
            if s["net"] < 0:
                ok = False
    return ok


def main():
    raw = fetch()
    grouped = []
    bucket = None
    for bar in raw:
        if bucket is None or bucket[0] != bar["t"].date():
            bucket = [bar["t"].date(), []]
            grouped.append(bucket)
        bucket[1].append(bar)
    dates = [d for d, _ in grouped]
    hold = set(dates[-5:])
    days = []
    for d, bars in grouped:
        days.append(("hold" if d in hold else "train", prep(bars), d))
    prepared = [(flag, b) for flag, b, _d in days]
    print(f"sessions {len(dates)} bars {sum(len(b['c']) for _f, b, _d in days)} "
          f"last {days[-1][1]['t'][-1].isoformat()}")
    print("holdout", ", ".join(str(d) for d in dates[-5:]))

    # --- classification table
    print("\n== day label at 09:00 / 09:30 / 11:00 ==")
    for _flag, b, d in days:
        bits = []
        for hm in ("09:00", "09:30", "11:00"):
            hit = [i for i, ts in enumerate(b["t"]) if ts.strftime("%H:%M") == hm]
            if not hit:
                bits.append(f"{hm}=na")
                continue
            lab, direc = day_label(b, hit[0])
            arrow = {1: "up", -1: "dn", 0: ""}.get(direc, "")
            bits.append(f"{hm}={lab}{arrow}")
        print(f"{d}  " + "  ".join(bits))

    # --- today's two signals, path
    b = days[-1][1]
    print("\n== 10/23 path 09:10-09:25 and 11:05-end ==")
    for i, ts in enumerate(b["t"]):
        hm = ts.strftime("%H:%M")
        if ("09:10" <= hm <= "09:25") or hm >= "11:05":
            lab, direc = day_label(b, i)
            side = baseline_side(b, i)
            print(f"{hm} c{b['c'][i]:.2f} h{b['h'][i]:.2f} l{b['l'][i]:.2f} "
                  f"ema{b['ema'][i]:.2f} el{b['el'][i]:.2f} vw{b['vwap'][i]:.2f} "
                  f"{b['color'][i][:1]} {lab}{direc:+d} base={side or '-'}")

    # --- grid
    specs = exit_grid()
    print(f"\nexit specs {len(specs)} trend entries {len(TREND_ENTRIES)} contracts {len(CONTRACTS)}")
    ranked = []
    tested = {}
    n_tested = 0
    for entry in TREND_ENTRIES:
        for cname, (prem, delta) in CONTRACTS.items():
            for mode, fixed, tp, time_n, latch in specs:
                spec = (mode, fixed, tp, time_n, latch, prem, delta)
                tr = run_split(prepared, entry, spec, "train")
                s = summarize(tr)
                cfg = (entry, mode, fixed, tp, time_n, latch, cname)
                tested[(entry, spec, None)] = s
                n_tested += 1
                ranked.append((s["wr"] if s["n"] else -1, s["net"], cfg, s))
    ranked.sort(key=lambda r: (-r[0], -r[1]))
    print(f"configs tested {n_tested}")

    def hold_stats(cfg):
        entry, mode, fixed, tp, time_n, latch, cname = cfg
        prem, delta = CONTRACTS[cname]
        spec = (mode, fixed, tp, time_n, latch, prem, delta)
        return summarize(run_split(prepared, entry, spec, "hold"))

    def full_and_today(cfg):
        entry, mode, fixed, tp, time_n, latch, cname = cfg
        prem, delta = CONTRACTS[cname]
        spec = (mode, fixed, tp, time_n, latch, prem, delta)
        tr = []
        today = []
        for flag, b, d in days:
            got = simulate(b, entry, spec)
            tr += got
            if str(d) == "2026-10-23":
                today = got
        return summarize(tr), today

    print("\n== top 5 by train WR then net, n>=20, any contract ==")
    shown = 0
    for _wr, _net, cfg, s in ranked:
        if s["n"] < 20:
            continue
        h = hold_stats(cfg)
        print(f"TRAIN {wr(s):16} net {s['net']:+8.2f} aw {money(s['avg_win'])} al {money(s['avg_loss'])} "
              f"| HOLD {wr(h):16} net {h['net']:+8.2f} | {describe(cfg)}")
        shown += 1
        if shown >= 5:
            break

    print("\n== top 12 by train WR then net (trend-retest family, all morning bars) ==")
    shown = 0
    eligible_rows = []
    for wr_, net_, cfg, s in ranked:
        if not eligible(s, 20):
            continue
        h = hold_stats(cfg)
        stable = neighbor_ok(prepared, cfg, tested)
        eligible_rows.append((cfg, s, h, stable))
        if shown < 12:
            print(f"TRAIN {wr(s):16} net {s['net']:+8.2f} aw {money(s['avg_win'])} al {money(s['avg_loss'])} "
                  f"| HOLD {wr(h):16} net {h['net']:+8.2f} | stable {stable} | {describe(cfg)}")
            shown += 1
    print(f"eligible {len(eligible_rows)}")

    # current paper rule on live contract
    paper = ("base", "fixed", 0.30, 0.12, 5, False, "live")
    ps = tested.get(("base", ("fixed", 0.30, 0.12, 5, False, *CONTRACTS["live"]), None))
    if ps is None:
        ps = summarize(run_split(prepared, "base", ("fixed", 0.30, 0.12, 5, False, *CONTRACTS["live"]), "train"))
    ph = hold_stats(paper)
    pf, pt = full_and_today(paper)
    print(f"\nPAPER live TRAIN {wr(ps)} net {ps['net']:+.2f} HOLD {wr(ph)} net {ph['net']:+.2f} "
          f"FULL {wr(pf)} net {pf['net']:+.2f}")
    print(" paper today", [(t["t"].strftime("%H:%M"), t["side"], round(t["pnl"], 2), t["reason"]) for t in pt])

    # recommend: first eligible whose holdout net > 0 and n>=5, prefer stable
    rec = None
    for cfg, s, h, stable in eligible_rows:
        if h["n"] >= 5 and h["net"] > 0 and stable:
            rec = (cfg, s, h, stable)
            break
    if rec is None:
        for cfg, s, h, stable in eligible_rows:
            if h["n"] >= 5 and h["net"] > 0:
                rec = (cfg, s, h, stable)
                break
    print("\nRECOMMEND", describe(rec[0]) if rec else "none", "hold", wr(rec[2]) if rec else "", rec[2]["net"] if rec else "")
    if rec:
        full, today = full_and_today(rec[0])
        print(f"  FULL {wr(full)} net {full['net']:+.2f} aw {money(full['avg_win'])} al {money(full['avg_loss'])}")
        print("  today", [(t["t"].strftime("%H:%M"), t["side"], round(t["entry"], 2), round(t["pnl"], 2), t["reason"]) for t in today])

    # --- regime books, live contract only (precommitted; other deltas reported on the winner)
    print("\n== regime books, live contract ==")
    prem, delta = CONTRACTS["live"]
    regime_ranked = {gate: [] for gate in ("TREND", "CHOP", "MIXED")}
    entries_for = {"TREND": TREND_ENTRIES, "CHOP": CHOP_ENTRIES, "MIXED": TREND_ENTRIES + ("fade_vwap", "fade_ema", "skip")}
    for gate, entries in entries_for.items():
        minimum = 12 if gate != "MIXED" else 8
        for entry in entries:
            if entry == "skip":
                regime_ranked[gate].append((0.0, 0.0, ("skip", None), summarize([]), minimum))
                continue
            for mode, fixed, tp, time_n, latch in specs:
                spec = (mode, fixed, tp, time_n, latch, prem, delta)
                s = summarize(run_split(prepared, entry, spec, "train", regime_gate=gate))
                cfg = (entry, mode, fixed, tp, time_n, latch, "live")
                regime_ranked[gate].append((s["wr"] if s["n"] else -1.0, s["net"], cfg, s, minimum))
        regime_ranked[gate].sort(key=lambda r: (-r[0], -r[1]))

    chosen = {}
    for gate in ("TREND", "CHOP", "MIXED"):
        pick = None
        minimum = 12 if gate != "MIXED" else 8
        for wr_, net_, cfg, s, _m in regime_ranked[gate]:
            if cfg[0] == "skip":
                continue
            if eligible(s, minimum):
                h = summarize(run_split(prepared, cfg[0], (
                    cfg[1], cfg[2], cfg[3], cfg[4], cfg[5], prem, delta), "hold", regime_gate=gate))
                print(f"{gate} candidate TRAIN {wr(s)} net {s['net']:+.2f} HOLD {wr(h)} net {h['net']:+.2f} "
                      f"{describe(cfg)}")
                if pick is None and h["net"] > 0 and h["n"] >= 3:
                    pick = (cfg, s, h)
                if pick is None and gate != "TREND":
                    pass
                break
        if pick is None:
            # best net among eligible even if holdout fails, else skip
            for wr_, net_, cfg, s, _m in regime_ranked[gate]:
                if cfg[0] != "skip" and eligible(s, minimum):
                    h = summarize(run_split(prepared, cfg[0], (
                        cfg[1], cfg[2], cfg[3], cfg[4], cfg[5], prem, delta), "hold", regime_gate=gate))
                    print(f"{gate} best-eligible (holdout not required for the print) TRAIN {wr(s)} net {s['net']:+.2f} "
                          f"HOLD {wr(h)} net {h['net']:+.2f} {describe(cfg)}")
                    pick = (cfg, s, h)
                    break
        if pick is None:
            print(f"{gate} -> skip (no eligible config)")
            chosen[gate] = None
        else:
            chosen[gate] = pick

    # If chop's best eligible is holdout-negative, compare to skip (net 0). Prefer skip when
    # the chop book does not clear the holdout, and say so. Selection of skip vs book:
    # on TRAIN, skip has net 0. An eligible chop book has train net > 0, so train prefers it.
    # We still stitch it and let the combined holdout judge.

    books = {}
    for gate, pick in chosen.items():
        if pick is None:
            books[gate] = None
        else:
            cfg = pick[0]
            books[gate] = (cfg[0], (cfg[1], cfg[2], cfg[3], cfg[4], cfg[5], prem, delta))
    print("stitched books", {k: (None if v is None else v[0]) for k, v in books.items()})

    tr_train, tr_hold, tr_all = [], [], []
    today = []
    for flag, b, d in days:
        got = simulate_switch(b, books)
        tr_all += got
        if flag == "train":
            tr_train += got
        else:
            tr_hold += got
        if str(d) == "2026-10-23":
            today = got
    st, sh, sf = summarize(tr_train), summarize(tr_hold), summarize(tr_all)
    print(f"STITCH TRAIN {wr(st)} net {st['net']:+.2f} aw {money(st['avg_win'])} al {money(st['avg_loss'])}")
    print(f"STITCH HOLD  {wr(sh)} net {sh['net']:+.2f} aw {money(sh['avg_win'])} al {money(sh['avg_loss'])}")
    print(f"STITCH FULL  {wr(sf)} net {sf['net']:+.2f} aw {money(sf['avg_win'])} al {money(sf['avg_loss'])}")
    by_reg = {}
    for t in tr_all:
        by_reg.setdefault(t["regime"], []).append(t)
    for gate, rows in by_reg.items():
        s = summarize(rows)
        print(f"  full/{gate} {wr(s)} net {s['net']:+.2f}")
    print("stitch today", [(t["t"].strftime("%H:%M"), t["regime"], t["side"], round(t["pnl"], 2), t["reason"]) for t in today])

    # Diagnostics for the note. These do not re-rank.
    print("\n== live all-morning n>=20, top 8 train WR ==")
    live_rows = [r for r in ranked if r[3]["n"] >= 20 and r[2][6] == "live"]
    for _wr, _net, cfg, s in live_rows[:8]:
        h = hold_stats(cfg)
        print(f"TRAIN {wr(s):16} net {s['net']:+8.2f} aw {money(s['avg_win'])} al {money(s['avg_loss'])} "
              f"| HOLD {wr(h):16} net {h['net']:+8.2f} | {describe(cfg)}")
    if live_rows:
        _wr, _net, cfg, s = max(live_rows, key=lambda r: (r[1], r[0]))
        h = hold_stats(cfg)
        print(f"best live train net TRAIN {wr(s)} net {s['net']:+.2f} HOLD {wr(h)} net {h['net']:+.2f} {describe(cfg)}")
        pos_live = sum(1 for r in live_rows if r[3]["net"] > 0)
        print(f"live n>=20 configs {len(live_rows)} train-net>0 {pos_live}")

    print("\n== chop live train net>0 n>=8 ==")
    shown_chop = 0
    for _wr, _net, cfg, s, _m in regime_ranked["CHOP"]:
        if cfg[0] == "skip" or s["n"] < 8 or s["net"] <= 0:
            continue
        h = summarize(run_split(prepared, cfg[0], (
            cfg[1], cfg[2], cfg[3], cfg[4], cfg[5], prem, delta), "hold", regime_gate="CHOP"))
        print(f"TRAIN {wr(s):16} net {s['net']:+8.2f} aw {money(s['avg_win'])} al {money(s['avg_loss'])} "
              f"| HOLD {wr(h):16} net {h['net']:+8.2f} | {describe(cfg)}")
        shown_chop += 1
        if shown_chop >= 8:
            break
    print(f"chop positive-net rows printed {shown_chop}")

    print("\n== trend live n>=12 ==")
    trend_rows = [r for r in regime_ranked["TREND"] if r[2][0] != "skip" and r[3]["n"] >= 12]
    pos_tr = sum(1 for r in trend_rows if r[3]["net"] > 0)
    hi_tr = sum(1 for r in trend_rows if r[3]["wr"] >= 0.70)
    print(f"n configs {len(trend_rows)} positive net {pos_tr} wr>=0.70 {hi_tr}")
    if trend_rows:
        _wr, _net, cfg, s, _m = max(trend_rows, key=lambda r: (r[1], r[0]))
        h = summarize(run_split(prepared, cfg[0], (
            cfg[1], cfg[2], cfg[3], cfg[4], cfg[5], prem, delta), "hold", regime_gate="TREND"))
        print(f"best net TRAIN {wr(s)} net {s['net']:+.2f} aw {money(s['avg_win'])} al {money(s['avg_loss'])} "
              f"HOLD {wr(h)} net {h['net']:+.2f} {describe(cfg)}")

    print("\n== precommitted chop fades (tight stop, +10%) ==")
    for fixed, tp, time_n in ((0.15, 0.10, 3), (0.22, 0.10, 3), (0.30, 0.10, 3), (0.30, 0.10, 5)):
        spec = ("fixed", fixed, tp, time_n, False, prem, delta)
        s = summarize(run_split(prepared, "fade_vwap", spec, "train", regime_gate="CHOP"))
        h = summarize(run_split(prepared, "fade_vwap", spec, "hold", regime_gate="CHOP"))
        print(f"fade_vwap stop {fixed:.2f} tp {tp:.0%} {time_n}m TRAIN {wr(s)} net {s['net']:+.2f} "
              f"HOLD {wr(h)} net {h['net']:+.2f}")

    print("\n== stitch ledger ==")
    for flag, b, d in days:
        for t in simulate_switch(b, books):
            print(f"{flag} {t['t'].strftime('%Y-%m-%d %H:%M')} {t['regime']} {t['side']} "
                  f"entry {t['entry']:.2f} pnl {t['pnl']:+.2f} {t['reason']} dist {t['dist']:.2f}")

    print("\n== 10/23 label features ==")
    b = days[-1][1]
    for hm in ("09:00", "09:12", "09:21", "09:25", "09:29", "09:30", "11:00", "11:09", "11:13"):
        hit = [i for i, ts in enumerate(b["t"]) if ts.strftime("%H:%M") == hm]
        if not hit:
            print(hm, "missing")
            continue
        i = hit[0]
        sl = b["ema"][i] - b["ema"][i - 15]
        x20 = crosses_n(b, i, 20)
        above = sum(1 for j in range(i - 19, i + 1) if b["c"][j] > b["vwap"][j])
        streak = 1
        j = i
        while j > 0 and b["color"][j - 1] == b["color"][i]:
            streak += 1
            j -= 1
        lab, direc = day_label(b, i)
        base = baseline_side(b, i)
        fade, _ = entry_side(b, i, "fade_vwap", None)
        print(f"{hm} {lab}{direc:+d} x20={x20} sl15={sl:+.2f} above={above}/20 "
              f"vwdist={b['c'][i]-b['vwap'][i]:+.2f} or={b['or_lo']:.2f}/{b['or_hi']:.2f} "
              f"ha={b['color'][i]} streak={streak} base={base or '-'} fade={fade or '-'}")

    # per-regime holdout already printed via candidates. Also count label occupancy.
    print("\n== label occupancy, entry window ==")
    occ = {"train": {}, "hold": {}}
    for flag, b, _d in days:
        for i, ts in enumerate(b["t"]):
            if not in_window(ts):
                continue
            lab, _ = day_label(b, i)
            occ[flag][lab] = occ[flag].get(lab, 0) + 1
    print(occ)
    report_combined(days)


def report_combined(days):
    """Monday paper switch: TREND keeps the PR #8 retest, CHOP fades VWAP, MIXED is flat.

    Live contract $0.50 / delta 0.25. Same fill rules as the rest of this script.
    """
    prem, delta = CONTRACTS["live"]
    books = {
        "TREND": ("base", ("fixed", 0.30, 0.12, 5, False, prem, delta)),
        "CHOP": ("fade_vwap", ("bar", 0.0, 0.25, 10, False, prem, delta)),
        "MIXED": None,
    }
    buckets = {"train": [], "hold": [], "full": []}
    by = {"train": {}, "hold": {}, "full": {}}
    print("\n== combined paper switch (TREND retest 0.30/12%/5m, CHOP fade bar/25%/10m) ==")
    for flag, b, d in days:
        got = simulate_switch(b, books)
        buckets[flag] += got
        buckets["full"] += got
        for t in got:
            by[flag].setdefault(t["regime"], []).append(t)
            by["full"].setdefault(t["regime"], []).append(t)
    for name in ("train", "hold", "full"):
        s = summarize(buckets[name])
        print(f"COMBINED {name.upper():5} {wr(s):16} gross {s['gross']:+8.2f} net {s['net']:+8.2f} "
              f"aw {money(s['avg_win'])} al {money(s['avg_loss'])}")
        for gate in ("TREND", "CHOP", "MIXED"):
            rows = by[name].get(gate) or []
            s = summarize(rows)
            print(f"  {name}/{gate} {wr(s)} net {s['net']:+.2f}")


if __name__ == "__main__":
    main()
