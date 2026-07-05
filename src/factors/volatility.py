"""
波动率因子 — 风险衡量

C1. ATR_20:       平均真实波幅（价格绝对值）
C2. VOLATILITY_20: 日收益率标准差（横截面可比）
"""

import pandas as pd
import numpy as np


def atr_20(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 20,
) -> pd.Series:
    """
    平均真实波幅（Average True Range）。

    公式：
      tr_t = max(
        high_t - low_t,            # 当日波幅
        |high_t - close_{t-1}|,   # 当日最高 vs 前日收盘
        |low_t - close_{t-1}|     # 当日最低 vs 前日收盘
      )
      atr = rolling_mean(tr, 20)

    含义：衡量波动水平，用于仓位大小（volatility scaling）。
    """
    prev_close = close.shift(1)
    tr1 = (high - low).values
    tr2 = (high - prev_close).abs().values
    tr3 = (low - prev_close).abs().values

    tr_values = np.maximum(tr1, np.maximum(tr2, tr3))
    tr = pd.Series(tr_values, index=close.index, name="tr")

    return tr.rolling(window=window, min_periods=window).mean()


def volatility_20(close: pd.Series, window: int = 20) -> pd.Series:
    """
    日收益率的标准差（20 日）。

    公式：vol = rolling_std(daily_return, 20)
    含义：和 ATR 类似，但用收益率而非绝对价格，更适合横截面比较。
    """
    daily_ret = close.pct_change()
    return daily_ret.rolling(window=window, min_periods=window).std()