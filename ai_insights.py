"""
ai_insights.py - 白話洞察（規則式）。v3 已移除 Claude API 解讀，不再需要 ANTHROPIC_API_KEY。
"""

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
