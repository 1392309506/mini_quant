"""
数据预处理 — 训练数据准备与 Walk-Forward 窗口切分
"""

import pandas as pd
import numpy as np
import logging
from typing import List, Tuple, Optional

from src.data.label import compute_forward_returns, DEFAULT_PERIODS

logger = logging.getLogger(__name__)


def prepare_training_data(
    factor_panel: pd.DataFrame,
    close: pd.DataFrame,
    periods: List[int] = None,
) -> pd.DataFrame:
    """
    整合因子面板和远期收益标签为训练数据集。

    步骤:
      1. 从 close 计算 forward_returns
      2. 堆叠因子面板 → 列: [MOMO_20, ..., VOLATILITY_20], 索引: (Date, ticker)
      3. 堆叠远期收益 → 列: [forward_return_5, forward_return_10, forward_return_21]
      4. 内连接特征与标签
      5. dropna() 丢弃任何列为 NaN 的行

    Parameters
    ----------
    factor_panel : pd.DataFrame
        MultiIndex 列: (ticker, factor)，行索引=日期。
    close : pd.DataFrame
        收盘价矩阵（行=日期，列=ticker）。
    periods : list[int]
        远期收益周期。

    Returns
    -------
    pd.DataFrame
        索引: (Date, ticker) — pd.MultiIndex。
    """
    if periods is None:
        periods = DEFAULT_PERIODS

    logger.info("🔄 准备训练数据...")

    # 1. 计算远期收益
    forward_returns = compute_forward_returns(close, periods)
    logger.info(f"   远期收益 shape: {forward_returns.shape}")

    # 2. 堆叠因子面板
    try:
        features = factor_panel.stack(level="ticker", future_stack=True)
    except TypeError:
        features = factor_panel.stack(level="ticker")
    features.index.names = ["Date", "ticker"]
    logger.info(f"   堆叠后特征 shape: {features.shape}")

    # 3. 堆叠远期收益
    label_dfs = []
    for period in periods:
        label_col = f"forward_return_{period}"
        try:
            lbl = forward_returns.xs(label_col, axis=1, level=1)
        except KeyError:
            lbl_cols = [c for c in forward_returns.columns if c[1] == label_col]
            if lbl_cols:
                lbl = forward_returns[lbl_cols]
                lbl.columns = lbl.columns.droplevel(1)
            else:
                raise

        lbl_stacked = lbl.stack()
        lbl_stacked.name = label_col
        label_dfs.append(lbl_stacked)

    labels = pd.concat(label_dfs, axis=1)
    labels.index.names = ["Date", "ticker"]
    logger.info(f"   堆叠后标签 shape: {labels.shape}")

    # 4. 内连接
    data = features.join(labels, how="inner")
    logger.info(f"   合并后 shape: {data.shape}")

    # 5. 丢弃 NaN
    n_before = len(data)
    data = data.dropna()
    n_after = len(data)
    logger.info(
        f"   丢弃 NaN: {n_before - n_after} 行丢弃, {n_after} 行保留 "
        f"({n_after / n_before:.1%})"
    )

    return data


def clip_outliers(
    df: pd.DataFrame,
    feature_cols: List[str],
    std_threshold: float = 5.0,
) -> pd.DataFrame:
    """
    横截面缩尾处理——每个日期在每个特征上截断极端值。

    方法: 对每个日期，特征值在 [mean - std_threshold*std, mean + std_threshold*std]
          之外的值被截断到边界。
    """
    if std_threshold <= 0:
        return df

    df = df.copy()
    for col in feature_cols:
        if col not in df.columns:
            continue

        grouped = df.groupby(level="Date")[col]
        means = grouped.transform("mean")
        stds = grouped.transform("std").fillna(0)

        lower = means - std_threshold * stds
        upper = means + std_threshold * stds

        df[col] = df[col].clip(lower, upper)

    logger.info(
        f"✂️  缩尾处理完成: threshold={std_threshold}σ, "
        f"特征数={len(feature_cols)}"
    )
    return df


