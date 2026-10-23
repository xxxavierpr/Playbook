"""Paper day-regime switch. Live stays on the old path."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import trader
from trader import CT, Quote, Trader, classify_day_regime, fade_stop_dist, vwap_fade_side


class FakeBroker:
    def __init__(self):
        self.placed = []
        self.bid = 0.48
        self.ask = 0.50

    def contracts(self, expiry, side, spot):
        strike = round(spot + 2, 2) if side == "CALL" else round(spot - 2, 2)
        return [{"symbol": f"QQQ{side}{strike}", "strike": strike}]

    def quotes(self, expiry, wanted):
        return {sym: Quote(self.bid, self.ask, "test", True) for sym in wanted}

    def preview(self, order):
        return 200, {"status": "ok"}

    def place(self, order):
        self.placed.append(order)
        raise AssertionError("paper test placed a live order")

    def cancel(self, cid):
        return {"status": "CANCELLED"}

    def order_status(self, cid):
        return {"status": "CANCELLED"}

    def position_mark(self, *args):
        return None


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def override(**extra):
    base = {
        "regime_mode": True,
        "entry_mode": "retest_trend",
        "retest_trend_only": True,
        "retest_near_only": True,
        "tp_pct": 0.12,
        "tp_min_hold_s": 10,
        "qqq_stop": 0.30,
        "time_exit_min": 5,
        "reentry_cooldown_bars": 1,
        "max_vwap_dist": 6.0,
        "paper_min_ask": 0.30,
        "paper_max_ask": 0.60,
        "paper_max_spread": 0.05,
        "max_buys": 12,
    }
    base.update(extra)
    return base


def make_trader(tmp, day, live=False, ov=None, echo=False):
    state = Path(tmp) / ("trader_state.json" if live else "trader_state.dryrun.json")
    log = Path(tmp) / "trader.dryrun.log"
    clock = Clock(datetime(day.year, day.month, day.day, 8, 30, tzinfo=CT))
    tr = Trader(FakeBroker(), trader.Logger(log, "LIVE" if live else "DRYRUN", echo=echo),
                live=live, state_path=state, kill_path=Path(tmp) / "KILL", clock=clock, signals_log=None)
    if ov is not None and not live:
        tr.state["override"] = ov
        tr.save()
    return tr, log, clock


def bar_at(t, close, **kw):
    ema = kw.get("ema", close - 0.05)
    return {
        "t": t.isoformat(),
        "open": close,
        "high": kw.get("high", close + 0.05),
        "low": kw.get("low", close - 0.05),
        "close": close,
        "ema20": ema,
        "ema_high": kw.get("ema_high", ema + 0.10),
        "ema_low": kw.get("ema_low", ema - 0.10),
        "vwap": kw.get("vwap", close - 1.0),
        "ha_color": kw.get("color", "green"),
        "ha_close": kw.get("ha_close", ema),
        "ha_open": ema - 0.02,
        "rsi14": kw.get("rsi", 50),
        "macd_hist": 0.01,
        "signal": "NONE",
    }


def feed(tr, clock, rec):
    bt = datetime.fromisoformat(rec["t"]).astimezone(CT)
    clock.t = bt + timedelta(seconds=70)
    tr.on_bar(rec, clock.t)


def read_events(log):
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


class ClassifyTests(unittest.TestCase):
    def test_warmup_before_0900_and_before_21_bars(self):
        hist = [(100 + i * 0.1, 100 + i * 0.1 - 0.05, 99 + i * 0.1) for i in range(21)]
        self.assertEqual(classify_day_regime(hist, 100, 99, trader.dtime(8, 50))["label"], "WARMUP")
        self.assertEqual(classify_day_regime(hist[:20], 100, 99, trader.dtime(9, 0))["label"], "WARMUP")

    def test_trend_chop_mixed_match_the_note(self):
        trend = [(100 + i * 0.05, 100 + i * 0.05 - 0.05, 99 + i * 0.05) for i in range(21)]
        lab = classify_day_regime(trend, or_hi=100.2, or_lo=99.5, when=trader.dtime(9, 0))
        self.assertEqual(lab["label"], "TREND")
        self.assertEqual(lab["direction"], 1)
        self.assertLessEqual(lab["crosses"], 2)
        self.assertGreaterEqual(abs(lab["slope15"]), 0.40)

        chop = []
        for i in range(21):
            close = 100.2 if i % 2 == 0 else 99.8
            chop.append((close, 100.0, 100.0))
        lab = classify_day_regime(chop, None, None, trader.dtime(9, 30))
        self.assertEqual(lab["label"], "CHOP")
        self.assertGreaterEqual(lab["crosses"], 4)

        mixed = []
        for i in range(21):
            ema = 100 + i * 0.05
            # last 20 bars: 5 up, 5 down, 5 up, 5 down -> 3 crosses
            slot = (i - 1) if i else 0
            up = slot < 5 or 10 <= slot < 15
            close = ema + (0.10 if up else -0.10)
            mixed.append((close, ema, ema - 1.0))
        lab = classify_day_regime(mixed, or_hi=100, or_lo=99, when=trader.dtime(9, 30))
        self.assertEqual(lab["label"], "MIXED")
        self.assertEqual(lab["crosses"], 3)

    def test_fade_geometry(self):
        self.assertEqual(vwap_fade_side("red", 704.84, 704.15, 704.16, 704.29), "PUT")
        self.assertEqual(vwap_fade_side("green", 704.97, 704.00, 704.87, 704.27), "CALL")
        self.assertIsNone(vwap_fade_side("green", 705.0, 704.80, 704.90, 704.90))
        self.assertAlmostEqual(fade_stop_dist("PUT", 704.16, 704.84, 704.15), 0.73, places=2)
        self.assertAlmostEqual(fade_stop_dist("CALL", 704.87, 704.97, 704.00), 0.92, places=2)
        self.assertEqual(fade_stop_dist("CALL", 100, 100, 99.99), 0.15)
        self.assertEqual(fade_stop_dist("PUT", 100, 102, 99), 1.0)


class StateTests(unittest.TestCase):
    def test_paper_load_keeps_override_across_a_new_day_and_live_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            friday = {
                "day": "2026-10-23", "buys": 2, "attempts": 2, "position": {"side": "CALL"},
                "pending_buy": None, "done": True, "override": override(), "closed": [1],
            }
            for name in ("trader_state.dryrun.json", "trader_state.json"):
                Path(tmp, name).write_text(json.dumps(friday))
            paper, _, _ = make_trader(tmp, datetime(2026, 10, 26, tzinfo=CT).date(), live=False)
            self.assertEqual(paper.state["day"], "2026-10-26")
            self.assertEqual(paper.state["buys"], 0)
            self.assertFalse(paper.state["done"])
            self.assertIsNone(paper.state["position"])
            self.assertTrue(paper.state["override"]["regime_mode"])
            live, _, _ = make_trader(tmp, datetime(2026, 10, 26, tzinfo=CT).date(), live=True)
            self.assertEqual(live.state["day"], "2026-10-26")
            self.assertNotIn("override", live.state)
            self.assertNotIn("day_regime_hist", live.state)
            self.assertFalse(live.regime_mode_on())
            self.assertIsNone(live.paper_mode("regime_mode"))

    def test_roll_day_carries_override_only_for_paper(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = datetime(2026, 10, 23, tzinfo=CT).date()
            paper, _, clock = make_trader(tmp, day, live=False, ov=override())
            paper.state["day"] = "2026-10-23"
            paper.state["buys"] = 4
            clock.t = datetime(2026, 10, 26, 8, 30, tzinfo=CT)
            paper.roll_day(clock.t)
            self.assertEqual(paper.state["day"], "2026-10-26")
            self.assertEqual(paper.state["buys"], 0)
            self.assertTrue(paper.state["override"]["regime_mode"])

            live_state = Path(tmp) / "live.json"
            live_state.write_text(json.dumps({"day": "2026-10-23", "override": override(), "buys": 1}))
            # rebuild with that file as today's file so _load returns it, then roll
            clock2 = Clock(datetime(2026, 10, 23, 15, 0, tzinfo=CT))
            live = Trader(FakeBroker(), trader.Logger(Path(tmp) / "live.log", "LIVE", echo=False),
                          live=True, state_path=live_state, kill_path=Path(tmp) / "KILL2",
                          clock=clock2, signals_log=None)
            self.assertIn("override", live.state)
            live.roll_day(datetime(2026, 10, 26, 8, 30, tzinfo=CT))
            self.assertNotIn("override", live.state)
            saved = json.loads(live_state.read_text())
            self.assertNotIn("override", saved)
            self.assertNotIn("day_regime_hist", saved)

    def test_done_stops_paper_entries_once_max_buys_is_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = datetime(2026, 10, 26, tzinfo=CT)
            paper, log, clock = make_trader(tmp, day.date(), ov=override(max_buys=2))
            paper.state["position"] = {
                "side": "CALL", "strike": 100, "symbol": "X", "expiry": "2026-10-26",
                "fill": 0.50, "buy_cid": "b", "stop": 0.25, "stop_cid": None,
                "simulated": True, "peak_gain": 0.0, "profit_mode": False,
                "opened": day.isoformat(), "entry_source": "retest_trend",
            }
            paper.state["buys"] = 1
            clock.t = day.replace(hour=9, minute=15)
            paper._close("stop", 0.40, "test")
            self.assertFalse(paper.state["done"])
            paper.state["position"] = dict(paper.state["closed"][-1])
            paper.state["buys"] = 2
            paper._close("stop", 0.40, "test")
            self.assertTrue(paper.state["done"])
            rec = bar_at(day.replace(hour=9, minute=20), 705.0)
            why = paper.entry_block_reason({**rec, "signal": "CALL"}, clock.t)
            self.assertEqual(why, "done")

            live_state = Path(tmp) / "live.json"
            live_state.write_text(json.dumps({"day": "2026-10-26", "buys": 0, "attempts": 0,
                                              "position": None, "pending_buy": None, "done": True,
                                              "closed": [], "override": {"max_buys": 5}}))
            live = Trader(FakeBroker(), trader.Logger(Path(tmp) / "l.log", "LIVE", echo=False),
                          live=True, state_path=live_state, kill_path=Path(tmp) / "no-kill",
                          clock=Clock(day.replace(hour=9, minute=20)), signals_log=None)
            why = live.entry_block_reason({**rec, "signal": "CALL"}, day.replace(hour=9, minute=21))
            self.assertNotEqual(why, "done")


class SwitchTests(unittest.TestCase):
    def test_trend_retest_uses_pr8_exits_and_logs_the_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = datetime(2026, 10, 26, 8, 30, tzinfo=CT)
            tr, log, clock = make_trader(tmp, day.date(), ov=override())
            for i in range(31):
                t = day + timedelta(minutes=i)
                close = 700 + i * 0.10
                color = "red" if i == 28 else "green"
                feed(tr, clock, bar_at(t, close, color=color))
            pos = tr.state["position"]
            self.assertIsNotNone(pos)
            self.assertEqual(pos["entry_source"], "retest_trend")
            self.assertEqual(pos["side"], "CALL")
            self.assertAlmostEqual(pos["tp_pct"], 0.12)
            self.assertEqual(pos["time_exit_min"], 5)
            self.assertAlmostEqual(pos["qqq_stop_level"], round(pos["entry_qqq"] - 0.30, 2))
            self.assertEqual(tr.b.placed, [])
            decisions = [e for e in read_events(log) if e["event"] in ("no_entry", "entry_signal", "entry_blocked", "hold")]
            self.assertTrue(decisions)
            self.assertTrue(all("day_regime" in e for e in decisions))
            self.assertEqual(decisions[-1]["day_regime"], "TREND")

    def test_chop_fade_arms_the_bar_stop_and_mixed_warmup_stay_flat(self):
        with tempfile.TemporaryDirectory() as tmp:
            start = datetime(2026, 10, 26, 9, 0, tzinfo=CT)
            tr, log, clock = make_trader(tmp, start.date(), ov=override())
            for i in range(21):
                t = start + timedelta(minutes=i)
                close = 100.2 if i % 2 == 0 else 99.8
                kw = {}
                if i == 20:
                    kw = {"color": "red", "high": 100.40, "low": 99.70}
                    close = 99.80
                feed(tr, clock, bar_at(t, close, ema=100.0, vwap=100.0, **kw))
            pos = tr.state["position"]
            self.assertEqual(pos["entry_source"], "vwap_fade")
            self.assertEqual(pos["side"], "PUT")
            self.assertAlmostEqual(pos["tp_pct"], 0.25)
            self.assertEqual(pos["time_exit_min"], 10)
            self.assertAlmostEqual(pos["qqq_stop_dist"], fade_stop_dist("PUT", 99.80, 100.40, 99.70))
            self.assertAlmostEqual(pos["qqq_stop_level"], round(99.80 + pos["qqq_stop_dist"], 2))
            entry = [e for e in read_events(log) if e["event"] == "entry_signal"][-1]
            self.assertEqual(entry["day_regime"], "CHOP")

            # next bar trades through the stop; the option mark stays at the fill so the
            # -50% option backstop does not take it first
            nxt = start + timedelta(minutes=21)
            feed(tr, clock, bar_at(nxt, 100.6, high=100.9, low=100.5, ema=100.0, vwap=100.0, color="green"))
            self.assertIsNone(tr.state["position"])
            self.assertIn("stop", tr.state["closed"][-1]["reason"])
            self.assertFalse(tr.state["done"])  # max_buys is 12

        with tempfile.TemporaryDirectory() as tmp:
            start = datetime(2026, 10, 26, 8, 30, tzinfo=CT)
            tr, log, clock = make_trader(tmp, start.date(), ov=override())
            for i in range(21):
                t = start + timedelta(minutes=i)
                close = 700 + i * 0.10
                feed(tr, clock, bar_at(t, close, color="red", high=close + 0.40, low=close - 0.10))
            self.assertIsNone(tr.state["position"])
            last = [e for e in read_events(log) if e["event"] == "no_entry"][-1]
            self.assertEqual(last["day_regime"], "WARMUP")

        with tempfile.TemporaryDirectory() as tmp:
            start = datetime(2026, 10, 26, 9, 0, tzinfo=CT)
            tr, log, clock = make_trader(tmp, start.date(), ov=override())
            for i in range(21):
                t = start + timedelta(minutes=i)
                ema = 100 + i * 0.05
                slot = i - 1 if i else 0
                up = slot < 5 or 10 <= slot < 15
                close = ema + (0.10 if up else -0.10)
                # a textbook fade wick that MIXED must ignore
                kw = {"color": "red", "high": close + 0.50, "low": close - 0.10, "vwap": ema - 1.0}
                feed(tr, clock, bar_at(t, close, ema=ema, **kw))
            self.assertIsNone(tr.state["position"])
            last = [e for e in read_events(log) if e["event"] == "no_entry"][-1]
            self.assertEqual(last["day_regime"], "MIXED")

    def test_flag_off_logs_no_regime_and_live_ignores_the_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = datetime(2026, 10, 26, 9, 5, tzinfo=CT)
            tr, log, clock = make_trader(tmp, day.date(), ov=override(regime_mode=False, entry_mode="config_c"))
            feed(tr, clock, bar_at(day, 700))
            event = read_events(log)[-1]
            self.assertEqual(event["event"], "no_entry")
            self.assertNotIn("day_regime", event)
            self.assertNotIn("day_regime_hist", tr.state)

            live_state = Path(tmp) / "trader_state.json"
            live_state.write_text(json.dumps({
                "day": "2026-10-26", "buys": 0, "attempts": 0, "position": None,
                "pending_buy": None, "done": False, "closed": [],
                "override": override(),
            }))
            live = Trader(FakeBroker(), trader.Logger(Path(tmp) / "live.log", "LIVE", echo=False),
                          live=True, state_path=live_state, kill_path=Path(tmp) / "KILL",
                          clock=Clock(day + timedelta(seconds=70)), signals_log=None)
            before = json.loads(live_state.read_text())
            live.on_bar(bar_at(day, 700, color="green"), day + timedelta(seconds=70))
            after = json.loads(live_state.read_text())
            self.assertNotIn("day_regime_hist", after)
            self.assertEqual(before.get("override"), after.get("override"))
            self.assertTrue(all("day_regime" not in e for e in read_events(Path(tmp) / "live.log")))


if __name__ == "__main__":
    unittest.main()
