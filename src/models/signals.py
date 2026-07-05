"""
训练信号生成 — 从模型预测生成交易信号

遵循 CONSTITUTION.md 约束：
  - 入场: 信号发出 → 次日开盘（open[t+1]）
  - 持仓: 最短 5 天，最长 30 天
  - 信号频率: 每周最多 2 次调仓
"""

import logging
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def generate_rebalance_calendar(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    max_per_week: int = 2,
) -> pd.DatetimeIndex:
    """
    生成调仓日期日历。

    策略：每周最多 2 次调仓，优先选择周一和周四。
    """
    dates = pd.bdate_range(start_date, end_date, freq="C", weekmask="Mon Thu")
    return dates


def generate_entry_signals(
    predictions: pd.DataFrame,
    rebalance_dates: pd.DatetimeIndex,
    close: pd.DataFrame,
    top_k: int = 5,
    min_pred: float = 0.0,
) -> pd.DataFrame:
    """
    在每个调仓日从预测生成入场信号。
    """
    entries = pd.DataFrame(False, index=close.index, columns=close.columns)

    if isinstance(predictions.index, pd.MultiIndex):
        pred_by_date = predictions.groupby(level="Date")
    else:
        pred_by_date = predictions.groupby("Date")

    for rdate in rebalance_dates:
        if rdate not in close.index:
            continue

        try:
            if isinstance(predictions.index, pd.MultiIndex):
                date_preds_df = predictions.loc[rdate]
            else:
                date_preds_df = predictions[predictions["Date"] == rdate]
        except (KeyError, TypeError):
            continue

        if date_preds_df.empty:
            continue

        candidates = date_preds_df[date_preds_df["pred"] > min_pred]
        if candidates.empty:
            continue

        candidates = candidates.sort_values("pred", ascending=False)
        if isinstance(candidates.index, pd.MultiIndex):
            selected = candidates.index.get_level_values(-1)[:top_k].tolist()
        else:
            selected = candidates.index[:top_k].tolist()

        next_idx = close.index.get_loc(rdate) + 1
        if next_idx < len(close.index):
            entry_date = close.index[next_idx]
            for ticker in selected:
                if ticker in entries.columns:
                    entries.loc[entry_date, ticker] = True

    n_entries = entries.sum().sum()
    logger.info(
        f"📈 入场信号生成: {len(rebalance_dates)} 个调仓日, {n_entries} 笔入场"
    )

    return entries


def generate_exit_signals(
    entries: pd.DataFrame,
    min_hold: int = 5,
    max_hold: int = 30,
) -> pd.DataFrame:
    """
    基于持仓期限生成出场信号。
    """
    exits = pd.DataFrame(False, index=entries.index, columns=entries.columns)

    for ticker in entries.columns:
        entry_dates = entries.index[entries[ticker]]
        for entry_date in entry_dates:
            entry_idx = entries.index.get_loc(entry_date)

            exit_early_idx = entry_idx + min_hold
            if exit_early_idx < len(entries.index):
                exits.iloc[exit_early_idx, exits.columns.get_loc(ticker)] = True

            exit_late_idx = entry_idx + max_hold
            if exit_late_idx < len(entries.index):
                exits.iloc[exit_late_idx, exits.columns.get_loc(ticker)] = True

    n_exits = exits.sum().sum()
    logger.info(f"📉 出场信号生成: {n_exits} 笔出场")
    return exits


def filter_by_market_regime(
    entries: pd.DataFrame,
    spy_close: pd.Series,
    ma_window: int = 200,
) -> pd.DataFrame:
    """
    市场状态过滤器：SPY 在 200 日均线之上时才允许做多。
    """
    ma = spy_close.rolling(window=ma_window, min_periods=ma_window).mean()
    regime_ok = spy_close > ma

    filtered = entries.copy()
    for date in entries.index:
        if date in regime_ok.index and not regime_ok[date]:
            filtered.loc[date] = False

    n_blocked = entries.sum().sum() - filtered.sum().sum()
    if n_blocked > 0:
        logger.info(f"🛑 市场状态过滤器阻挡了 {n_blocked} 笔入场（SPY < MA200）")

    return filtered