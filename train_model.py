#!/usr/bin/env python3
"""
train_model.py — 模型训练入口脚本

用法:
  python train_model.py                                 # 完整训练（默认全量标的）
  python train_model.py --quick                         # 快速测试（5 个标的）
  python train_model.py --target 21                     # 预测 forward_return_21
  python train_model.py --version V3                    # 指定模型版本名
  python train_model.py --universe 28                   # 只训练前 28 个标的
  python train_model.py --version V3 --universe 28      # 组合使用
  python train_model.py --load <exp_id>                 # 加载已有实验
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
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
    add_cross_sectional_features,
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
from src.experiment import save_experiment, load_experiment, generate_experiment_id
from src.config import MODELS_DIR


def parse_args():
    """解析命令行参数。"""
    args = {
        "quick": "--quick" in sys.argv[1:],
        "load_mode": "--load" in sys.argv[1:],
        "target": DEFAULT_TARGET,
        "load_id": None,
        "version": None,
        "universe": None,
    }

    for i, arg in enumerate(sys.argv):
        if arg == "--target" and i + 1 < len(sys.argv):
            period = sys.argv[i + 1]
            args["target"] = f"forward_return_{period}"
        elif arg == "--load" and i + 1 < len(sys.argv):
            args["load_id"] = sys.argv[i + 1]
        elif arg == "--version" and i + 1 < len(sys.argv):
            args["version"] = sys.argv[i + 1]
        elif arg == "--universe" and i + 1 < len(sys.argv):
            args["universe"] = int(sys.argv[i + 1])

    return args


def save_to_models(config: dict, results: dict, version: str, n_tickers: int):
    """将模型保存到 models/ 目录（Model Registry 格式）。"""
    target = config.get("target", "forward_return_10")
    target_days = target.replace("forward_return_", "fwd")
    version_dir = MODELS_DIR / f"{version}_{n_tickers}stock_{target_days}"
    version_dir.mkdir(parents=True, exist_ok=True)

    # 保存模型文件
    models_dir = version_dir / "models"
    models_dir.mkdir(exist_ok=True)
    for name, model in results.get("models", {}).items():
        model.save_model(str(models_dir / f"{name}.txt"))
    final_model = results.get("final_model")
    if final_model is not None:
        final_model.save_model(str(models_dir / "final.txt"))

    # 特征重要性
    importance = results.get("importance")
    if importance is not None and len(importance) > 0:
        importance.to_csv(version_dir / "feature_importance.csv", index=False)

    # manifest.json
    metrics = results.get("metrics")
    manifest = {
        "version": version,
        "name": f"{version}_{n_tickers}stock_{target_days}",
        "target": target,
        "n_tickers": n_tickers,
        "tickers": config.get("tickers"),
        "n_features": len(FEATURE_COLS),
        "feature_cols": FEATURE_COLS,
        "n_windows": len(results.get("models", {})),
        "avg_val_rmse": round(float(metrics["val_rmse"].mean()), 6)
            if metrics is not None and len(metrics) > 0 else None,
        "trained_at": datetime.now().isoformat(),
        "walk_forward_params": {
            "initial_train_years": WF_INITIAL_TRAIN_YEARS,
            "val_years": WF_VAL_YEARS,
            "step_years": WF_STEP_YEARS,
            "test_years": WF_TEST_YEARS,
        },
    }
    with open(version_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"💾 模型已保存到: {version_dir}")


def print_summary(results: dict):
    """打印训练结果摘要。"""
    metrics = results.get("metrics")
    if metrics is None or len(metrics) == 0:
        logger.warning("⚠️  无有效的训练窗口")
        return

    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 训练摘要")
    logger.info("=" * 60)

    logger.info(f"{'窗口':<8} {'Train RMSE':<14} {'Val RMSE':<14} {'Best Iter':<12}")
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

    # --universe N：只保留前 N 个标的
    if args["universe"] is not None:
        tickers = closes.columns[:args["universe"]].tolist()
        logger.info(
            f"📌 标的池限制: 前 {args['universe']} 个标的 "
            f"({tickers[0]}...{tickers[-1]})"
        )
        closes = closes[tickers]
        volumes = volumes[tickers]
        highs = highs[tickers]
        lows = lows[tickers]
    elif args["quick"]:
        tickers = closes.columns[:5].tolist()
        logger.info(f"⚡ 快速模式: 仅使用 5 个标的: {tickers}")
        closes = closes[tickers]
        volumes = volumes[tickers]
        highs = highs[tickers]
        lows = lows[tickers]

    n_tickers = closes.shape[1]

    # 2. 计算因子
    logger.info("🔢 计算因子...")
    factor_panel = build_factor_panel(closes, volumes, highs, lows)
    logger.info(f"   因子面板: {factor_panel.shape}")

    # 3. 准备训练数据
    data = prepare_training_data(factor_panel, closes)
    logger.info(f"   训练数据: {data.shape}")

    N_BASE_FEATURES = 13

    # 3b. 添加横截面特征
    logger.info("📊 添加横截面特征...")
    data = add_cross_sectional_features(data, FEATURE_COLS[:N_BASE_FEATURES])
    logger.info(f"   横截面特征后: {data.shape}, 特征数={len(FEATURE_COLS)}")

    # 4. 缩尾处理
    data = clip_outliers(data, FEATURE_COLS[:N_BASE_FEATURES], CLIP_STD_THRESHOLD)

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

    # 7. 配置摘要
    config = {
        "quick": args["quick"],
        "target": args["target"],
        "feature_cols": FEATURE_COLS,
        "lgbm_params": DEFAULT_LGBM_PARAMS,
        "num_boost_round": NUM_BOOST_ROUND,
        "early_stopping_rounds": EARLY_STOPPING_ROUNDS,
        "n_tickers": n_tickers,
        "tickers": closes.columns.tolist(),
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

    # 8. 保存到 experiments/（实验记录）
    exp_path = save_experiment(config, results)

    # 9. 保存到 models/（可部署模型文件）
    if args["version"]:
        save_to_models(config, results, args["version"], n_tickers)

    # 10. 打印摘要
    print_summary(results)

    logger.info(f"💾 实验已保存: {exp_path}")

    if args["version"]:
        version_name = f"{args['version']}_{n_tickers}stock_{args['target'].replace('forward_return_', 'fwd')}"
        logger.info(f"💾 模型已保存: {MODELS_DIR / version_name}")
    else:
        logger.info("💡 提示: 用 --version <name> 同时保存模型到 models/ 目录")

    logger.info("✅ 训练完成")


if __name__ == "__main__":
    main()
