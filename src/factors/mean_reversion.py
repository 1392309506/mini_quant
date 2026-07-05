"""
均值回归因子 — 超买超卖信号

B1. RSI_14:      相对强弱指标
B2. BB_POS:      布林带位置
B3. VOL_MA_RATIO: 成交量 / 均量比
"""

import pandas as pd
import numpy as np


def rsi_14(close: pd.Series, window: int = 14) -> pd.Series:
    """
    相对强弱指标 RSI-14。

    公式：
      gain = max(close_t - close_{t-1}, 0)
      loss = max(close_{t-1} - close_t, 0)
      avg_gain = rolling_mean(gain, 14)
      avg_loss = rolling_mean(loss, 14)
      rs = avg_gain / avg_loss
      rsi = 100 - 100 / (1 + rs)

    含义：
      - < 30：超卖 → 可能反弹（做多信号）
      - > 70：超买 → 可能回调（做空/减仓信号）

    Edge case: 如果 avg_loss = 0（持续上涨），RSI = 100；
              如果 avg_gain = 0（持续下跌），RSI = 0。
    """
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    zero_loss_mask = (avg_loss == 0) & (avg_gain > 0)
    rsi[zero_loss_mask] = 100
    rsi[(avg_gain == 0) & (avg_loss == 0)] = 50

    return rsi


def bb_position(
    close: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.Series:
    """
    布林带位置：收盘价在布林带中的相对位置。

    公式：
      ma = rolling_mean(close, 20)
      std = rolling_std(close, 20)
      bb_pos = (close - bb_lower) / (bb_upper - bb_lower)

    含义：
      - ≈ 0：在布林带下轨附近（超卖）
      - ≈ 1：在布林带上轨附近（超买）
      - > 1 / < 0：突破布林带（强趋势，均值回归失效）

    Edge case: 当上下轨间距为 0 时，位置设为 0.5。
    """
    ma = close.rolling(window=window, min_periods=window).mean()
    std = close.rolling(window=window, min_periods=window).std()

    bb_upper = ma + num_std * std
    bb_lower = ma - num_std * std

    denominator = bb_upper - bb_lower
    denominator = denominator.replace(0, np.nan)

    pos = (close - bb_lower) / denominator
    return pos.clip(-0.1, 1.1)


def vol_ma_ratio(volume: pd.Series, window: int = 20) -> pd.Series:
    """
    成交量 / 均量比——衡量当前成交量相对于近期均值的倍数。

    公式：r = volume_t / rolling_mean(volume, 20)
    含义：
      - > 1.5：放量（可能的突破/反转信号）
      - < 0.5：缩量（市场犹豫/盘整）
      - 1.0：正常

    Edge case: 均量为 0 时，返回 NaN。
    """
    vol_ma = volume.rolling(window=window, min_periods=window).mean()
    vol_ma = vol_ma.replace(0, np.nan)
    ratio = volume / vol_ma
    return ratio.clip(0, 10)