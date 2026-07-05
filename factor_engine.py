#!/usr/bin/env python3
"""
factor_engine.py — 因子计算入口脚本

用法:
  python factor_engine.py                    # 下载最新数据并计算因子
  python factor_engine.py --cache            # 用缓存的 parquet 数据计算因子
  python factor_engine.py --validate-only    # 只做因子验证，不重新计算
"""

import sys
import logging
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("factor_engine")

from src.data.fetcher import (
    fetch_all_data,
    extract_close_matrix,
    extract_volume_matrix,
)
from src.factors import build_factor_panel, validate_factors


def main():
    use_cache = "--cache" in sys.argv[1:]

    logger.info("📥 加载数据...")
    df = fetch_all_data(force_refresh=not use_cache)

    if df.empty:
        logger.error("❌ 无数据可用")
        sys.exit(1)

    closes = extract_close_matrix(df)
    volumes = extract_volume_matrix(df)

    logger.info(f"📊 数据: {closes.shape[0]} 天 × {len(closes.columns)} 个标的")

    logger.info("🔢 计算因子...")
    factors = build_factor_panel(closes, volumes)

    logger.info("✅ 因子计算完成")
    logger.info(f"   形状: {factors.shape}")

    latest = factors.iloc[-1].dropna()
    logger.info(f"   最新交易日因子值（部分）:")
    for idx, val in latest.head(10).items():
        ticker, factor = idx
        logger.info(f"     [{ticker}] {factor} = {val:.4f}")

    report_file = "data/factor_validation.csv"
    v_report = validate_factors(factors)
    v_report.to_csv(report_file, index=False)
    logger.info(f"💾 因子验证报告已保存到 {report_file}")


if __name__ == "__main__":
    main()