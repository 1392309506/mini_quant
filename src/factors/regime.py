"""
市场状态过滤器 — 策略级开关

D. market_regime_filter: SPY 在 200 日均线上方还是下方

这不是一个用于预测的因子，而是风险管理开关。
"""

import pandas as pd


def market_regime_filter(
    spy_close: pd.Series,
    ma_window: int = 200,
) -> pd.Series:
    """
    市场状态过滤器：SPY 在 200 日均线上方还是下方。

    返回：布尔值 Series（True = 允许做多，False = 熊市，减仓或空仓）

    这是一个策略级别的开关，不是因子——不用于预测，用于风险管理。
    """
    ma200 = spy_close.rolling(window=ma_window, min_periods=ma_window).mean()
    return spy_close > ma200