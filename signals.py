import pandas as pd
import numpy as np
from technical_indicators import calc_all_indicators


def analyze_buy_signals(df: pd.DataFrame) -> list:
    if df.empty or len(df) < 30:
        return []
    df = calc_all_indicators(df)
    signals = []
    last = df.iloc[-1]
    prev = df.iloc[-2]
    score = 0
    reasons = []

    if _ma_golden_cross(df):
        score += 2
        reasons.append("MA金叉: 短期均线上穿长期均线")

    if _macd_golden_cross(df):
        score += 2
        reasons.append("MACD金叉: DIF上穿DEA")

    if _kdj_oversold(df):
        score += 1
        reasons.append("KDJ超卖: J值从低位回升")

    if _rsi_oversold(df):
        score += 1
        reasons.append("RSI超卖: RSI从低位回升")

    if _volume_breakout(df):
        score += 1
        reasons.append("放量突破: 成交量显著放大")

    if _boll_lower_support(df):
        score += 1
        reasons.append("布林下轨支撑: 价格触及下轨反弹")

    if _price_above_ma5(df):
        score += 1
        reasons.append("站上5日均线: 短期趋势转强")

    if score >= 3:
        signals.append({
            "type": "buy",
            "score": score,
            "reasons": reasons,
            "price": last["close"],
            "date": str(last["date"]) if "date" in df.columns else "",
        })

    return signals


def analyze_sell_signals(df: pd.DataFrame) -> list:
    if df.empty or len(df) < 30:
        return []
    df = calc_all_indicators(df)
    signals = []
    last = df.iloc[-1]
    prev = df.iloc[-2]
    score = 0
    reasons = []

    if _ma_death_cross(df):
        score += 2
        reasons.append("MA死叉: 短期均线下穿长期均线")

    if _macd_death_cross(df):
        score += 2
        reasons.append("MACD死叉: DIF下穿DEA")

    if _kdj_overbought(df):
        score += 1
        reasons.append("KDJ超买: J值从高位回落")

    if _rsi_overbought(df):
        score += 1
        reasons.append("RSI超买: RSI从高位回落")

    if _boll_upper_pressure(df):
        score += 1
        reasons.append("布林上轨压力: 价格触及上轨回落")

    if _price_below_ma5(df):
        score += 1
        reasons.append("跌破5日均线: 短期趋势转弱")

    if _volume_shrink_up(df):
        score += 1
        reasons.append("缩量上涨: 上涨动力不足")

    if score >= 3:
        signals.append({
            "type": "sell",
            "score": score,
            "reasons": reasons,
            "price": last["close"],
            "date": str(last["date"]) if "date" in df.columns else "",
        })

    return signals


def scan_buy_opportunities(stocks_df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    from stock_data import get_stock_history
    results = []
    total = len(stocks_df)
    for idx, row in stocks_df.iterrows():
        symbol = row["symbol"]
        name = row.get("name", "")
        try:
            hist = get_stock_history(symbol, days=90)
            if hist.empty or len(hist) < 30:
                continue
            buy_signals = analyze_buy_signals(hist)
            if buy_signals:
                sig = buy_signals[0]
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "price": sig["price"],
                    "score": sig["score"],
                    "reasons": "；".join(sig["reasons"]),
                    "pct_change": row.get("pct_change", 0),
                    "turnover": row.get("turnover", 0),
                })
        except Exception:
            continue
    if not results:
        return pd.DataFrame()
    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values("score", ascending=False).head(top_n).reset_index(drop=True)
    return result_df


def _ma_golden_cross(df: pd.DataFrame) -> bool:
    if "ma5" not in df.columns or "ma10" not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev["ma5"] <= prev["ma10"] and last["ma5"] > last["ma10"]


def _ma_death_cross(df: pd.DataFrame) -> bool:
    if "ma5" not in df.columns or "ma10" not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev["ma5"] >= prev["ma10"] and last["ma5"] < last["ma10"]


def _macd_golden_cross(df: pd.DataFrame) -> bool:
    if "dif" not in df.columns or "dea" not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev["dif"] <= prev["dea"] and last["dif"] > last["dea"]


def _macd_death_cross(df: pd.DataFrame) -> bool:
    if "dif" not in df.columns or "dea" not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev["dif"] >= prev["dea"] and last["dif"] < last["dea"]


def _kdj_oversold(df: pd.DataFrame) -> bool:
    if "j" not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev["j"] < 20 and last["j"] > 20


def _kdj_overbought(df: pd.DataFrame) -> bool:
    if "j" not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev["j"] > 80 and last["j"] < 80


def _rsi_oversold(df: pd.DataFrame) -> bool:
    col = "rsi14"
    if col not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev[col] < 30 and last[col] > 30


def _rsi_overbought(df: pd.DataFrame) -> bool:
    col = "rsi14"
    if col not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev[col] > 70 and last[col] < 70


def _volume_breakout(df: pd.DataFrame) -> bool:
    if "vol_ma5" not in df.columns:
        return False
    last = df.iloc[-1]
    return last["volume"] > last["vol_ma5"] * 1.5


def _boll_lower_support(df: pd.DataFrame) -> bool:
    if "boll_lower" not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev["close"] <= prev["boll_lower"] and last["close"] > last["boll_lower"]


def _boll_upper_pressure(df: pd.DataFrame) -> bool:
    if "boll_upper" not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev["close"] >= prev["boll_upper"] and last["close"] < last["boll_upper"]


def _price_above_ma5(df: pd.DataFrame) -> bool:
    if "ma5" not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev["close"] <= prev["ma5"] and last["close"] > last["ma5"]


def _price_below_ma5(df: pd.DataFrame) -> bool:
    if "ma5" not in df.columns:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return prev["close"] >= prev["ma5"] and last["close"] < last["ma5"]


def _volume_shrink_up(df: pd.DataFrame) -> bool:
    if "vol_ma5" not in df.columns:
        return False
    last = df.iloc[-1]
    return last["close"] > df.iloc[-2]["close"] and last["volume"] < last["vol_ma5"] * 0.7
