"""
ai_insights.py - 白話洞察（規則式，一定有）+ Claude 解讀（選用，需 ANTHROPIC_API_KEY）
"""
import json
import os

import requests


def build_rule_insight(c, env, evidence):
    """以統計數字產生可驗證的白話說明，不編造任何數據"""
    lines = []
    lines.append(
        f"型態：均線糾結 {c['ma_spread_pct']}%，今日量為 20 日均量的 {c['vol_ratio']}x，"
        f"股價位於 1 年高點的 {c['dist_high_pct']}%，RSI {c['rsi']}。"
    )
    if c["stock_hist_n"] > 0:
        lines.append(
            f"個股歷史：此型態出現 {c['stock_hist_n']} 次，勝 {round(c['stock_hist_wr'] * 100)}%（樣本小，僅供參考）。"
        )
    lines.append(
        f"全市場證據：同環境下類似訊號 {c['evidence_n']} 次，勝率 {c['regime_wr_pct']}%"
        f"（95% 區間 {c['regime_ci_lo']}%~{c['regime_ci_hi']}%），證據強度「{c['evidence_label']}」。"
    )
    ml_txt = f"，機器學習 {round(c['win_prob_ml'] * 100)}%" if c["win_prob_ml"] is not None else ""
    lines.append(
        f"綜合勝率估計 {round(c['win_prob'] * 100)}%（貝氏 {round(c['win_prob_bayes'] * 100)}%{ml_txt}），"
        f"扣除交易成本後期望值 {c['ev_R']:+.2f}R。"
    )
    lines.append(
        f"風險：評分 {c['risk_score']}（{c['risk_label']}），ATR {c['atr_pct']}%，近一年最大回撤 {c['max_dd_1y']}%，"
        f"Beta {c['beta']}。"
    )
    lines.append(
        f"計畫：參考價 ${c['close']}，停損 ${c['stop_price']}（-{c['stop_pct']}%），"
        f"目標 ${c['target_price']}；單筆最大虧損約 {c['risk_pct_used']}% 資金，建議部位約 {c['position_pct']}% 資金。"
    )
    if not env["is_day_bullish"]:
        lines.append("警示：加權指數在季線下，勝率通常較低。")
    if not env["is_night_safe"]:
        lines.append("警示：隔夜美股走弱，留意開低風險。")
    if not evidence["validated"]:
        lines.append("警示：策略整體尚未通過統計驗證（未顯著優於隨機進場），部位已減半。")
    lines.append(f"失效條件：收盤跌破 ${c['stop_price']}，或大盤跌破季線。")
    return lines


def llm_summary(picks, env, evidence, ml, model, top_n=8):
    """選用：把統計結果交給 Claude 做白話解讀。沒有金鑰或失敗時回傳 None。"""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key or not picks:
        return None

    ov = evidence["overall"]
    payload = {
        "market": {
            "taiex_above_ma60": env["is_day_bullish"],
            "sp500_overnight_pct": round(env["night_pct"], 2),
        },
        "strategy_evidence": {
            "trades": ov["n"],
            "win_rate": round(ov["win_rate"], 3),
            "expectancy_R": round(ov["expectancy_R"], 3),
            "edge_vs_random_pct_points": round(evidence["edge_vs_random"] * 100, 1),
            "p_value_vs_random": round(evidence["p_vs_random"], 4),
            "validated": evidence["validated"],
            "ml_status": ml.get("status") if ml else None,
        },
        "picks": [
            {k: c[k] for k in (
                "code", "name", "grade", "win_prob", "ev_R", "risk_score", "risk_label",
                "stop_pct", "position_pct", "evidence_n", "foreign_lots", "trust_lots",
            )}
            for c in picks[:top_n]
        ],
    }
    prompt = (
        "你是謹慎的台股量化分析助理。以下是掃描器算出的統計結果(JSON)。"
        "請用繁體中文，簡潔寫出：1) 今日整體環境與策略證據是否可信；"
        "2) 每檔標的各一句重點(多方理由+最大風險)；3) 三點操作紀律提醒。"
        "只能引用 JSON 內的數字，不可編造資料，不可保證獲利，結尾註明僅供研究。\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": model, "max_tokens": 1500,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=90,
        )
        if res.status_code != 200:
            print(f"⚠️ AI 解讀略過 (HTTP {res.status_code})")
            return None
        return res.json()["content"][0]["text"]
    except Exception as e:
        print(f"⚠️ AI 解讀略過: {e}")
        return None
