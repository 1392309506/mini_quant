"""
因子组装器 — 从 OHLCV 数据计算所有因子
"""

import logging
from typing import Optional

import pandas as pd

from src.factors.momentum import momo_20, momo_60, mom_ratio
from src.factors.mean_reversion import rsi_14, bb_position, vol_ma_ratio
from src.factors.volatility import atr_20, volatility_20
from src.factors.validation import validate_factors

logger = logging.getLogger(__name__)

FACTOR_NAMES = [
    "MOMO_20",
    "MOMO_60",
    "MOM_RATIO",
    "RSI_14",
    "BB_POS",
    "VOL_MA_RATIO",
    "ATR_20_NORM",
    "VOLATILITY_20",
]


def compute_all_factors(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    high: Optional[pd.DataFrame] = None,
    low: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    计算所有因子，返回 MultiIndex DataFrame。

    Parameters
    ----------
    close : pd.DataFrame
        收盘价矩阵（行=日期，列=ticker）
    volume : pd.DataFrame
        成交量矩阵（行=日期，列=ticker）
    high : pd.DataFrame, optional
        最高价矩阵。若不提供，用 close * 1.01 近似
    low : pd.DataFrame, optional
        最低价矩阵。若不提供，用 close * 0.99 近似

    Returns
    -------
    pd.DataFrame
        MultiIndex columns: (ticker, factor_name)
        行 = 日期

    Raises
    ------
    ValueError
        如果 close 或 volume 为空
    """
    if close.empty or volume.empty:
        raise ValueError("close 和 volume 必须是非空的 DataFrame")

    if high is None:
        high = close * 1.01
    if low is None:
        low = close * 0.99

    assert close.index.equals(volume.index), "close 和 volume 的索引不一致"
    assert close.columns.equals(volume.columns), "close 和 volume 的列不一致"

    logger.info(
        f"📊 计算 {len(FACTOR_NAMES)} 个因子，{close.shape[1]} 个标的，"
        f"{close.shape[0]} 个交易日"
    )

    factors = {}

    for ticker in close.columns:
        tk_close = close[ticker].dropna()
        tk_volume = volume[ticker].dropna()
        tk_high = high[ticker].dropna()
        tk_low = low[ticker].dropna()

        if len(tk_close) < 60:
            logger.warning(
                f"⚠️  {ticker} 数据不足（{len(tk_close)} 天），跳过因子计算"
            )
            continue

        f = pd.DataFrame(index=tk_close.index)

        f["MOMO_20"] = momo_20(tk_close)
        f["MOMO_60"] = momo_60(tk_close)
        f["MOM_RATIO"] = mom_ratio(f["MOMO_20"], f["MOMO_60"])
        f["RSI_14"] = rsi_14(tk_close)
        f["BB_POS"] = bb_position(tk_close)
        f["VOL_MA_RATIO"] = vol_ma_ratio(tk_volume)
        f["ATR_20_NORM"] = atr_20(tk_high, tk_low, tk_close) / tk_close
        f["VOLATILITY_20"] = volatility_20(tk_close)

        f.columns = [f"{ticker}|{col}" for col in f.columns]
        factors[ticker] = f

    if not factors:
        raise ValueError("没有任何 ticker 能成功计算因子——数据可能全部无效")

    result = pd.concat(factors.values(), axis=1)
    result.columns = pd.MultiIndex.from_tuples(
        [col.split("|") for col in result.columns],
        names=["ticker", "factor"],
    )

    result = result.sort_index(axis=1)

    logger.info(f"✅ 因子计算完成: {result.shape}")
    return result


def build_factor_panel(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    high: Optional[pd.DataFrame] = None,
    low: Optional[pd.DataFrame] = None,
    validate: bool = True,
) -> pd.DataFrame:
    """
    一键计算并验证所有因子。

    Parameters
    ----------
    close, volume, high, low : pd.DataFrame
        OHLC 数据矩阵
    validate : bool
        是否执行因子质量检查

    Returns
    -------
    pd.DataFrame
        MultiIndex columns: (ticker, factor_name)
    """
    factors = compute_all_factors(close, volume, high, low)

    if validate:
        v_report = validate_factors(factors)
        if v_report["pass"].sum() < v_report.shape[0] * 0.8:
            logger.warning("⚠️  因子通过率 < 80%，部分数据可能不可靠")

    return factors