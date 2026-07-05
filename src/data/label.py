"""
标签计算 — 远期收益标签
"""

import pandas as pd
import logging
from typing import List

logger = logging.getLogger(__name__)

DEFAULT_PERIODS = [5, 10, 21]


def compute_forward_returns(
    close: pd.DataFrame,
    periods: List[int] = None,
) -> pd.DataFrame:
    """
    计算远期收益标签。

    Parameters
    ----------
    close : pd.DataFrame
        收盘价矩阵（行=日期，列=ticker）。
    periods : list[int]
        远期收益周期（交易日），默认 [5, 10, 21]。

    Returns
    -------
    pd.DataFrame
        MultiIndex 列: (ticker, forward_return_{period})。
        行索引同 close.index。
    """
    if periods is None:
        periods = DEFAULT_PERIODS

    logger.info(
        f"🏷️  计算远期收益: periods={periods}, "
        f"{close.shape[1]} 个标的, {close.shape[0]} 天"
    )

    dfs = []
    for p in periods:
        fwd = close.shift(-p) / close - 1
        fwd.columns = pd.MultiIndex.from_product(
            [fwd.columns, [f"forward_return_{p}"]],
            names=["ticker", "factor"],
        )
        dfs.append(fwd)

    result = pd.concat(dfs, axis=1).sort_index(axis=1)
    logger.info(f"✅ 远期收益计算完成: {result.shape}")
    return result