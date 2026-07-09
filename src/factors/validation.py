"""
因子质量检查 — 验证因子值是否在合理范围内
"""

import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 每个因子的合理值域
RANGES = {
    "MOMO_20": (-0.8, 0.8),      # 放宽：20日动量在极端行情可达±70%+
    "MOMO_60": (-1.5, 1.5),      # 放宽：60日动量累积效应更强
    "MOM_RATIO": (-5.0, 5.0),
    "RSI_14": (0, 100),
    "BB_POS": (-0.1, 1.1),
    "VOL_MA_RATIO": (0, 10),
    "ATR_20_NORM": (0, 0.3),     # 放宽：ATR/Close 在波动率骤升时可达 0.25
    "VOLATILITY_20": (0, 0.15),  # 放宽：20日波动率在恐慌/暴涨阶段可超 10%
    "BB_WIDTH": (0, 1),
    "HIGH_LOW_RATIO": (0, 0.3),
    "CHAIKIN_MF": (-1, 1),
    "ULCER_INDEX": (0, 0.3),
    "MAX_DD_60": (-1, 0),
}


def validate_factors(factor_df: pd.DataFrame) -> pd.DataFrame:
    """
    验证因子的值是否在合理范围内。

    返回一个摘要 DataFrame: ticker | factor | pass | nan_pct | min_val | max_val | notes
    """
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
                notes.append(
                    f"范围异常 [{min_v:.2f}, {max_v:.2f}] (应在 [{lo}, {hi}])"
                )

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