def add_cross_sectional_features(
    df: pd.DataFrame,
    feature_cols: List[str],
) -> pd.DataFrame:
    """
    添加横截面特征：排名和 Z-score，增强模型横截面区分能力。

    对每个原始因子 X，生成两个新特征：
      - X_rank: 截面排名归一化到 [0, 1]（高=该因子截面最高）
      - X_zscore: 截面 Z-score（相对位置的标准差倍数）

    Parameters
    ----------
    df : pd.DataFrame
        堆叠后的训练数据，索引 (Date, ticker)。
    feature_cols : list[str]
        要转化的原始因子列名。

    Returns
    -------
    pd.DataFrame
        添加了截面特征的副本。
    """
    df = df.copy()
    n_new = 0

    for col in feature_cols:
        if col not in df.columns:
            continue

        # 截面排名 (0~1)
        rank_col = f"{col}_rank"
        # groupby(level="Date") 对每个日期独立排名
        df[rank_col] = (
            df.groupby(level="Date")[col]
            .rank(pct=True)
        )
        n_new += 1

        # 截面 Z-score
        z_col = f"{col}_zscore"
        grouped = df.groupby(level="Date")[col]
        means = grouped.transform("mean")
        stds = grouped.transform("std").fillna(1.0)
        df[z_col] = (df[col] - means) / stds
        df[z_col] = df[z_col].clip(-5, 5)  # 截断极端 Z-score
        n_new += 1

    logger.info(
        f"📊 横截面特征已添加: {n_new} 个新特征 "
        f"(每因子 × rank + zscore)"
    )

    return df


def build_walk_forward_windows(
    dates: pd.DatetimeIndex,
    initial_train_years: float = 6.0,
    val_years: float = 1.0,
    step_years: float = 1.0,
    test_years: float = 1.5,
) -> Tuple[List[dict], dict]:
    """
    构建 Walk-Forward 滚动窗口定义。

    使用日期边界（而非索引位置），确保数据刷新后切分不变。
    """
    dates = pd.DatetimeIndex(sorted(dates))
    start = dates[0]
    end = dates[-1]

    test_start = end - pd.Timedelta(days=int(test_years * 365.25))
    val_end = test_start - pd.Timedelta(days=1)
    train_initial_end = start + pd.Timedelta(days=int(initial_train_years * 365.25))

    windows = []
    i = 0
    while True:
        train_end = train_initial_end + pd.Timedelta(days=int(i * step_years * 365.25))
        val_start = train_end + pd.Timedelta(days=1)
        val_end_cur = val_start + pd.Timedelta(days=int(val_years * 365.25))

        if val_end_cur >= test_start:
            break

        train_mask = (dates >= start) & (dates <= train_end)
        val_mask = (dates >= val_start) & (dates <= val_end_cur)

        if train_mask.sum() < 20 or val_mask.sum() < 5:
            break

        train_actual_end = dates[train_mask][-1]
        val_actual_start = dates[val_mask][0] if val_mask.any() else val_start
        val_actual_end = dates[val_mask][-1] if val_mask.any() else val_end_cur

        windows.append({
            "name": f"W{i + 1}",
            "train_start": start,
            "train_end": train_actual_end,
            "val_start": val_actual_start,
            "val_end": val_actual_end,
        })
        i += 1

    test_train_end = windows[-1]["val_end"] if windows else val_end
    test_mask = (dates >= test_start) & (dates <= end)
    test_actual_start = dates[test_mask][0] if test_mask.any() else test_start

    test_window = {
        "name": "test",
        "train_start": start,
        "train_end": test_train_end,
        "test_start": test_actual_start,
        "test_end": dates[-1],
    }

    logger.info(
        f"📅 Walk-Forward 窗口: {len(windows)} 个验证窗口 + 1 个测试集"
    )
    for w in windows:
        logger.info(
            f"   {w['name']}: train {w['train_start'].date()} → "
            f"{w['train_end'].date()}, "
            f"val {w['val_start'].date()} → {w['val_end'].date()}"
        )
    logger.info(
        f"   测试集: train {test_window['train_start'].date()} → "
        f"{test_window['train_end'].date()}, "
        f"test {test_window['test_start'].date()} → "
        f"{test_window['test_end'].date()}"
    )

    return windows, test_window


def split_by_window(
    data: pd.DataFrame,
    window: dict,
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], str]:
    """按窗口定义切分数据。"""
    dates = data.index.get_level_values("Date")
    is_test = "test_start" in window and "val_start" not in window

    if is_test:
        train_mask = (dates >= window["train_start"]) & (dates <= window["train_end"])
        test_mask = (dates >= window["test_start"]) & (dates <= window["test_end"])
        return data.loc[train_mask], data.loc[test_mask], "test"
    else:
        train_mask = (dates >= window["train_start"]) & (dates <= window["train_end"])
        val_mask = (dates >= window["val_start"]) & (dates <= window["val_end"])
        return data.loc[train_mask], data.loc[val_mask], "val"