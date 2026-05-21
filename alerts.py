from config import ALERT_THRESHOLD, WATCHLIST
from stock_data import get_stock_realtime, get_all_stocks_realtime
import pandas as pd


def check_watchlist_alerts(symbols: list = None, threshold: float = None) -> list:
    symbols = symbols or WATCHLIST
    threshold = threshold or ALERT_THRESHOLD
    alerts = []
    for symbol in symbols:
        info = get_stock_realtime(symbol)
        if not info:
            continue
        pct = info.get("pct_change", 0)
        if abs(pct) >= threshold:
            alerts.append({
                "symbol": symbol,
                "name": info.get("name", ""),
                "price": info.get("price", 0),
                "pct_change": pct,
                "alert_type": "大涨" if pct > 0 else "大跌",
                "threshold": threshold,
            })
    return alerts


def scan_market_alerts(threshold: float = None, top_n: int = 30) -> pd.DataFrame:
    threshold = threshold or ALERT_THRESHOLD
    df = get_all_stocks_realtime()
    if df.empty:
        return df
    df = df[df["pct_change"].abs() >= threshold]
    df = df.sort_values("pct_change", key=abs, ascending=False).head(top_n)
    return df.reset_index(drop=True)


def get_volume_alerts(ratio: float = 2.0, top_n: int = 20) -> pd.DataFrame:
    from stock_data import get_stock_history
    df = get_all_stocks_realtime()
    if df.empty:
        return df
    results = []
    for _, row in df.iterrows():
        symbol = row["symbol"]
        try:
            hist = get_stock_history(symbol, days=10)
            if hist.empty or len(hist) < 5:
                continue
            avg_vol = hist["volume"].iloc[-5:].mean()
            cur_vol = row.get("volume", 0)
            if avg_vol > 0 and cur_vol > avg_vol * ratio:
                results.append({
                    "symbol": symbol,
                    "name": row.get("name", ""),
                    "price": row.get("price", 0),
                    "pct_change": row.get("pct_change", 0),
                    "volume_ratio": round(cur_vol / avg_vol, 2),
                    "turnover": row.get("turnover", 0),
                })
        except Exception:
            continue
        if len(results) >= top_n:
            break
    if not results:
        return pd.DataFrame()
    result_df = pd.DataFrame(results)
    return result_df.sort_values("volume_ratio", ascending=False).reset_index(drop=True)
