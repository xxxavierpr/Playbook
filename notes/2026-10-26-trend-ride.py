#!/usr/bin/env python3
"""Trend-day ride for the Monday paper switch. Research only.

Entries only on bars the day classifier labels TREND, inside 08:45-12:00 CT.
Exits follow Xavier's trend rule: no short clock. Ride until a QQQ stop, an HA
close through EMA20, or a +latch that then gives back or prints an HA bar
against the trade. Rank is train win rate, then train net after $2. The last
five sessions, including 2026-10-26 when Yahoo has it, are the holdout.
"""
from __future__ import annotations

import importlib.util
from collections import defaultdict
from datetime import time as dtime
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "grid", Path(__file__).with_name("2026-10-23-regime-grid.py"))
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

PREM, DELTA = g.CONTRACTS["live"]
WINDOW_LO, WINDOW_HI = dtime(8, 45), dtime(12, 0)


def pullback_side(b, i):
    """With-trend EMA20 tag that closes back through EMA. Direction comes from the day label."""
    lab, direc = g.day_label(b, i)
    if lab != "TREND" or direc == 0 or i < 5 or b["reg"][i] != "TRENDING":
        return None
    c, ema, eh, el = b["c"][i], b["ema"][i], b["eh"][i], b["el"][i]
    vwap, sl = b["vwap"][i], b["slope5"][i]
    if direc > 0:
        tagged = el - 0.40 <= b["l"][i] <= max(ema, eh) + 0.15
        if tagged and sl > 0 and b["color"][i] == "green" and c > ema and c > vwap:
            return "CALL"
    else:
        tagged = min(ema, el) - 0.15 <= b["h"][i] <= eh + 0.40
        if tagged and sl < 0 and b["color"][i] == "red" and c < ema and c < vwap:
            return "PUT"
    return None


def trend_side(b, i, name):
    lab, direc = g.day_label(b, i)
    if lab != "TREND":
        return None
    tt = b["t"][i].time()
    if not (WINDOW_LO <= tt <= WINDOW_HI):
        return None
    if name == "retest":
        side = g.baseline_side(b, i)
    else:
        side = pullback_side(b, i)
    if side == "CALL" and direc < 0:
        return None
    if side == "PUT" and direc > 0:
        return None
    return side


def resolve_ride(b, i, side, dist, latch_pct, buf, hard_tp, time_n):
    """QQQ stop, then structure or a latched giveback. time_n None rides to the last bar."""
    sign = 1 if side == "CALL" else -1
    entry = b["c"][i]
    stop_lvl = entry - sign * dist
    arm_qqq = latch_pct * PREM / DELTA
    arm_lvl = entry + sign * arm_qqq
    tp_lvl = None if not hard_tp else entry + sign * (hard_tp * PREM / DELTA)
    armed = False
    last = len(b["c"]) - 1
    k = 0
    while True:
        k += 1
        j = i + k
        if j > last:
            j = last
            fill = b["c"][j]
            return fill, "eod", j, sign * (fill - entry) * DELTA * 100.0
        o, h, l, c = b["o"][j], b["h"][j], b["l"][j], b["c"][j]
        if (sign == 1 and o < stop_lvl) or (sign == -1 and o > stop_lvl):
            return o, "stop", j, sign * (o - entry) * DELTA * 100.0
        if armed and ((sign == 1 and o <= arm_lvl) or (sign == -1 and o >= arm_lvl)):
            fill = o if (sign == 1 and o < arm_lvl) or (sign == -1 and o > arm_lvl) else arm_lvl
            return fill, "latch", j, sign * (fill - entry) * DELTA * 100.0
        if tp_lvl is not None and ((sign == 1 and o >= tp_lvl) or (sign == -1 and o <= tp_lvl)):
            return tp_lvl, "target", j, sign * (tp_lvl - entry) * DELTA * 100.0
        if (sign == 1 and l < stop_lvl) or (sign == -1 and h > stop_lvl):
            return stop_lvl, "stop", j, sign * (stop_lvl - entry) * DELTA * 100.0
        if tp_lvl is not None and ((sign == 1 and h >= tp_lvl) or (sign == -1 and l <= tp_lvl)):
            return tp_lvl, "target", j, sign * (tp_lvl - entry) * DELTA * 100.0
        reached = (h >= arm_lvl) if sign == 1 else (l <= arm_lvl)
        if armed:
            gave = (l <= arm_lvl) if sign == 1 else (h >= arm_lvl)
            if gave:
                return arm_lvl, "latch", j, sign * (arm_lvl - entry) * DELTA * 100.0
        elif reached:
            armed = True
        against = (b["color"][j] == "red") if sign == 1 else (b["color"][j] == "green")
        through = (b["ha_c"][j] < b["ema"][j] - buf) if sign == 1 else (b["ha_c"][j] > b["ema"][j] + buf)
        if armed and against:
            return c, "momentum", j, sign * (c - entry) * DELTA * 100.0
        if not armed and through:
            return c, "ema", j, sign * (c - entry) * DELTA * 100.0
        if time_n is not None and k >= time_n:
            return c, "time", j, sign * (c - entry) * DELTA * 100.0


