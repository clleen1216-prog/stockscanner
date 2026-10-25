"""
離線測試（不連網）：python -m unittest tests.test_regime -v   （在專案根目錄執行）
用假的網路連線與合成資料，確認宏觀風險調節、前瞻記錄、證據看板，以及它們與掃描器 / 紙上交易的串接。
"""
import json
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import analytics as an          # noqa: E402
import paper_trade as pt        # noqa: E402
import regime                   # noqa: E402
import stock_scanner as sc      # noqa: E402


def weekly(start, n, v0, drift):
    idx = pd.date_range(start, periods=n, freq="W-WED")
    return pd.Series(v0 * (1 + drift) ** np.arange(n), index=idx)


def fred_series(direction):
    """direction=+1 擴張 / -1 收縮。單位：WALCL、TGA 為百萬美元；RRP 為十億美元。"""
    end = pd.Timestamp.today().normalize()
    start = end - pd.Timedelta(weeks=100)
    walcl = weekly(start, 100, 7_000_000, 0.002 * direction)
    tga = weekly(start, 100, 800_000, 0.0)
    rrp = pd.Series(300.0, index=pd.bdate_range(start, end))
    return walcl, tga, rrp


class FakeResp:
    def __init__(self, text="", js=None):
        self.text, self._js, self.status_code = text, js, 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._js


