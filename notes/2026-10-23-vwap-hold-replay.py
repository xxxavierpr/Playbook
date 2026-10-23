#!/usr/bin/env python3
"""Replay the 2026-10-23 VWAP-hold entry note. Research only. Not imported by the trader.

Yahoo 1-minute QQQ, same source as PR #9. Prints the ranked table in
notes/2026-10-23-vwap-hold-entry.md. The sample is cut at 2026-10-23 09:32 CT,
the last complete bar when the note was written.
"""
from __future__ import annotations

import json
import math
import urllib.request
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
UNTIL = datetime(2026, 10, 23, 9, 32, tzinfo=CT)
TOUCH = 0.15
ENTRY_END = dtime(12, 0)


def fetch() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0"}
    start = datetime(2026, 9, 29, tzinfo=timezone.utc)
    end = datetime(2026, 10, 24, tzinfo=timezone.utc)
    bars = []
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
            if when > UNTIL:
                continue
            bars.append({"t": when, "o": o, "h": h, "l": l, "c": c, "v": quote["volume"][i] or 0})
        cur = nxt
    bars.sort(key=lambda b: b["t"])
    dedup = []
    for b in bars:
        if dedup and dedup[-1]["t"] == b["t"]:
            continue
        dedup.append(b)
    return dedup


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
    color = []
    for i in range(n):
        ha_c[i] = (o[i] + h[i] + l[i] + c[i]) / 4.0
        ha_o[i] = (o[i] + c[i]) / 2.0 if i == 0 else (ha_o[i - 1] + ha_c[i - 1]) / 2.0
        color.append("green" if ha_c[i] > ha_o[i] else ("red" if ha_c[i] < ha_o[i] else "doji"))
    vwap = [0.0] * n
    acc = 0.0
    for i in range(n):
        acc += (h[i] + l[i] + c[i]) / 3.0
        vwap[i] = acc / (i + 1)
    reg = ["WARMUP"] * n
    slope = [float("nan")] * n
    for i in range(19, n):
        crosses, last = 0, 0
        for j in range(i - 19, i + 1):
            sg = 1 if c[j] > ema_c[j] else (-1 if c[j] < ema_c[j] else 0)
            if sg == 0:
                continue
            if last and sg != last:
                crosses += 1
            last = sg
        reg[i] = "CHOPPY" if crosses >= 4 else "TRENDING"
        slope[i] = ema_c[i] - ema_c[i - 5]
    return {
        "t": [b["t"] for b in day], "o": o, "h": h, "l": l, "c": c,
        "ema": ema_c, "eh": ema_h, "el": ema_l, "vwap": vwap,
        "color": color, "ha_c": ha_c, "reg": reg, "slope": slope,
    }


def baseline_side(b, i, require_beyond=True):
    if b["reg"][i] != "TRENDING" or math.isnan(b["slope"][i]) or i < 3:
        return None
    prior = b["color"][i - 3:i]
    c, ema, eh, el = b["c"][i], b["ema"][i], b["eh"][i], b["el"][i]
    vwap, hc, sl = b["vwap"][i], b["ha_c"][i], b["slope"][i]
    green, red = b["color"][i] == "green", b["color"][i] == "red"
    near_c = min(abs(hc - ema), abs(hc - eh)) <= TOUCH
    near_p = min(abs(hc - ema), abs(hc - el)) <= TOUCH
    if c > vwap and sl > 0 and green and "red" in prior and near_c and (c > ema or not require_beyond):
        return "CALL"
    if c < vwap and sl < 0 and red and "green" in prior and near_p and (c < ema or not require_beyond):
        return "PUT"
    return None


def in_window(ts, end=ENTRY_END):
    return dtime(8, 45) <= ts.time() <= end