def simulate_trend(b, entry_name, stop_mode, stop_fixed, latch_pct, buf, hard_tp, time_n):
    trades = []
    pos_until = -1
    cool_until = -1
    i, n = 0, len(b["c"])
    while i < n:
        if i <= pos_until or i < cool_until:
            i += 1
            continue
        side = trend_side(b, i, entry_name)
        if side is None:
            i += 1
            continue
        dist = g.stop_dist_for(b, i, side, stop_mode, stop_fixed)
        if dist is None:
            i += 1
            continue
        _fill, reason, j, pnl = resolve_ride(b, i, side, dist, latch_pct, buf, hard_tp, time_n)
        trades.append({
            "t": b["t"][i], "side": side, "entry": b["c"][i], "pnl": pnl,
            "reason": reason, "dist": dist, "exit_t": b["t"][j],
        })
        pos_until = j
        cool_until = j + 2
        i = j + 1
    return trades


def old_style(b, entry_name):
    """The exits the paper trend book uses today: $0.30, +12%, 5 minutes."""
    trades = []
    pos_until = -1
    cool_until = -1
    i, n = 0, len(b["c"])
    spec_tp = 0.12 * PREM / DELTA
    while i < n:
        if i <= pos_until or i < cool_until:
            i += 1
            continue
        side = trend_side(b, i, entry_name)
        if side is None:
            i += 1
            continue
        fill, reason, j, pnl = g.resolve(b, i, side, 0.30, spec_tp, 5, False, DELTA)
        trades.append({"t": b["t"][i], "side": side, "entry": b["c"][i], "pnl": pnl,
                       "reason": reason, "dist": 0.30, "exit_t": b["t"][j]})
        pos_until = j
        cool_until = j + 2
        i = j + 1
    return trades


def load_days():
    raw = g.fetch("2026-10-27")
    grouped = defaultdict(list)
    for bar in raw:
        grouped[bar["t"].date()].append(bar)
    dates = sorted(grouped)
    hold = set(dates[-5:])
    days = []
    for d in dates:
        days.append(("hold" if d in hold else "train", g.prep(grouped[d]), d))
    return days


def describe(cfg):
    entry, mode, fixed, latch, buf, hard, time_n = cfg
    stop = f"stop {fixed:.2f}" if mode == "fixed" else f"stop {mode}"
    tp = "no hard tp" if not hard else f"tp {hard:.0%}"
    clock = "no clock" if time_n is None else f"{time_n}m"
    return f"{entry} | {stop} | latch {latch:.0%} | ema buf {buf:.2f} | {tp} | {clock}"


