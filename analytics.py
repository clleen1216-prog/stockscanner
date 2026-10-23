"""
analytics.py - 指標、訊號、交易模擬、統計證據、風險評估、機器學習
所有訊號只使用「當日(含)以前」的資料，進場假設為訊號隔日開盤價，避免未來函數。
"""
import math
import zlib

import numpy as np
import pandas as pd

# 台股來回交易成本：手續費 0.1425% x2 + 證交稅 0.3%
ROUND_TRIP_COST = 0.00585

FEATURE_COLS = [
    "spread", "vol_ratio", "rsi", "atr_pct", "dist_high", "ma120_slope",
    "max_drop", "trig_count", "body_atr", "ret20", "upper_ratio", "bull",
]


# ==============================================================================
# 1. 指標與訊號（向量化，可回溯每一天）
# ==============================================================================
def add_indicators(df):
    d = df.copy()
    for n in (5, 10, 20, 60, 120, 200):
        d[f"MA{n}"] = d["Close"].rolling(n).mean()
    d["Vol_MA5"] = d["Volume"].rolling(5).mean()
    d["Vol_MA20"] = d["Volume"].rolling(20).mean()

    prev_close = d["Close"].shift(1)
    tr = pd.concat(
        [d["High"] - d["Low"], (d["High"] - prev_close).abs(), (d["Low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    d["ATR14"] = tr.rolling(14).mean()

    delta = d["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    d["RSI14"] = 100 - 100 / (1 + rs)

    d["High_1y"] = d["High"].rolling(250, min_periods=120).max()
    d["Low_120"] = d["Low"].rolling(120).min()
    return d


def compute_signals(d, cfg):
    """回傳 (訊號表 s, 特徵表 f)。邏輯與原版掃描器完全一致，但可套用到歷史每一天。"""
    s = pd.DataFrame(index=d.index)

    max_drop = (d["High_1y"] - d["Low_120"]) / d["High_1y"]
    ma120_slope = d["MA120"] / d["MA120"].shift(20) - 1
    ma200_slope = (d["MA200"] / d["MA200"].shift(20) - 1).fillna(0)

    if cfg.get("setup_mode") == "uptrend_base":
        # 變體：上升趨勢中的整理（股價在 120MA 之上、120MA 向上、距 1 年高點不遠）
        s["trend"] = (
            (d["Close"] > d["MA120"]) & (ma120_slope > 0)
            & (d["Close"] >= d["High_1y"] * 0.75)
        )
    else:
        s["trend"] = (
            ((max_drop >= 0.30) | (ma120_slope.abs() < 0.03))
            & (ma120_slope <= 0.015)
            & (ma200_slope <= 0.015)
            & (d["Close"] <= d["High_1y"] * cfg["max_relative_high"])
        )

    mas = d[["MA5", "MA10", "MA20", "MA60"]]
    spread = (mas.max(axis=1) - mas.min(axis=1)) / mas.min(axis=1)
    s["structure"] = (
        (spread < cfg["max_ma_spread"]) & (d["Close"] >= d["MA20"]) & (d["Close"] >= d["MA60"])
    )

    s["volume"] = (d["Vol_MA5"] < d["Vol_MA20"]) & (
        d["Volume"].rolling(10).max() < d["Volume"].shift(10).rolling(50).max()
    )
    s["setup"] = s["trend"] & s["structure"] & s["volume"]

    body = (d["Close"] - d["Open"]).abs()
    prev5_body = body.shift(1).rolling(5).mean()
    upper = d["High"] - d[["Close", "Open"]].max(axis=1)

    t1 = d["Volume"] >= d["Vol_MA20"] * 1.3
    t2 = d["Close"] >= d["Close"].rolling(20).max()
    t3 = body >= prev5_body
    s["trig_count"] = t1.astype(int) + t2.astype(int) + t3.astype(int)

    not_exaggerated = d["Volume"] < d["Vol_MA20"] * 3.5
    healthy_k = (upper <= body * 1.5) | (body <= 0)
    s["entry"] = s["setup"] & (s["trig_count"] >= cfg.get("trig_min", 2)) & not_exaggerated & healthy_k

    f = pd.DataFrame(index=d.index)
    f["spread"] = spread
    f["vol_ratio"] = d["Volume"] / d["Vol_MA20"]
    f["rsi"] = d["RSI14"]
    f["atr_pct"] = d["ATR14"] / d["Close"]
    f["dist_high"] = d["Close"] / d["High_1y"]
    f["ma120_slope"] = ma120_slope
    f["max_drop"] = max_drop
    f["trig_count"] = s["trig_count"]
    f["body_atr"] = body / d["ATR14"]
    f["ret20"] = d["Close"] / d["Close"].shift(20) - 1
    f["upper_ratio"] = upper / (d["High"] - d["Low"]).replace(0, np.nan)
    if cfg.get("setup_mode") in ("flow_breakout", "low_volume_spike", "cmf_accum", "momentum_flow"):
        s = _flow_signals(d, s, cfg["setup_mode"])
    return s, f


def _flow_signals(d, s, mode):
    """資金流向類訊號（只用價量，回溯可驗證）。回傳更新後的 s。"""
    c, o, h, l, v = d["Close"], d["Open"], d["High"], d["Low"], d["Volume"]
    rng = (h - l).replace(0, np.nan)
    pos = (c - l) / rng                       # 收盤在當日區間的位置 (1=收最高)
    ma60_up = d["MA60"] > d["MA60"].shift(10)
    vr = v / d["Vol_MA20"]
    if mode == "flow_breakout":               # 價漲量增：多頭排列中帶量突破 20 日高
        setup = (c > d["MA20"]) & (d["MA20"] > d["MA60"]) & ma60_up
        trig = (vr >= 1.5) & (vr < 4) & (c > o) & (c >= c.rolling(20).max()) & (pos >= 0.7)
    elif mode == "low_volume_spike":          # 爆量不跌：低檔爆量收紅且不創新低
        setup = c <= d["Low_120"] * 1.20
        prior_low = l.shift(1).rolling(20).min()
        trig = (vr >= 2.5) & (c > o) & (pos >= 0.5) & (l >= prior_low)
    elif mode == "cmf_accum":                 # 資金累積：20 日 Chaikin 資金流轉強
        mfm = ((c - l) - (h - c)) / rng
        cmf = (mfm.fillna(0) * v).rolling(20).sum() / v.rolling(20).sum()
        setup = (c > d["MA60"]) & ma60_up
        trig = (cmf > 0.10) & (cmf.shift(1) <= 0.10)
    elif mode == "momentum_flow":             # 強勢+資金湧入：60 日漲幅大且帶量創 60 日新高
        setup = ((c / c.shift(60) - 1) >= 0.20) & (c > d["MA20"]) & (d["MA20"] > d["MA60"]) \
                & (d["Vol_MA20"] > v.rolling(60).mean())
        trig = (c >= c.rolling(60).max()) & (vr >= 1.3) & (vr < 4) & (c > o)
    else:
        return s
    s["setup"] = setup.fillna(False)
    s["entry"] = (setup & trig).fillna(False)
    return s


def stop_fraction(atr, price, cfg):
    """停損距離占價格比例（回測與實戰共用同一公式，確保證據與建議一致）"""
    return float(min(max(cfg["atr_stop_mult"] * atr / price, cfg["min_stop_pct"]), cfg["max_stop_pct"]))


# ==============================================================================
# 2. 交易模擬（隔日開盤進場、ATR停損、R倍數停利、時間出場、含交易成本）
# ==============================================================================
def simulate_trade(o, h, l, c, atr, i, cfg, ma20=None):
    n = len(c)
    j0 = i + 1
    if j0 >= n or not np.isfinite(atr[i]) or atr[i] <= 0:
        return None
    entry = o[j0]
    if not np.isfinite(entry) or entry <= 0:
        return None

    risk_frac = stop_fraction(atr[i], entry, cfg)
    stop = entry * (1 - risk_frac)
    trail = cfg.get("exit_mode") == "trail" and ma20 is not None
    target = np.inf if trail else entry * (1 + risk_frac * cfg["target_R"])

    last = min(j0 + cfg["hold_days"], n) - 1
    exit_price, reason, bars = c[last], "time", last - j0 + 1
    for j in range(j0, last + 1):
        if j > j0 and o[j] <= stop:          # 跳空跌破停損，以開盤價出場
            exit_price, reason, bars = o[j], "stop_gap", j - j0 + 1
            break
        if l[j] <= stop:                      # 同日同時觸及時，保守先算停損
            exit_price, reason, bars = stop, "stop", j - j0 + 1
            break
        if trail and j > j0 and np.isfinite(ma20[j]) and c[j] < ma20[j]:
            exit_price, reason, bars = c[j], "trail", j - j0 + 1   # 收盤跌破 20MA 出場
            break
        if h[j] >= target:
            exit_price, reason, bars = target, "target", j - j0 + 1
            break

    ret = exit_price / entry - 1 - cfg.get("round_trip_cost", ROUND_TRIP_COST)   # 預設為台股成本；美股設定會覆蓋
    return {"ret": float(ret), "R": float(ret / risk_frac), "bars": int(bars),
            "reason": reason, "risk_frac": float(risk_frac)}


def collect_history(code, d, s, f, cfg, bull_by_date):
    """
    對單一股票回溯：
      trades   - 歷史上每次「進場訊號」的模擬結果（統計證據）
      samples  - 歷史上每次「型態成立日」的特徵+結果（機器學習訓練資料）
      baseline - 隨機日期進場的模擬結果（用來檢驗策略是否優於亂買）
    """
    n = len(d)
    o, h, l, c = d["Open"].values, d["High"].values, d["Low"].values, d["Close"].values
    atr = d["ATR14"].values
    ma20 = d["MA20"].values
    hold = cfg["hold_days"]

    liq = (
        (d["Close"] >= cfg["min_price"])
        & (d["Vol_MA20"] >= cfg["min_avg_vol_20d"])
        & (d["Vol_MA20"] <= cfg["max_avg_vol_20d"])
    ).values
    entry = s["entry"].values & liq
    setup = s["setup"].values & liq

    bull = (
        bull_by_date.reindex(d.index, method="ffill").fillna(1.0).values > 0.5
        if bull_by_date is not None else np.ones(n, dtype=bool)
    )

    trades, next_ok = [], 0
    for i in np.flatnonzero(entry):
        if i < next_ok or i + hold + 1 >= n:   # 不重疊持倉；未結算的訊號不納入統計
            continue
        r = simulate_trade(o, h, l, c, atr, i, cfg, ma20)
        if r:
            r.update(code=code, date=d.index[i], bull=bool(bull[i]))
            trades.append(r)
            next_ok = i + hold

    samples, last_i = [], -99
    for i in ([] if cfg.get("skip_samples") else np.flatnonzero(setup)):
        if i - last_i < 5 or i + hold + 1 >= n:
            continue
        r = simulate_trade(o, h, l, c, atr, i, cfg, ma20)
        if r is None:
            continue
        last_i = i
        row = f.iloc[i].to_dict()
        row["bull"] = float(bull[i])
        row.update(date=d.index[i], label=int(r["ret"] > 0), code=code)
        samples.append(row)

    baseline = []
    valid = np.flatnonzero(liq[: max(n - hold - 1, 0)])
    valid = valid[valid >= 200]
    if len(valid):
        rng = np.random.default_rng(zlib.crc32(code.encode()) % (2**32))
        pick = rng.choice(valid, size=min(cfg["baseline_per_stock"], len(valid)), replace=False)
        for i in pick:
            r = simulate_trade(o, h, l, c, atr, int(i), cfg, ma20)
            if r:
                r.update(code=code, date=d.index[i], bull=bool(bull[i]))
                baseline.append(r)

    return trades, samples, baseline


# ==============================================================================
# 3. 統計證據
# ==============================================================================
def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def wilson_interval(wins, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    adj = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0.0, (centre - adj) / denom), min(1.0, (centre + adj) / denom)


def two_proportion_p(w1, n1, w2, n2):
    """雙比例 z 檢定（雙尾 p 值）"""
    if n1 == 0 or n2 == 0:
        return 1.0
    p1, p2, p = w1 / n1, w2 / n2, (w1 + w2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    return 2 * (1 - norm_cdf(abs((p1 - p2) / se)))


def summarize(df):
    n = len(df)
    if n == 0:
        return {"n": 0, "win_rate": 0.0, "wins": 0, "ci_lo": 0.0, "ci_hi": 0.0,
                "avg_win_R": 0.0, "avg_loss_R": 0.0, "expectancy_R": 0.0,
                "t_stat": 0.0, "profit_factor": 0.0, "avg_ret": 0.0,
                "median_ret": 0.0, "avg_bars": 0.0, "max_dd_R": 0.0}
    win_mask = df["ret"] > 0
    wins = int(win_mask.sum())
    lo, hi = wilson_interval(wins, n)
    exp = float(df["R"].mean())
    sd = float(df["R"].std(ddof=1)) if n > 1 else 0.0
    gross_win = float(df.loc[win_mask, "ret"].sum())
    gross_loss = float(-df.loc[~win_mask, "ret"].sum())
    ordered = df.sort_values("date")["R"].cumsum()
    max_dd = float((ordered.cummax() - ordered).max()) if n else 0.0
    return {
        "n": n, "wins": wins, "win_rate": wins / n, "ci_lo": lo, "ci_hi": hi,
        "avg_win_R": float(df.loc[win_mask, "R"].mean()) if wins else 0.0,
        "avg_loss_R": float(df.loc[~win_mask, "R"].mean()) if wins < n else 0.0,
        "expectancy_R": exp,
        "t_stat": exp / (sd / math.sqrt(n)) if sd > 0 else 0.0,
        "profit_factor": min(gross_win / gross_loss, 99.0) if gross_loss > 0 else 99.0,
        "avg_ret": float(df["ret"].mean()), "median_ret": float(df["ret"].median()),
        "avg_bars": float(df["bars"].mean()), "max_dd_R": max_dd,
    }


def build_evidence(trades_df, baseline_df):
    """策略整體證據：全樣本、多空環境分層、樣本外穩定度、與隨機進場比較"""
    overall = summarize(trades_df)
    base = summarize(baseline_df)
    regime = {
        True: summarize(trades_df[trades_df["bull"]]) if len(trades_df) else summarize(trades_df),
        False: summarize(trades_df[~trades_df["bull"]]) if len(trades_df) else summarize(trades_df),
    }

    oos = summarize(trades_df.iloc[0:0])
    ins = summarize(trades_df.iloc[0:0])
    if len(trades_df) >= 20:
        ordered = trades_df.sort_values("date")
        cut = int(len(ordered) * 0.7)
        ins, oos = summarize(ordered.iloc[:cut]), summarize(ordered.iloc[cut:])

    p_vs_random = two_proportion_p(overall["wins"], overall["n"], base["wins"], base["n"])
    edge = overall["win_rate"] - base["win_rate"]
    validated = bool(
        overall["n"] >= 30 and overall["expectancy_R"] > 0
        and edge > 0 and p_vs_random < 0.05
    )
    return {
        "overall": overall, "baseline": base, "regime": regime,
        "in_sample": ins, "out_of_sample": oos,
        "edge_vs_random": edge, "p_vs_random": p_vs_random, "validated": validated,
    }


# ==============================================================================
# 4. 機率估計：貝氏收縮 + 機器學習
# ==============================================================================
def blend_probability(stock_wins, stock_n, prior_p, k):
    """個股自身歷史勝率向「全市場同型態勝率」收縮，樣本越少越相信全市場"""
    return (stock_wins + prior_p * k) / (stock_n + k)


def train_model(samples_df, cfg):
    """以時間切分（前70%訓練、後30%測試，中間留20天隔離）驗證模型是否真的有預測力"""
    out = {"valid": False, "status": "樣本不足，未啟用機器學習", "n": len(samples_df)}
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.metrics import roc_auc_score
    except ImportError:
        out["status"] = "未安裝 scikit-learn，未啟用機器學習"
        return out

    if len(samples_df) < cfg["ml_min_samples"] or samples_df["label"].nunique() < 2:
        return out

    df = samples_df.sort_values("date").reset_index(drop=True)
    cut_date = df["date"].iloc[int(len(df) * 0.7)]
    train = df[df["date"] < cut_date - pd.Timedelta(days=30)]
    test = df[df["date"] >= cut_date]
    if len(train) < 100 or len(test) < 50 or train["label"].nunique() < 2 or test["label"].nunique() < 2:
        return out

    def new_model():
        return HistGradientBoostingClassifier(
            max_depth=3, learning_rate=0.05, max_iter=150,
            min_samples_leaf=30, l2_regularization=1.0, random_state=7,
        )

    m = new_model().fit(train[FEATURE_COLS], train["label"])
    p = m.predict_proba(test[FEATURE_COLS])[:, 1]
    auc = float(roc_auc_score(test["label"], p))
    top = test[p >= np.quantile(p, 0.75)]
    final = new_model().fit(df[FEATURE_COLS], df["label"])

    out.update(
        model=final, auc=auc, train_n=len(train), test_n=len(test),
        base_rate=float(df["label"].mean()),
        test_base_rate=float(test["label"].mean()),
        top_quartile_win=float(top["label"].mean()),
        valid=bool(auc >= 0.55),
        status=("已啟用（樣本外 AUC=%.3f）" % auc) if auc >= 0.55
        else ("AUC=%.3f 未達 0.55，模型預測力不足，已停用" % auc),
    )
    return out


def predict_ml(ml, feat_row, cfg):
    if not ml or not ml.get("valid"):
        return None
    X = pd.DataFrame([feat_row])[FEATURE_COLS]
    p = float(ml["model"].predict_proba(X)[0, 1])
    base = ml["base_rate"]
    return base + cfg["ml_shrink"] * (p - base)   # 向基準勝率收縮，避免過度自信


# ==============================================================================
# 5. 風險評估
# ==============================================================================
def kelly_fraction(p, avg_win_R, avg_loss_R):
    if avg_win_R <= 0 or avg_loss_R >= 0:
        return 0.0
    b = avg_win_R / abs(avg_loss_R)
    return max(0.0, p - (1 - p) / b)


def stock_risk_stats(d, twii_ret):
    """年化波動、近一年最大回撤、60日 Beta"""
    close = d["Close"]
    ret = close.pct_change().dropna()
    vol_ann = float(ret.iloc[-250:].std() * math.sqrt(250)) if len(ret) > 20 else 0.0
    window = close.iloc[-250:]
    max_dd = float((1 - window / window.cummax()).max()) if len(window) else 0.0

    beta = 1.0
    if twii_ret is not None and len(ret) > 60:
        j = pd.concat([ret.iloc[-120:], twii_ret], axis=1, join="inner").dropna()
        if len(j) >= 40 and j.iloc[:, 1].var() > 0:
            beta = float(j.iloc[:, 0].cov(j.iloc[:, 1]) / j.iloc[:, 1].var())
    return vol_ann, max_dd, beta


def risk_score(atr_pct, max_dd, beta, turnover_m, bull, night_safe, evidence_n):
    """0~100，越高越危險"""
    score = min(atr_pct / 0.06, 1) * 25
    score += min(max_dd / 0.5, 1) * 15
    score += min(max(beta, 0) / 1.8, 1) * 10
    score += 10 if turnover_m < 20 else (5 if turnover_m < 50 else 0)
    score += 0 if bull else 15
    score += 0 if night_safe else 10
    score += 15 * (1 - min(evidence_n / 50, 1))
    score = float(round(score, 1))
    label = "低" if score < 35 else ("中" if score < 60 else "高")
    return score, label


def evidence_strength(n):
    return "強" if n >= 100 else ("中" if n >= 30 else "弱")


def welch_t(x, y):
    """兩組 R 倍數的 Welch t 統計量（x 的平均是否高於 y）"""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 2 or len(y) < 2:
        return 0.0
    se = math.sqrt(x.var(ddof=1) / len(x) + y.var(ddof=1) / len(y))
    return float((x.mean() - y.mean()) / se) if se > 0 else 0.0