class FakeSession:
    """假的 requests.Session：FRED 回 CSV，Yahoo 回圖表 JSON。"""
    def __init__(self, direction, vix=18.0):
        self.series = dict(zip(("WALCL", "WTREGEN", "RRPONTSYD"), fred_series(direction)))
        self.vix = vix

    def get(self, url, **kw):
        if "fredgraph" in url:
            s = self.series[url.split("id=")[1]]
            body = "observation_date,v\n" + "\n".join(f"{d:%Y-%m-%d},{v}" for d, v in s.items())
            return FakeResp(text=body)
        sym = url.rsplit("/", 1)[1]
        px = {"^VIX": self.vix, "^GSPC": 5000.0, "^TWII": 20000.0}.get(sym, 100.0)
        ts = [1_700_000_000 + 86400 * i for i in range(10)]
        return FakeResp(js={"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [{"close": [px] * 10}]}}]}})


class TestOverlay(unittest.TestCase):
    def test_never_enlarges(self):
        fed_up = {"expanding": True, "units_ok": True}
        fed_dn = {"expanding": False, "units_ok": True}
        for vix in (None, 10, 17, 25, 35, 60):
            for fed in (None, fed_up, fed_dn):
                self.assertLessEqual(regime.macro_overlay(fed, vix)["size_mult"], 1.0)

    def test_rules(self):
        fed_dn = {"expanding": False, "units_ok": True}
        fed_up = {"expanding": True, "units_ok": True}
        self.assertEqual(regime.macro_overlay(fed_up, 12)["size_mult"], 1.0)
        self.assertEqual(regime.macro_overlay(fed_up, 25)["size_mult"], 0.75)
        self.assertEqual(regime.macro_overlay(fed_dn, 12)["size_mult"], 0.75)
        self.assertEqual(regime.macro_overlay(fed_dn, 35)["size_mult"], 0.375)   # 0.5 * 0.75
        self.assertEqual(regime.macro_overlay(None, None)["size_mult"], 1.0)     # 資料缺漏 → 不調整
        bad_units = {"expanding": False, "units_ok": False}
        self.assertEqual(regime.macro_overlay(bad_units, 12)["size_mult"], 1.0)   # 單位異常 → 不採用


class TestFed(unittest.TestCase):
    def test_direction(self):
        w, t, r = fred_series(+1)
        up = regime.fed_from_series(w, t, r)
        w, t, r = fred_series(-1)
        dn = regime.fed_from_series(w, t, r)
        self.assertTrue(up["expanding"] and up["units_ok"] and up["chg13_pct"] > 0)
        self.assertFalse(dn["expanding"] and dn["units_ok"])
        self.assertTrue(1000 < up["net_bn"] < 12000)

    def test_get_macro_offline(self):
        m = regime.get_macro(FakeSession(-1, vix=35.0))
        self.assertFalse(m["fed"]["expanding"])
        self.assertEqual(m["size_mult"], 0.375)
        self.assertEqual((m["spx"], m["twii"], m["vix"]), (5000.0, 20000.0, 35.0))
        self.assertTrue(any("收縮" in x for x in m["notes"]))

    def test_lines(self):
        txt = "\n".join(regime.macro_lines(regime.get_macro(FakeSession(+1))))
        self.assertIn("擴張", txt)
        self.assertIn("不是選股訊號", txt)
        self.assertIn("資料暫時無法取得", regime.macro_lines(None)[0])


class TestForward(unittest.TestCase):
    def test_log_spacing_and_bar(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "macro_log.csv")
            m = {"fed": {"expanding": True, "units_ok": True}, "vix": 18, "spx": 5000.0, "twii": 20000.0}
            t0 = pd.Timestamp("2026-01-01")
            self.assertTrue(regime.log_macro(m, p, today=t0))
            self.assertFalse(regime.log_macro(m, p, today=t0 + pd.Timedelta(days=10)))   # 未滿 28 天不記
            self.assertTrue(regime.log_macro(m, p, today=t0 + pd.Timedelta(days=28)))
            self.assertFalse(regime.log_macro({**m, "fed": None}, p, today=t0 + pd.Timedelta(days=90)))
            self.assertEqual(len(pd.read_csv(p)), 2)

    def test_verdict_bar(self):
        rng = np.random.default_rng(1)
        good = list(0.02 + rng.normal(0, 0.01, 20))          # 穩定為正
        noise = list(rng.normal(0, 0.03, 40))                # 純雜訊
        self.assertTrue(regime.verdict(good)["ok"])
        self.assertFalse(regime.verdict(good[:8])["ok"])     # 期數不足
        self.assertFalse(regime.verdict(noise)["ok"])
        first_only = list(np.r_[np.full(10, 0.03), np.full(10, -0.001)] + rng.normal(0, 0.002, 20))
        self.assertFalse(regime.verdict(first_only)["ok"])   # 後半期不為正

    def test_forward_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "macro_log.csv")
            rng = np.random.default_rng(3)
            px, rows = 100.0, []
            for i in range(16):                               # 16 期，訊號完全正確預測方向
                s = int(rng.integers(0, 2))
                rows.append({"date": f"2025-{(i % 12) + 1:02d}-01", "fed_expanding": s, "vix": 18, "spx": px, "twii": px})
                px *= 1.03 if s else 0.97
            pd.DataFrame(rows).to_csv(p, index=False)
            res = regime.forward_results(p)
            self.assertEqual(res["S&P 500"]["n"], 15)
            self.assertTrue(res["S&P 500"]["mean"] > 0)
            self.assertTrue(res["S&P 500"]["ok"])                                # 訊號完美預測 → 通過門檻
            self.assertIn("通過（新資料）", "\n".join(regime.forward_lines(p)))
            short = os.path.join(d, "short.csv")
            pd.DataFrame(rows[:5]).to_csv(short, index=False)
            self.assertIn("樣本不足", "\n".join(regime.forward_lines(short)))   # 只有 4 期 → 不判定


class TestEvidence(unittest.TestCase):
    def test_seed_and_update(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "evidence.json")
            ev = regime.load_evidence(p)
            self.assertFalse(any(v["passed"] for v in ev.values()))    # 種子資料都是未通過
            regime.update_evidence("13f_growth", p, name="x", periods=17, unit="季", mean=float("nan"),
                                   t=1.0, passed=False, asof="20261101", source="test")
            with open(p, encoding="utf-8") as fh:
                self.assertIsNone(json.load(fh)["13f_growth"]["mean"])                           # NaN 不會寫壞 JSON
            self.assertEqual(regime.load_evidence(p)["13f_growth"]["periods"], 17)               # 覆蓋種子
            md = "\n".join(regime.evidence_lines(p))
            self.assertIn("證據看板", md)
            self.assertNotIn("✅", md)


def fake_evidence(n=200, seed=0):
    rng = np.random.default_rng(seed)
    mk = lambda mu: pd.DataFrame({"ret": rng.normal(mu, 0.05, n), "R": rng.normal(mu * 10, 1.0, n),
                                  "bars": 10, "reason": "time", "risk_frac": 0.05, "code": "2330",
                                  "date": pd.date_range("2022-01-01", periods=n), "bull": rng.random(n) > 0.3})
    return an.build_evidence(mk(0.01), mk(0.0))


class TestScannerIntegration(unittest.TestCase):
    def setUp(self):
        self.cur = {"code": "2330", "name": "TSMC", "market": "TWSE", "close": 100.0, "low": 98.0, "body": 2.0,
                    "is_entry": True, "trig_count": 2, "atr": 3.0, "ma60": 95.0, "avg_vol_lots": 5000,
                    "feat": {"spread": 0.03, "vol_ratio": 1.5, "dist_high": 0.6, "rsi": 55.0},
                    "vol_ann": 0.3, "max_dd": 0.2, "beta": 1.0}
        self.ev = fake_evidence()

    def ctx(self, macro):
        env = {"is_day_bullish": True, "is_night_safe": True, "macro": macro, "twii_close": 46000.0,
               "twii_ma60": 45000.0, "night_pct": 0.3}
        empty = pd.DataFrame(columns=["ret", "R", "bars", "reason", "risk_frac", "code", "date", "bull"])
        return {"env": env, "evidence": self.ev, "ml": {"valid": False, "status": "x"}, "trades_df": empty,
                "twse_chips": {"2330": {"foreign": 1_000_000, "trust": 0}}, "tpex_chips": {}}

    def test_position_scaled_down_only(self):
        base = sc.evaluate_candidate(self.cur, self.ctx(None))
        cut = sc.evaluate_candidate(self.cur, self.ctx({"size_mult": 0.375, "notes": ["Fed 收縮"], "fed": None}))
        up = sc.evaluate_candidate(self.cur, self.ctx({"size_mult": 5.0, "notes": ["bug"], "fed": None}))
        self.assertAlmostEqual(cut["position_pct"], base["position_pct"] * 0.375, delta=0.06)
        self.assertEqual(up["position_pct"], base["position_pct"])              # 倍數被限制在 1 以內
        for k in ("grade", "win_prob", "ev_R", "stop_price"):                    # 評級與機率完全不受影響
            self.assertEqual(base[k], cut[k])
        self.assertTrue(any("宏觀風險調節" in x for x in cut["insights"]))
        self.assertFalse(any("宏觀風險調節" in x for x in base["insights"]))

    def test_report_sections(self):
        macro = regime.get_macro(FakeSession(-1, vix=25.0))
        ctx = self.ctx(macro)
        pick = sc.evaluate_candidate(self.cur, ctx)
        env = ctx["env"]
        md = sc.build_markdown(env, self.ev, {"valid": False, "status": "x"}, [pick], "", "20261024")
        self.assertIn("Fed 淨流動性", md)
        self.assertIn("宏觀部位倍數", md)
        self.assertIn("證據看板", md)
        self.assertIn("13F", md)


class TestPaperIntegration(unittest.TestCase):
    def test_report_has_forward_sections(self):
        rows = []
        for i in range(24):
            rows.append({c: None for c in pt.COLS} | {
                "strategy": "V8", "signal_date": f"2026-0{1 + i % 9}-1{i % 9}", "code": f"{2000 + i}", "name": "n",
                "market": "TWSE", "status": "closed", "R": 0.5 if i % 2 else -0.5, "ret": 0.02 if i % 2 else -0.02,
                "bars": 10, "bull": True, "bench_ret": 0.01, "fed_expanding": i % 2})
        ledger = pd.DataFrame(rows, columns=pt.COLS)
        extra = regime.forward_lines("nonexistent.csv") + regime.evidence_lines()
        md = pt.build_report(ledger, "2026-10-24", extra)
        self.assertIn("Fed 流動性狀態 vs 結果", md)
        self.assertIn("宏觀前瞻驗證", md)
        self.assertIn("證據看板", md)
        self.assertIn("12 / +0.50R", md)                                         # 擴張組 12 筆


if __name__ == "__main__":
    unittest.main()