def resolve(b, i, side, tp_pts):
    sign = 1 if side == "CALL" else -1
    entry = b["c"][i]
    stop_lvl = entry - sign * 0.30
    tp_lvl = entry + sign * tp_pts
    n = len(b["c"])
    for k in range(1, 6):
        j = i + k
        if j >= n:
            j = n - 1
            fill = b["c"][j]
            return fill, "eod", j, sign * (fill - entry) * 30.0
        o, h, l, c = b["o"][j], b["h"][j], b["l"][j], b["c"][j]
        if (sign == 1 and o >= tp_lvl) or (sign == -1 and o <= tp_lvl):
            return tp_lvl, "target", j, sign * (tp_lvl - entry) * 30.0
        if (sign == 1 and o < stop_lvl) or (sign == -1 and o > stop_lvl):
            return o, "stop", j, sign * (o - entry) * 30.0
        stop_hit = (l < stop_lvl) if sign == 1 else (h > stop_lvl)
        tgt_hit = (h >= tp_lvl) if sign == 1 else (l <= tp_lvl)
        if stop_hit:
            return stop_lvl, "stop", j, sign * (stop_lvl - entry) * 30.0
        if tgt_hit:
            return tp_lvl, "target", j, sign * (tp_lvl - entry) * 30.0
        if k == 5:
            return c, "time", j, sign * (c - entry) * 30.0
    raise RuntimeError("no exit")


def vwap_held_recent(b, i, side, lookback):
    tag = None
    for j in range(max(0, i - lookback), i + 1):
        if side == "CALL" and b["l"][j] <= b["vwap"][j] + TOUCH:
            tag = j
        if side == "PUT" and b["h"][j] >= b["vwap"][j] - TOUCH:
            tag = j
    if tag is None:
        return False
    for j in range(tag, i + 1):
        if side == "CALL" and b["c"][j] < b["vwap"][j] - 0.02:
            return False
        if side == "PUT" and b["c"][j] > b["vwap"][j] + 0.02:
            return False
    return True


def run_baseline(b, tp, end=ENTRY_END, cooldown=1, require_beyond=True, dist_max=None, vwap_hold_lb=None):
    trades = []
    pos_until = -1
    cool_until = -1
    i, n = 0, len(b["c"])
    while i < n:
        if i <= pos_until:
            i += 1
            continue
        ts = b["t"][i]
        if not in_window(ts, end) or i < cool_until:
            i += 1
            continue
        side = baseline_side(b, i, require_beyond=require_beyond)
        if side is None:
            i += 1
            continue
        if dist_max is not None and abs(b["ema"][i] - b["vwap"][i]) > dist_max + 1e-9:
            i += 1
            continue
        if vwap_hold_lb is not None and not vwap_held_recent(b, i, side, vwap_hold_lb):
            i += 1
            continue
        _fill, reason, j, pnl = resolve(b, i, side, tp)
        trades.append({
            "t": ts, "side": side, "entry": b["c"][i], "pnl": pnl, "reason": reason,
            "ema": b["ema"][i], "vwap": b["vwap"][i],
        })
        pos_until = j
        cool_until = j + 1 + cooldown
        i = j + 1
    return trades


