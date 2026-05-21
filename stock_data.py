import pandas as pd
import requests
import re
from datetime import datetime, timedelta

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
}

_TENCENT_HIST_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
_TENCENT_REALTIME_URL = "https://qt.gtimg.cn/q="
_SINA_REALTIME_URL = "https://hq.sinajs.cn/list="


def get_stock_history(symbol: str, period: str = "daily", days: int = 120) -> pd.DataFrame:
    try:
        prefix = _to_tencent_prefix(symbol)
        period_map = {"daily": "day", "weekly": "week", "monthly": "month"}
        tencent_period = period_map.get(period, "day")
        start_date = _calc_start_date(days)
        param = f"{prefix}{symbol},{tencent_period},{start_date},,{days * 2},qfq"
        params = {"param": param}
        headers = {**_HEADERS, "Referer": "https://gu.qq.com/"}
        resp = requests.get(_TENCENT_HIST_URL, params=params, headers=headers, timeout=15)
        data = resp.json()
        if data.get("code") != 0 or "data" not in data:
            return pd.DataFrame()
        stock_data = data["data"].get(f"{prefix}{symbol}", {})
        klines = stock_data.get("qfqday") or stock_data.get("day", [])
        if not klines:
            return pd.DataFrame()
        rows = []
        for item in klines:
            rows.append({
                "date": item[0],
                "open": float(item[1]),
                "close": float(item[2]),
                "high": float(item[3]),
                "low": float(item[4]),
                "volume": float(item[5]),
            })
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df["amount"] = 0.0
        df["amplitude"] = ((df["high"] - df["low"]) / df["close"].shift(1) * 100).round(2).fillna(0)
        df["pct_change"] = ((df["close"] - df["close"].shift(1)) / df["close"].shift(1) * 100).round(2).fillna(0)
        df["change"] = (df["close"] - df["close"].shift(1)).round(3).fillna(0)
        df["turnover"] = 0.0
        df = df.sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"获取股票 {symbol} 历史数据失败: {e}")
        return pd.DataFrame()


def get_stock_realtime(symbol: str) -> dict:
    try:
        prefix = _to_tencent_prefix(symbol)
        url = f"{_TENCENT_REALTIME_URL}{prefix}{symbol}"
        headers = {**_HEADERS, "Referer": "https://gu.qq.com/"}
        resp = requests.get(url, headers=headers, timeout=15)
        text = resp.text.strip()
        parts = text.split("~")
        if len(parts) < 50:
            return {}
        return {
            "symbol": symbol,
            "name": parts[1],
            "price": _safe_float(parts[3]),
            "prev_close": _safe_float(parts[4]),
            "open": _safe_float(parts[5]),
            "volume": _safe_float(parts[6]),
            "amount": _safe_float(parts[37]) if len(parts) > 37 else 0,
            "high": _safe_float(parts[33]) if len(parts) > 33 else 0,
            "low": _safe_float(parts[34]) if len(parts) > 34 else 0,
            "pct_change": _safe_float(parts[32]) if len(parts) > 32 else 0,
            "change": _safe_float(parts[31]) if len(parts) > 31 else 0,
            "turnover": _safe_float(parts[38]) if len(parts) > 38 else 0,
            "pe": _safe_float(parts[39]) if len(parts) > 39 else 0,
            "total_mv": _safe_float(parts[45]) if len(parts) > 45 else 0,
            "circ_mv": _safe_float(parts[44]) if len(parts) > 44 else 0,
            "amplitude": 0,
            "pb": 0,
        }
    except Exception as e:
        print(f"获取股票 {symbol} 实时数据失败: {e}")
        return {}


def get_all_stocks_realtime() -> pd.DataFrame:
    try:
        url = "https://qt.gtimg.cn/q=sh000001"
        headers = {**_HEADERS, "Referer": "https://gu.qq.com/"}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return pd.DataFrame()
        return _get_all_stocks_sina()
    except Exception as e:
        print(f"获取全市场实时数据失败: {e}")
        return pd.DataFrame()


def _get_all_stocks_sina() -> pd.DataFrame:
    try:
        all_rows = []
        for page in range(1, 80):
            codes = _get_stock_list_page_sina(page)
            if not codes:
                break
            code_str = ",".join(codes)
            url = f"{_SINA_REALTIME_URL}{code_str}"
            headers = {**_HEADERS, "Referer": "https://finance.sina.com.cn/"}
            resp = requests.get(url, headers=headers, timeout=15)
            lines = resp.text.strip().split("\n")
            for line in lines:
                info = _parse_sina_realtime(line)
                if info:
                    all_rows.append(info)
        return pd.DataFrame(all_rows)
    except Exception as e:
        print(f"新浪全市场数据获取失败: {e}")
        return pd.DataFrame()


def _get_stock_list_page_sina(page: int) -> list:
    try:
        size = 80
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
        params = {
            "page": page,
            "num": size,
            "sort": "changepercent",
            "asc": 0,
            "node": "hs_a",
            "symbol": "",
            "_s_r_a": "page",
        }
        headers = {**_HEADERS, "Referer": "https://finance.sina.com.cn/"}
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        data = resp.json()
        if not data:
            return []
        codes = []
        for item in data:
            code = item.get("code", "")
            if code:
                prefix = "sh" if code.startswith("6") else "sz"
                codes.append(f"{prefix}{code}")
        return codes
    except Exception:
        return []


def _parse_sina_realtime(line: str) -> dict:
    try:
        match = re.search(r'hq_str_(s[hz]\d+)="(.+)"', line)
        if not match:
            return None
        symbol_with_prefix = match.group(1)
        symbol = symbol_with_prefix[2:]
        fields = match.group(2).split(",")
        if len(fields) < 32:
            return None
        return {
            "symbol": symbol,
            "name": fields[0],
            "open": _safe_float(fields[1]),
            "prev_close": _safe_float(fields[2]),
            "price": _safe_float(fields[3]),
            "high": _safe_float(fields[4]),
            "low": _safe_float(fields[5]),
            "volume": _safe_float(fields[8]),
            "amount": _safe_float(fields[9]),
            "pct_change": 0,
            "change": 0,
            "amplitude": 0,
            "turnover": 0,
            "pe": 0,
            "pb": 0,
            "total_mv": 0,
            "circ_mv": 0,
        }
    except Exception:
        return None


def search_stock(keyword: str) -> pd.DataFrame:
    try:
        df = get_all_stocks_realtime()
        if df.empty:
            return df
        mask = df["symbol"].str.contains(keyword) | df["name"].str.contains(keyword)
        return df[mask].head(20)
    except Exception as e:
        print(f"搜索股票失败: {e}")
        return pd.DataFrame()


def _to_tencent_prefix(symbol: str) -> str:
    if symbol.startswith("6"):
        return "sh"
    else:
        return "sz"


def _calc_start_date(days: int) -> str:
    start = datetime.now() - timedelta(days=days * 2)
    return start.strftime("%Y-%m-%d")


def _safe_float(val) -> float:
    if val is None or val == "-" or val == "":
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
