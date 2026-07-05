"""
动量因子 — 趋势跟踪信号

A. MOMO_20:  短期动量（20 日累计收益）
B. MOMO_60:  中期动量（60 日累计收益 ≈ 3 个日历月）
C. MOM_RATIO: 动量加速比（短期动量 / 长期动量绝对值）
"""

import pandas as pd
import numpy as np


def momo_20(close: pd.Series) -> pd.Series:
    """
    短期动量：过去 20 个交易日的累计收益率。

    公式：r = (close_t / close_{t-20}) - 1
    含义：衡量最近一个月的趋势强度（正=上涨趋势，负=下跌趋势）
    """
    return close.pct_change(periods=20)


def momo_60(close: pd.Series) -> pd.Series:
    """
    中期动量：过去 60 个交易日的累计收益率（≈ 3 个日历月）。

    公式：r = (close_t / close_{t-60}) - 1
    含义：趋势的确认信号。60 日动量向上同时 20 日动量向上 → 趋势健康。
    """
    return close.pct_change(periods=60)


def mom_ratio(momo20: pd.Series, momo60: pd.Series) -> pd.Series:
    """
    动量加速比：短期动量 / 长期动量绝对值。

    公式：r = momo20 / |momo60|
    含义：
      - > 1：趋势在过去 20 天加速（强趋势信号）
      - 0~1：趋势在减速
      - < 0：趋势方向不一致（需警惕）

    Edge case: 当 momo60 ≈ 0 时，ratio 趋向无穷——需要截断处理。
    """
    denom = np.abs(momo60).clip(lower=1e-8)
    ratio = momo20 / denom
    return ratio.clip(-5, 5)