def run_vwap_after_fail(b, tp, require_ema_reclaim=False, require_trend=False,
                        fail_bars=15, hold_bars=20, tag_pad=0.15, pierce_cancel=1.0, cooldown=1):
    """Skip the EMA20 retest. After it closes back through EMA20, buy the VWAP hold.

    Confirmation is tested before a new EMA20 retest re-arms the skip, so a bar
    that both holds VWAP and retouches EMA20 is an entry, not another skip.
    """
    trades = []
    pos_until = -1
    cool_until = -1
    setup = None
    i, n = 0, len(b["c"])
    while i < n:
        ts = b["t"][i]
        if i <= pos_until:
            setup = None
            i += 1
            continue
        if setup and i > setup["sig"]:
            side = setup["side"]
            if setup["phase"] == "wait_fail" and i - setup["sig"] > fail_bars:
                setup = None
            elif setup and setup["phase"] == "wait_hold" and i - setup["fail"] > hold_bars:
                setup = None
            elif setup is not None:
                if side == "CALL" and b["c"][i] < b["vwap"][i] - pierce_cancel:
                    setup = None
                elif side == "PUT" and b["c"][i] > b["vwap"][i] + pierce_cancel:
                    setup = None
        entered = None
        if setup and i > setup["sig"] and in_window(ts) and i >= cool_until:
            side = setup["side"]
            if setup["phase"] == "wait_fail":
                failed = (side == "CALL" and b["c"][i] < b["ema"][i]) or (side == "PUT" and b["c"][i] > b["ema"][i])
                if failed:
                    setup["phase"] = "wait_hold"
                    setup["fail"] = i
                    setup["tag"] = None
            if setup and setup["phase"] == "wait_hold":
                tagged = (
                    (side == "CALL" and b["l"][i] <= b["vwap"][i] + tag_pad)
                    or (side == "PUT" and b["h"][i] >= b["vwap"][i] - tag_pad)
                )
                if tagged:
                    setup["tag"] = i
                tag = setup["tag"]
                fresh = tag is not None and i - tag <= 5
                reclaim = (
                    (side == "CALL" and b["c"][i] > b["vwap"][i] and b["color"][i] == "green")
                    or (side == "PUT" and b["c"][i] < b["vwap"][i] and b["color"][i] == "red")
                )
                ema_ok = True
                if require_ema_reclaim:
                    ema_ok = (side == "CALL" and b["c"][i] > b["ema"][i]) or (side == "PUT" and b["c"][i] < b["ema"][i])
                trend_ok = True
                if require_trend:
                    trend_ok = b["reg"][i] == "TRENDING" and (
                        (side == "CALL" and b["slope"][i] > 0) or (side == "PUT" and b["slope"][i] < 0)
                    )
                if fresh and reclaim and ema_ok and trend_ok and i != setup["fail"]:
                    _fill, reason, j, pnl = resolve(b, i, side, tp)
                    trades.append({"t": ts, "side": side, "entry": b["c"][i], "pnl": pnl, "reason": reason,
                                   "ema": b["ema"][i], "vwap": b["vwap"][i]})
                    pos_until = j
                    cool_until = j + 1 + cooldown
                    setup = None
                    entered = j
        if entered is not None:
            i = entered + 1
            continue
        if in_window(ts) and i >= cool_until:
            side = baseline_side(b, i, require_beyond=True)
            if side:
                setup = {"side": side, "sig": i, "phase": "wait_fail", "fail": None, "tag": None}
        i += 1
    return trades


def summarize(trades):
    n = len(trades)
    wins = [t["pnl"] for t in trades if t["pnl"] > 1e-9]
    losses = [t["pnl"] for t in trades if t["pnl"] <= 1e-9]
    gross = sum(t["pnl"] for t in trades)
    return {
        "n": n,
        "wins": len(wins),
        "wr": (len(wins) / n) if n else float("nan"),
        "avg_win": (sum(wins) / len(wins)) if wins else float("nan"),
        "avg_loss": (sum(losses) / len(losses)) if losses else float("nan"),
        "gross": gross,
        "net": gross - 2 * n,
    }


def money(x):
    if isinstance(x, float) and math.isnan(x):
        return "—"
    return f"{x:+.2f}"


