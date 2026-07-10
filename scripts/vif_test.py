#!/usr/bin/env python3
"""
VIF 多重共线性测试

计算 13 个因子之间的 VIF（方差膨胀因子），
识别高相关因子簇（波动率大类）。

用法:
  python scripts/vif_test.py                          # 默认（28只，最近 252 天）
  python scripts/vif_test.py --days 500               # 更长窗口
  python scripts/vif_test.py --output reports/vif.csv # 保存 CSV
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("vif")

import pandas as pd
import numpy as np
from src.data.fetcher import fetch_all_data, extract_close_matrix, extract_volume_matrix
from src.factors.assembly import compute_all_factors, FACTOR_NAMES


def compute_vif(panel: pd.DataFrame, max_tickers: int = 5) -> pd.DataFrame:
    """计算因子间的 VIF（逐对使用完整观测）。"""
    from sklearn.linear_model import LinearRegression

    tickers = panel.columns.get_level_values(0).unique()
    ticker_counts = {t: panel.xs(t, axis=1, level=0).dropna(how="all").shape[0]
                     for t in tickers}
    top_tickers = sorted(ticker_counts, key=ticker_counts.get, reverse=True)[:max_tickers]

    all_vifs = []
    for ticker in top_tickers:
        df = panel.xs(ticker, axis=1, level=0)
        if df.shape[0] < 30 or df.shape[1] < 3:
            continue

        vifs = {}
        for col in df.columns:
            # 每个目标因子独立：排除完全 NaN 的其他因子
            others = df.drop(columns=[col])
            valid_others = others.columns[others.notna().any()].tolist()
            if len(valid_others) < 2:
                vifs[col] = float("nan")
                continue
            sub = df[[col] + valid_others].dropna()
            if sub.shape[0] < 20:
                vifs[col] = float("nan")
                continue

            y = sub[col].values
            X = sub[valid_others].values
            X = np.column_stack([X, np.ones(X.shape[0])])
            try:
                model = LinearRegression().fit(X, y)
                residuals = y - model.predict(X)
                r2 = 1 - np.nansum(residuals ** 2) / max(np.nansum((y - y.mean()) ** 2), 1e-10)
                vif = 1 / (1 - r2) if r2 < 0.999 else float("inf")
            except Exception:
                vif = float("nan")
            vifs[col] = vif

        all_vifs.append(pd.DataFrame([vifs], index=[ticker]))

    if not all_vifs:
        logger.error("无有效数据")
        return pd.DataFrame()

    result = pd.concat(all_vifs)

    # 汇总：跨标的取均值
    summary = result.mean().round(2).to_frame("VIF_mean")
    summary["VIF_std"] = result.std().round(2)
    summary = summary.sort_values("VIF_mean", ascending=False)
    summary["risk"] = summary["VIF_mean"].apply(
        lambda x: "🔴 high" if x > 5 else ("🟡 moderate" if x > 2 else "🟢 low")
    )
    summary.index.name = "factor"
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="因子 VIF 多重共线性测试")
    parser.add_argument("--days", type=int, default=252,
                        help="计算窗口天数（默认 252，1 交易年）")
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()

    logger.info("📥 加载数据...")
    df = fetch_all_data(force_refresh=False)
    closes = extract_close_matrix(df).iloc[-args.days:]
    volumes = extract_volume_matrix(df).iloc[-args.days:]
    logger.info(f"📊 数据: {closes.shape[0]} 天 × {closes.shape[1]} 个标的")

    factor_panel = compute_all_factors(closes, volumes, closes, closes)
    logger.info(f"🔢 计算因子: {list(FACTOR_NAMES)}")

    result = compute_vif(factor_panel)
    if result.empty:
        logger.error("VIF 计算失败")
        return

    logger.info("\n" + "=" * 60)
    logger.info("VIF 多重共线性测试结果")
    logger.info("=" * 60)
    logger.info(f"数据窗口: 最近 {args.days} 天")
    logger.info("")
    logger.info(f"{'因子':<20} {'VIF均值':>8} {'VIF标准差':>10} {'风险':<10}")
    logger.info("-" * 50)
    for factor, row in result.iterrows():
        logger.info(f"{factor:<20} {row['VIF_mean']:>8.2f} {row['VIF_std']:>10.2f} {row['risk']:<10}")

    high = result[result["risk"] == "🔴 high"]
    if len(high) > 0:
        logger.info(f"\n🔴 VIF>5: {list(high.index)}")
    else:
        logger.info("\n🟢 所有因子 VIF ≤ 5，无高相关风险")

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(out, encoding="utf-8")
        logger.info(f"💾 结果已保存: {out}")


if __name__ == "__main__":
    main()