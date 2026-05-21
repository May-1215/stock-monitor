import pandas as pd
import numpy as np
from config import RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL, MA_PERIODS, KDJ_PERIOD


def calc_ma(df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
    if periods is None:
        periods = MA_PERIODS
    for p in periods:
        df[f"ma{p}"] = df["close"].rolling(window=p).mean()
    return df


def calc_macd(df: pd.DataFrame, fast: int = None, slow: int = None, signal: int = None) -> pd.DataFrame:
    fast = fast or MACD_FAST
    slow = slow or MACD_SLOW
    signal = signal or MACD_SIGNAL
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["dif"] = ema_fast - ema_slow
    df["dea"] = df["dif"].ewm(span=signal, adjust=False).mean()
    df["macd"] = 2 * (df["dif"] - df["dea"])
    return df


def calc_rsi(df: pd.DataFrame, period: int = None) -> pd.DataFrame:
    period = period or RSI_PERIOD
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    df[f"rsi{period}"] = 100 - (100 / (1 + rs))
    return df


def calc_kdj(df: pd.DataFrame, period: int = None) -> pd.DataFrame:
    period = period or KDJ_PERIOD
    low_min = df["low"].rolling(window=period).min()
    high_max = df["high"].rolling(window=period).max()
    rsv = (df["close"] - low_min) / (high_max - low_min) * 100
    rsv = rsv.fillna(50)
    df["k"] = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    df["d"] = df["k"].ewm(alpha=1 / 3, adjust=False).mean()
    df["j"] = 3 * df["k"] - 2 * df["d"]
    return df


def calc_boll(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
    df["boll_mid"] = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()
    df["boll_upper"] = df["boll_mid"] + std_dev * std
    df["boll_lower"] = df["boll_mid"] - std_dev * std
    return df


def calc_volume_ma(df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
    if periods is None:
        periods = [5, 10]
    for p in periods:
        df[f"vol_ma{p}"] = df["volume"].rolling(window=p).mean()
    return df


def calc_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = calc_ma(df)
    df = calc_macd(df)
    df = calc_rsi(df)
    df = calc_kdj(df)
    df = calc_boll(df)
    df = calc_volume_ma(df)
    return df
