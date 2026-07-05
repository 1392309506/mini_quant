"""
experiment.py — 实验记录与加载

将训练结果保存到 experiments/<exp_id>/ 目录，支持后续加载和回测。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from src.config import EXPERIMENTS_DIR

logger = logging.getLogger(__name__)


def generate_experiment_id() -> str:
    """生成实验 ID: YYYYMMDD_HHMMSS"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_experiment(
    config: dict,
    results: dict,
    exp_dir: Optional[str] = None,
    exp_id: Optional[str] = None,
) -> str:
    """
    保存完整的实验工件到 {exp_dir}/{exp_id}/。

    写入:
      - config.json: 训练参数、窗口边界等
      - windows_metrics.csv: 每个窗口的指标
      - feature_importance.csv: 所有窗口的特征重要性
      - oos_predictions.parquet: OOS 预测
      - test_predictions.parquet: 测试集预测
      - models/: model_{window}.txt (LightGBM 文本格式)
      - summary.json: 摘要指标

    Parameters
    ----------
    config : dict
        实验配置（参数、数据范围等）。
    results : dict
        训练结果（来自 trainer.train_walk_forward）。
    exp_dir : str, optional
        实验根目录，默认 EXPERIMENTS_DIR。
    exp_id : str, optional
        实验 ID，默认自动生成。

    Returns
    -------
    str
        实验目录的完整路径。
    """
    if exp_dir is None:
        exp_dir = str(EXPERIMENTS_DIR)
    if exp_id is None:
        exp_id = generate_experiment_id()

    exp_path = Path(exp_dir) / exp_id
    models_path = exp_path / "models"
    exp_path.mkdir(parents=True, exist_ok=True)
    models_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"💾 保存实验到 {exp_path}")

    # 1. config.json
    with open(exp_path / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False, default=str)

    # 2. windows_metrics.csv
    metrics = results.get("metrics")
    if metrics is not None and len(metrics) > 0:
        metrics.to_csv(exp_path / "windows_metrics.csv", index=False)

    # 3. feature_importance.csv
    importance = results.get("importance")
    if importance is not None and len(importance) > 0:
        importance.to_csv(exp_path / "feature_importance.csv", index=False)

    # 4. oos_predictions.parquet
    pred_oos = results.get("pred_oos")
    if pred_oos is not None and len(pred_oos) > 0:
        pred_oos.to_parquet(exp_path / "oos_predictions.parquet")

    # 5. test_predictions.parquet
    pred_test = results.get("pred_test")
    if pred_test is not None and len(pred_test) > 0:
        pred_test.to_parquet(exp_path / "test_predictions.parquet")

    # 6. models
    for name, model in results.get("models", {}).items():
        model.save_model(str(models_path / f"{name}.txt"))

    final_model = results.get("final_model")
    if final_model is not None:
        final_model.save_model(str(models_path / "final.txt"))

    # 7. summary.json
    summary = {
        "exp_id": exp_id,
        "exp_dir": str(exp_path),
        "config": {k: str(v) if not isinstance(v, (int, float, str, list, dict)) else v
                   for k, v in config.items()},
    }

    if metrics is not None and len(metrics) > 0:
        summary["avg_val_rmse"] = round(float(metrics["val_rmse"].mean()), 6)
        summary["avg_val_mae"] = round(float(metrics["val_mae"].mean()), 6)
        summary["n_windows_success"] = len(metrics)

    data_ranges = results.get("data_ranges", {})
    summary.update(data_ranges)

    with open(exp_path / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"✅ 实验保存完成: {exp_path}")
    logger.info(f"   窗口指标: {metrics.shape[0] if metrics is not None else 0} 个窗口")
    logger.info(f"   OOS 预测: {len(pred_oos) if pred_oos is not None else 0} 行")

    return str(exp_path)


def load_experiment(
    exp_path: str,
) -> dict:
    """
    从磁盘加载实验工件。

    返回 dict:
        config, metrics, importance, pred_oos, pred_test, models, summary
    """
    exp_dir = Path(exp_path)
    if not exp_dir.exists():
        raise FileNotFoundError(f"实验目录不存在: {exp_path}")

    logger.info(f"📂 加载实验: {exp_path}")

    config = {}
    config_path = exp_dir / "config.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

    metrics = None
    metrics_path = exp_dir / "windows_metrics.csv"
    if metrics_path.exists():
        metrics = pd.read_csv(metrics_path)

    importance = None
    imp_path = exp_dir / "feature_importance.csv"
    if imp_path.exists():
        importance = pd.read_csv(imp_path)

    pred_oos = None
    oos_path = exp_dir / "oos_predictions.parquet"
    if oos_path.exists():
        pred_oos = pd.read_parquet(oos_path)

    pred_test = None
    test_path = exp_dir / "test_predictions.parquet"
    if test_path.exists():
        pred_test = pd.read_parquet(test_path)

    # 加载 LightGBM 模型
    import lightgbm as lgb
    models = {}
    models_dir = exp_dir / "models"
    if models_dir.exists():
        for model_file in sorted(models_dir.glob("*.txt")):
            name = model_file.stem  # W1, W2, ..., final
            models[name] = lgb.Booster(model_file=str(model_file))

    summary = {}
    summary_path = exp_dir / "summary.json"
    if summary_path.exists():
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

    logger.info(
        f"   加载完成: {len(models)} 个模型, "
        f"{metrics.shape[0] if metrics is not None else 0} 个窗口, "
        f"{len(pred_oos) if pred_oos is not None else 0} 条 OOS 预测"
    )

    return {
        "exp_path": str(exp_dir),
        "config": config,
        "metrics": metrics,
        "importance": importance,
        "pred_oos": pred_oos,
        "pred_test": pred_test,
        "models": models,
        "summary": summary,
    }