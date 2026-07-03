"""
Factor Engine — 计算量化因子（Features）

从 OHLCV 数据计算所有技术因子，供模型训练和信号生成。
设计原则：每个因子函数是纯函数（输入 price_df → 输出 factor_df），
便于测试和组合。

因子列表（对应文档第 3.4 节）：
  A. 动量因子:         MOMO_20, MOMO_60, MOM_RATIO
  B. 均值回归因子:     RSI_14, BB_POS, VOL_MA_RATIO
  C. 波动率/风控因子:  ATR_20, VOLATILITY_20
  D. 市场过滤器:        SPY_ABOVE_200MA（不是因子，是 enable/disable 开关）
"""

import pandas as pd
import numpy as np
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


# ===================================================================
# A. 动量因子
# ===================================================================

def momo_20(close: pd.DataFrame) -> pd.DataFrame:
    """
    短期动量：过去 20 个交易日的累计收益率。

    公式：r = (close_t / close_{t-20}) - 1
    含义：衡量最近一个月的趋势强度（正=上涨趋势，负=下跌趋势）
    """
    return close.pct_change(periods=20)


def momo_60(close: pd.DataFrame) -> pd.DataFrame:
    """
    中期动量：过去 60 个交易日的累计收益率（≈ 3 个日历月）。

    公式：r = (close_t / close_{t-60}) - 1
    含义：趋势的确认信号。60 日动量向上同时 20 日动量向上 → 趋势健康。
    """
    return close.pct_change(periods=60)


def mom_ratio(momo20: pd.DataFrame, momo60: pd.DataFrame) -> pd.DataFrame:
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


# ===================================================================
# B. 均值回归因子
# ===================================================================

def rsi_14(close: pd.DataFrame, window: int = 14) -> pd.DataFrame:
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
    close: pd.DataFrame,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
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


def vol_ma_ratio(volume: pd.DataFrame, window: int = 20) -> pd.DataFrame:
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


# ===================================================================
# C. 波动率因子
# ===================================================================

def atr_20(
    high: pd.DataFrame,
    low: pd.DataFrame,
    close: pd.DataFrame,
    window: int = 20,
) -> pd.DataFrame:
    """
    平均真实波幅（Average True Range）。

    公式：
      tr_t = max(
        high_t - low_t,            # 当日波幅
        |high_t - close_{t-1}|,    # 当日最高 vs 前日收盘
        |low_t - close_{t-1}|      # 当日最低 vs 前日收盘
      )
      atr = rolling_mean(tr, 20)

    含义：衡量波动水平，用于仓位大小（volatility scaling）。
    """
    prev_close = close.shift(1)
    tr1 = (high - low).values
    tr2 = (high - prev_close).abs().values
    tr3 = (low - prev_close).abs().values

    tr_values = np.maximum(tr1, np.maximum(tr2, tr3))
    tr = pd.DataFrame(tr_values, index=close.index, columns=close.columns)

    return tr.rolling(window=window, min_periods=window).mean()


def volatility_20(close: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    日收益率的标准差（20 日）。

    公式：vol = rolling_std(daily_return, 20)
    含义：和 ATR 类似，但用收益率而非绝对价格，更适合横截面比较。
    """
    daily_ret = close.pct_change()
    return daily_ret.rolling(window=window, min_periods=window).std()


# ===================================================================
# D. 市场状态过滤器
# ===================================================================

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


# ===================================================================
# 因子组装器
# ===================================================================

FACTOR_NAMES = [
    "MOMO_20",
    "MOMO_60",
    "MOM_RATIO",
    "RSI_14",
    "BB_POS",
    "VOL_MA_RATIO",
    "ATR_20_NORM",   # ATR 除以收盘价，使其在不同价格水平间可比
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

    logger.info(f"📊 计算 {len(FACTOR_NAMES)} 个因子，{close.shape[1]} 个标的，{close.shape[0]} 个交易日")

    factors = {}

    for ticker in close.columns:
        tk_close = close[ticker].dropna()
        tk_volume = volume[ticker].dropna()
        tk_high = high[ticker].dropna()
        tk_low = low[ticker].dropna()

        if len(tk_close) < 60:
            logger.warning(f"⚠️  {ticker} 数据不足（{len(tk_close)} 天），跳过因子计算")
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


# ===================================================================
# 因子质量检查
# ===================================================================

def validate_factors(factor_df: pd.DataFrame) -> pd.DataFrame:
    """
    验证因子的值是否在合理范围内。

    返回一个摘要 DataFrame: ticker | factor | pass | nan_pct | min_val | max_val | notes
    """
    RANGES = {
        "MOMO_20": (-0.5, 0.5),
        "MOMO_60": (-0.8, 0.8),
        "MOM_RATIO": (-5.0, 5.0),
        "RSI_14": (0, 100),
        "BB_POS": (-0.1, 1.1),
        "VOL_MA_RATIO": (0, 10),
        "ATR_20_NORM": (0, 0.2),
        "VOLATILITY_20": (0, 0.1),
    }

    rows = []
    tickers = factor_df.columns.get_level_values(0).unique()
    factors = factor_df.columns.get_level_values(1).unique()

    for ticker in tickers:
        for factor in factors:
            try:
                series = factor_df[(ticker, factor)].dropna()
            except KeyError:
                continue

            if len(series) == 0:
                rows.append({
                    "ticker": ticker,
                    "factor": factor,
                    "pass": False,
                    "nan_pct": 1.0,
                    "min_val": np.nan,
                    "max_val": np.nan,
                    "notes": "全部为 NaN",
                })
                continue

            nan_pct = 1 - len(series) / len(factor_df[(ticker, factor)])
            min_v, max_v = series.min(), series.max()
            lo, hi = RANGES.get(factor, (-np.inf, np.inf))
            in_range = (lo <= min_v) and (max_v <= hi)

            notes = []
            if nan_pct > 0.3:
                notes.append(f"缺失 {nan_pct:.0%}")
            if not in_range:
                notes.append(f"范围异常 [{min_v:.2f}, {max_v:.2f}] (应在 [{lo}, {hi}])")

            rows.append({
                "ticker": ticker,
                "factor": factor,
                "pass": in_range and (nan_pct < 0.3),
                "nan_pct": round(nan_pct, 3),
                "min_val": round(min_v, 4),
                "max_val": round(max_v, 4),
                "notes": "; ".join(notes) if notes else "✅",
            })

    report = pd.DataFrame(rows)

    passed = report["pass"].sum()
    failed = (~report["pass"]).sum()
    logger.info(f"📋 因子验证: {passed} 通过, {failed} 有问题")

    failed_rows = report[~report["pass"]]
    if len(failed_rows) > 0:
        logger.warning("以下因子验证未通过:")
        for _, row in failed_rows.iterrows():
            logger.warning(f"  [{row.ticker}] {row.factor}: {row.notes}")

    return report


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