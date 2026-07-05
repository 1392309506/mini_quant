#!/usr/bin/env python3
"""
train_model.py — 模型训练入口脚本

用法:
  python train_model.py                          # 完整训练
  python train_model.py --quick                  # 快速测试（5 个标的）
  python train_model.py --target 21              # 预测 forward_return_21
  python train_model.py --load <exp_id>          # 加载已有实验
"""

import sys
import logging
from typing import Optional

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train_model")

from src.data.fetcher import (
    fetch_all_data,
    extract_close_matrix,
    extract_volume_matrix,
)
from src.factors import build_factor_panel
from src.data.label import compute_forward_returns, DEFAULT_PERIODS
from src.data.preprocess import (
    prepare_training_data,
    clip_outliers,
    build_walk_forward_windows,
)
from src.models.config import (
    FEATURE_COLS,
    DEFAULT_TARGET,
    DEFAULT_LGBM_PARAMS,
    NUM_BOOST_ROUND,
    EARLY_STOPPING_ROUNDS,
    WF_INITIAL_TRAIN_YEARS,
    WF_VAL_YEARS,
    WF_STEP_YEARS,
    WF_TEST_YEARS,
    CLIP_STD_THRESHOLD,
)
from src.models.trainer import train_walk_forward
from src.experiment import save_experiment, load_experiment


def parse_args():
    """解析命令行参数"""
    args = {
        "quick": "--quick" in sys.argv[1:],
        "load_mode": "--load" in sys.argv[1:],
        "target": DEFAULT_TARGET,
        "load_id": None,
    }

    for i, arg in enumerate(sys.argv):
        if arg == "--target" and i + 1 < len(sys.argv):
            period = sys.argv[i + 1]
            args["target"] = f"forward_return_{period}"
        if arg == "--load" and i + 1 < len(sys.argv):
            args["load_id"] = sys.argv[i + 1]

    return args


def print_summary(results: dict):
    """打印训练结果摘要"""
    metrics = results.get("metrics")
    if metrics is None or len(metrics) == 0:
        logger.warning("⚠️  无有效的训练窗口")
        return

    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 训练摘要")
    logger.info("=" * 60)

    logger.info(
        f"{'窗口':<8} {'Train RMSE':<14} {'Val RMSE':<14} {'Best Iter':<12}"
    )
    logger.info("-" * 50)
    for _, row in metrics.iterrows():
        logger.info(
            f"{row['window']:<8} {row['train_rmse']:<14.6f} "
            f"{row['val_rmse']:<14.6f} {int(row['best_iteration']):<12}"
        )

    logger.info("")
    logger.info(f"平均验证 RMSE: {metrics['val_rmse'].mean():.6f}")

    importance = results.get("importance")
    if importance is not None and len(importance) > 0:
        logger.info("")
        logger.info("特征重要性（按 avg gain 排序）:")
        top = (
            importance.groupby("feature")["gain"]
            .mean()
            .sort_values(ascending=False)
            .head(5)
        )
        for feat, gain in top.items():
            logger.info(f"  {feat:<16} {gain:.2f}")

    pred_oos = results.get("pred_oos")
    if pred_oos is not None and len(pred_oos) > 0:
        logger.info("")
        logger.info(f"OOS 预测统计: {len(pred_oos)} 行")
        logger.info(f"  pred mean={pred_oos['pred'].mean():.4f}")
        logger.info(f"  pred std={pred_oos['pred'].std():.4f}")
        actual = pred_oos["actual"].dropna()
        if len(actual) > 0:
            logger.info(f"  actual mean={actual.mean():.4f}")
            logger.info(f"  actual std={actual.std():.4f}")


def main():
    args = parse_args()

    # 加载模式
    if args["load_mode"] and args["load_id"]:
        from src.config import EXPERIMENTS_DIR

        exp_path = EXPERIMENTS_DIR / args["load_id"]
        if not exp_path.exists():
            logger.error(f"❌ 实验不存在: {exp_path}")
            sys.exit(1)
        exp = load_experiment(str(exp_path))
        print_summary({
            "metrics": exp["metrics"],
            "importance": exp["importance"],
            "pred_oos": exp["pred_oos"],
        })
        return

    # 1. 加载数据
    logger.info("📥 加载数据...")
    df = fetch_all_data(force_refresh=False)

    if df.empty:
        logger.error("❌ 无数据可用")
        sys.exit(1)

    closes = extract_close_matrix(df)
    volumes = extract_volume_matrix(df)
    highs = df.xs("High", axis=1, level=1).sort_index(axis=1).sort_index()
    lows = df.xs("Low", axis=1, level=1).sort_index(axis=1).sort_index()

    logger.info(f"📊 数据: {closes.shape[0]} 天 × {closes.shape[1]} 个标的")

    # --quick 模式：只保留前 5 个标的
    if args["quick"]:
        tickers = closes.columns[:5].tolist()
        logger.info(f"⚡ 快速模式: 仅使用 {len(tickers)} 个标的: {tickers}")
        closes = closes[tickers]
        volumes = volumes[tickers]
        highs = highs[tickers]
        lows = lows[tickers]

    # 2. 计算因子
    logger.info("🔢 计算因子...")
    factor_panel = build_factor_panel(closes, volumes, highs, lows)
    logger.info(f"   因子面板: {factor_panel.shape}")

    # 3. 准备训练数据
    data = prepare_training_data(factor_panel, closes)
    logger.info(f"   训练数据: {data.shape}")

    # 4. 缩尾处理
    data = clip_outliers(data, FEATURE_COLS, CLIP_STD_THRESHOLD)

    # 5. 构建 Walk-Forward 窗口
    dates = data.index.get_level_values("Date").unique()
    windows, test_window = build_walk_forward_windows(
        dates,
        initial_train_years=WF_INITIAL_TRAIN_YEARS,
        val_years=WF_VAL_YEARS,
        step_years=WF_STEP_YEARS,
        test_years=WF_TEST_YEARS,
    )

    if not windows:
        logger.error("❌ 无法构建 Walk-Forward 窗口——数据不足？")
        sys.exit(1)

    # 6. 训练
    results = train_walk_forward(
        data=data,
        windows=windows,
        test_window=test_window,
        feature_cols=FEATURE_COLS,
        target_col=args["target"],
        lgbm_params=DEFAULT_LGBM_PARAMS,
        num_boost_round=NUM_BOOST_ROUND,
        early_stopping_rounds=EARLY_STOPPING_ROUNDS,
    )

    # 7. 保存
    config = {
        "quick": args["quick"],
        "target": args["target"],
        "feature_cols": FEATURE_COLS,
        "lgbm_params": DEFAULT_LGBM_PARAMS,
        "num_boost_round": NUM_BOOST_ROUND,
        "early_stopping_rounds": EARLY_STOPPING_ROUNDS,
        "n_tickers": len(closes.columns),
        "n_dates": len(closes),
        "n_features": len(FEATURE_COLS),
        "walk_forward_params": {
            "initial_train_years": WF_INITIAL_TRAIN_YEARS,
            "val_years": WF_VAL_YEARS,
            "step_years": WF_STEP_YEARS,
            "test_years": WF_TEST_YEARS,
        },
        "clip_std_threshold": CLIP_STD_THRESHOLD,
    }
    exp_path = save_experiment(config, results)

    # 8. 打印摘要
    print_summary(results)

    logger.info(f"💾 实验已保存: {exp_path}")
    logger.info("✅ 训练完成")


if __name__ == "__main__":
    main()