def main():
    raw = fetch()
    days = []
    bucket = None
    for bar in raw:
        if bucket is None or bucket[0] != bar["t"].date():
            bucket = (bar["t"].date(), [])
            days.append(bucket)
        bucket[1].append(bar)
    prepared = [(d, prep(bars)) for d, bars in days]
    print(f"sessions {len(prepared)} bars {sum(len(b['c']) for _, b in prepared)} "
          f"last {prepared[-1][1]['t'][-1].isoformat()}")

    # PR #9 check: full day through 2026-10-22 11:49 CT, note rule, no cooldown.
    cal = []
    for d, b in prepared:
        if str(d) > "2026-10-22":
            continue
        if str(d) == "2026-10-22":
            m = max(k for k, ts in enumerate(b["t"]) if ts.strftime("%H:%M") <= "11:49") + 1
            b = {k: v[:m] for k, v in b.items()}
        cal += run_baseline(b, 0.12, end=dtime(14, 30), cooldown=0, require_beyond=False)
    s = summarize(cal)
    t21 = [t for t in cal if str(t["t"].date()) == "2026-10-21"]
    print(f"calibration n={s['n']} wins={s['wins']} wr={s['wr']*100:.1f}% "
          f"gross={s['gross']:+.2f} day1021={sum(t['pnl'] for t in t21):+.2f}")
    print("10/21", [(t["t"].strftime("%H:%M"), t["side"][0], round(t["pnl"], 2), t["reason"]) for t in t21])

    specs = [
        ("a", "+12%", "baseline EMA20 retest", lambda b, tp: run_baseline(b, tp), 0.12),
        ("d", "+20%", "retest only if |EMA-VWAP| <= $0.50", lambda b, tp: run_baseline(b, tp, dist_max=0.50), 0.20),
        ("d", "+12%", "retest only if |EMA-VWAP| <= $0.50", lambda b, tp: run_baseline(b, tp, dist_max=0.50), 0.12),
        ("a", "+20%", "baseline EMA20 retest", lambda b, tp: run_baseline(b, tp), 0.20),
        ("b", "+12%", "VWAP hold after EMA20 fails", lambda b, tp: run_vwap_after_fail(b, tp), 0.12),
        ("b", "+20%", "VWAP hold after EMA20 fails", lambda b, tp: run_vwap_after_fail(b, tp), 0.20),
        ("b2", "+12%", "VWAP hold and close back through EMA20",
         lambda b, tp: run_vwap_after_fail(b, tp, require_ema_reclaim=True), 0.12),
        ("b2", "+20%", "VWAP hold and close back through EMA20",
         lambda b, tp: run_vwap_after_fail(b, tp, require_ema_reclaim=True), 0.20),
        ("c", "+12%", "both EMA20 and VWAP held", lambda b, tp: run_baseline(b, tp, vwap_hold_lb=10), 0.12),
        ("c", "+20%", "both EMA20 and VWAP held", lambda b, tp: run_baseline(b, tp, vwap_hold_lb=10), 0.20),
        ("b3", "+12%", "VWAP hold, trend filter still on",
         lambda b, tp: run_vwap_after_fail(b, tp, require_trend=True), 0.12),
    ]
    rows = []
    for key, tp_label, name, fn, tp in specs:
        tr = []
        for _d, b in prepared:
            tr += fn(b, tp)
        s = summarize(tr)
        today = [t for t in tr if str(t["t"].date()) == "2026-10-23"]
        took = any(t["t"].strftime("%H:%M") == "09:12" for t in today)
        rows.append((s["wr"], s["net"], key, tp_label, name, s, took, today))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    print(f"{'rk':>2} {'id':<3} {'tp':<5} {'n':>4} {'wr':>16} {'aw':>7} {'al':>7} {'gross':>8} {'net':>8} 9:13")
    for i, r in enumerate(rows, 1):
        s = r[5]
        wr = f"{s['wr']*100:.1f}% ({s['wins']}/{s['n']})"
        print(f"{i:2} {r[2]:<3} {r[3]:<5} {s['n']:4} {wr:>16} {money(s['avg_win']):>7} {money(s['avg_loss']):>7} "
              f"{s['gross']:+8.2f} {s['net']:+8.2f} {'taken' if r[6] else 'skipped'} "
              f"{[(t['t'].strftime('%H:%M'), t['side'], round(t['pnl'], 2)) for t in r[7]]}")

    for dist in (0.40, 0.50, 0.75, 1.00):
        for tp in (0.12, 0.20):
            tr = []
            for _d, b in prepared:
                tr += run_baseline(b, tp, dist_max=dist)
            s = summarize(tr)
            today = any(str(t["t"].date()) == "2026-10-23" and t["t"].strftime("%H:%M") == "09:12" for t in tr)
            print(f"dist {dist:.2f} tp {tp:.2f} n={s['n']} wr={s['wr']*100:.1f}% gross={s['gross']:+.2f} "
                  f"net={s['net']:+.2f} took912={today}")


if __name__ == "__main__":
    main()