def run():
    days = load_days()
    print(f"sessions {len(days)} last {days[-1][1]['t'][-1].isoformat()} "
          f"holdout {', '.join(str(d) for _f, _b, d in days if _f == 'hold')}")
    b = days[-1][1]
    if str(days[-1][2]) == "2026-10-26":
        print("\n== 10/26 09:00-10:15 ==")
        for i, ts in enumerate(b["t"]):
            hm = ts.strftime("%H:%M")
            if not ("09:00" <= hm <= "10:15"):
                continue
            lab, direc = g.day_label(b, i)
            if hm in ("09:00", "09:30", "10:00", "10:07") or lab == "TREND" or trend_side(b, i, "retest") or trend_side(b, i, "pullback"):
                print(f"{hm} c{b['c'][i]:.2f} ema{b['ema'][i]:.2f} vw{b['vwap'][i]:.2f} "
                      f"{b['color'][i][:1]} {lab}{direc:+d} sl5{b['slope5'][i]:+.2f} "
                      f"retest={trend_side(b, i, 'retest') or '-'} pull={trend_side(b, i, 'pullback') or '-'}")

    specs = []
    for entry in ("retest", "pullback"):
        for mode, fixeds in (("fixed", (0.30, 0.45, 0.60)), ("ema", (0.0,))):
            for fixed in fixeds:
                for latch in (0.15, 0.20, 0.30):
                    for buf in (0.0, 0.15):
                        for hard in (None, 0.20):
                            for time_n in (None, 5, 30):
                                specs.append((entry, mode, fixed, latch, buf, hard, time_n))
    print(f"\nspecs {len(specs)}")

    def collect(cfg, which):
        entry, mode, fixed, latch, buf, hard, time_n = cfg
        out = []
        for flag, bar, _d in days:
            if flag != which and which != "all":
                continue
            if which == "all" or flag == which:
                out += simulate_trend(bar, entry, mode, fixed, latch, buf, hard, time_n)
        return out

    ranked = []
    for cfg in specs:
        s = g.summarize(collect(cfg, "train"))
        ranked.append((s["wr"] if s["n"] else -1, s["net"], cfg, s))
    ranked.sort(key=lambda r: (-r[0], -r[1]))
    print("\n== top 8 train WR then net, n>=8 ==")
    shown = 0
    for _wr, _net, cfg, s in ranked:
        if s["n"] < 8:
            continue
        h = g.summarize(collect(cfg, "hold"))
        full = g.summarize(collect(cfg, "all"))
        print(f"TRAIN {g.wr(s):16} net {s['net']:+8.2f} aw {g.money(s['avg_win'])} al {g.money(s['avg_loss'])} "
              f"| HOLD {g.wr(h):16} net {h['net']:+8.2f} | FULL {g.wr(full):16} net {full['net']:+8.2f} | {describe(cfg)}")
        shown += 1
        if shown >= 8:
            break
    print("\n== best train net, n>=8 ==")
    best = max((r for r in ranked if r[3]["n"] >= 8), key=lambda r: (r[1], r[0]))
    h = g.summarize(collect(best[2], "hold"))
    print(f"TRAIN {g.wr(best[3])} net {best[3]['net']:+.2f} HOLD {g.wr(h)} net {h['net']:+.2f} {describe(best[2])}")

    print("\n== current paper exits on the same entries ==")
    for entry in ("retest", "pullback"):
        def rows(which, entry=entry):
            out = []
            for flag, bar, _d in days:
                if which != "all" and flag != which:
                    continue
                out += old_style(bar, entry)
            return out
        s, h = g.summarize(rows("train")), g.summarize(rows("hold"))
        full = g.summarize(rows("all"))
        print(f"{entry} 0.30/12%/5m TRAIN {g.wr(s)} net {s['net']:+.2f} HOLD {g.wr(h)} net {h['net']:+.2f} "
              f"FULL {g.wr(full)} net {full['net']:+.2f}")

    # The rule-shaped cell: pullback and retest, latch 20%, ema buf 0.15, no hard tp, no clock, stop 0.45 and 0.60 and ema.
    print("\n== rule-shaped cells ==")
    for cfg in (
        ("retest", "fixed", 0.30, 0.20, 0.0, None, None),
        ("pullback", "fixed", 0.30, 0.20, 0.0, None, None),
        ("retest", "fixed", 0.30, 0.20, 0.15, None, None),
        ("pullback", "fixed", 0.45, 0.20, 0.15, None, None),
        ("pullback", "fixed", 0.60, 0.20, 0.15, None, None),
        ("pullback", "ema", 0.0, 0.20, 0.15, None, None),
        ("retest", "fixed", 0.45, 0.20, 0.15, None, None),
        ("retest", "fixed", 0.60, 0.20, 0.15, None, None),
        ("retest", "ema", 0.0, 0.20, 0.15, None, None),
        ("pullback", "fixed", 0.45, 0.20, 0.0, None, None),
        ("retest", "fixed", 0.45, 0.20, 0.0, None, None),
    ):
        s, h = g.summarize(collect(cfg, "train")), g.summarize(collect(cfg, "hold"))
        full = g.summarize(collect(cfg, "all"))
        print(f"TRAIN {g.wr(s):16} net {s['net']:+8.2f} | HOLD {g.wr(h):16} net {h['net']:+8.2f} "
              f"| FULL {g.wr(full):16} net {full['net']:+8.2f} | {describe(cfg)}")

    print("\n== 10/26 trades for pullback latch 20% stop 0.45 buf 0.15 ==")
    today = [d for d in days if str(d[2]) == "2026-10-26"]
    if today:
        flag, bar, _d = today[0]
        for t in simulate_trend(bar, "pullback", "fixed", 0.45, 0.20, 0.15, None, None):
            print(f"{t['t'].strftime('%H:%M')} {t['side']} {t['entry']:.2f} -> {t['exit_t'].strftime('%H:%M')} "
                  f"{t['reason']} pnl {t['pnl']:+.2f} dist {t['dist']:.2f}")
        print("-- retest same exit --")
        for t in simulate_trend(bar, "retest", "fixed", 0.45, 0.20, 0.15, None, None):
            print(f"{t['t'].strftime('%H:%M')} {t['side']} {t['entry']:.2f} -> {t['exit_t'].strftime('%H:%M')} "
                  f"{t['reason']} pnl {t['pnl']:+.2f}")
        print("-- retest old 0.30/12%/5m --")
        for t in old_style(bar, "retest"):
            print(f"{t['t'].strftime('%H:%M')} {t['side']} {t['entry']:.2f} -> {t['exit_t'].strftime('%H:%M')} "
                  f"{t['reason']} pnl {t['pnl']:+.2f}")
        print("-- shipped default: retest stop 0.30 latch 20% buf 0 no hard tp no clock --")
        for t in simulate_trend(bar, "retest", "fixed", 0.30, 0.20, 0.0, None, None):
            print(f"{t['t'].strftime('%H:%M')} {t['side']} {t['entry']:.2f} -> {t['exit_t'].strftime('%H:%M')} "
                  f"{t['reason']} pnl {t['pnl']:+.2f}")

    cleared = 0
    for _wr, _net, cfg, s in ranked:
        if s["n"] < 20 or s["wr"] < 0.70 or s["net"] <= 0:
            continue
        h = g.summarize(collect(cfg, "hold"))
        cleared += 1
        print(f"ELIGIBLE TRAIN {g.wr(s)} net {s['net']:+.2f} HOLD {g.wr(h)} net {h['net']:+.2f} {describe(cfg)}")
    print(f"train n>=20 wr>=70 net>0: {cleared}")


if __name__ == "__main__":
    run()
