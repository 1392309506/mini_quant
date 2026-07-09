"""
LightGBM 模型训练编排

提供单窗口训练和完整的 Walk-Forward 滚动训练流程。
"""

import logging
from typing import List, Optional, Dict, Tuple

import pandas as pd
import numpy as np
import lightgbm as lgb

from src.models.config import (
    FEATURE_COLS,
    DEFAULT_LGBM_PARAMS,
    NUM_BOOST_ROUND,
    EARLY_STOPPING_ROUNDS,
)

logger = logging.getLogger(__name__)


def train_single_window(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
    target_col: str = "forward_return_10",
    lgbm_params: Optional[dict] = None,
    num_boost_round: int = NUM_BOOST_ROUND,
    early_stopping_rounds: int = EARLY_STOPPING_ROUNDS,
) -> Tuple[lgb.Booster, dict, pd.DataFrame]:
    """
    在训练集上训练 LightGBM 回归器，在验证集上评估。
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLS
    if lgbm_params is None:
        lgbm_params = DEFAULT_LGBM_PARAMS.copy()

    X_train = train_df[feature_cols].values
    y_train = train_df[target_col].values
    X_val = val_df[feature_cols].values
    y_val = val_df[target_col].values

    if len(X_train) < 10 or len(X_val) < 5:
        logger.warning(f"⚠️  数据量不足: train={len(X_train)}, val={len(X_val)}")
        raise ValueError(f"训练/验证数据不足: train={len(X_train)}, val={len(X_val)}")

    logger.info(
        f"🚀 训练: train={len(X_train)} 样本, val={len(X_val)} 样本, "
        f"features={len(feature_cols)}, target={target_col}"
    )

    train_data = lgb.Dataset(X_train, label=y_train, feature_name=feature_cols)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    model = lgb.train(
        lgbm_params,
        train_data,
        num_boost_round=num_boost_round,
        valid_sets=[train_data, val_data],
        valid_names=["train", "val"],
        callbacks=[
            lgb.early_stopping(early_stopping_rounds, verbose=False),
            lgb.log_evaluation(0),
        ],
    )

    best_score = getattr(model, "best_score", {})
    train_score = best_score.get("train", {})
    val_score = best_score.get("val", {})
    train_rmse = train_score.get("rmse", float("nan"))
    val_rmse = val_score.get("rmse", float("nan"))
    train_mae = train_score.get("mae", float("nan"))
    val_mae = val_score.get("mae", float("nan"))

    metrics = {
        "train_rmse": round(train_rmse, 6),
        "val_rmse": round(val_rmse, 6),
        "train_mae": round(train_mae, 6),
        "val_mae": round(val_mae, 6),
        "best_iteration": model.best_iteration,
        "n_train": len(y_train),
        "n_val": len(y_val),
    }

    gain = model.feature_importance(importance_type="gain")
    split = model.feature_importance(importance_type="split")
    importance = pd.DataFrame({
        "feature": feature_cols,
        "gain": gain,
        "split": split,
    }).sort_values("gain", ascending=False).reset_index(drop=True)

    logger.info(
        f"✅ 训练完成: val_rmse={val_rmse:.6f}, "
        f"best_iter={model.best_iteration}, "
        f"top_feature={importance.iloc[0]['feature']}"
        f"(gain={importance.iloc[0]['gain']:.2f})"
    )

    return model, metrics, importance


def predict_oos(
    model: lgb.Booster,
    df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
    target_col: str = "forward_return_10",
) -> pd.DataFrame:
    """
    在 DataFrame 上运行 OOS 预测。
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLS

    X = df[feature_cols].values
    pred = model.predict(X)

    result = pd.DataFrame({
        "pred": pred,
        "actual": df.get(target_col, np.nan),
    }, index=df.index)

    return result


def train_walk_forward(
    data: pd.DataFrame,
    windows: List[dict],
    test_window: dict,
    feature_cols: Optional[List[str]] = None,
    target_col: str = "forward_return_10",
    lgbm_params: Optional[dict] = None,
    num_boost_round: int = NUM_BOOST_ROUND,
    early_stopping_rounds: int = EARLY_STOPPING_ROUNDS,
) -> dict:
    """
    运行完整的 Walk-Forward 滚动训练流程。
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLS
    if lgbm_params is None:
        lgbm_params = DEFAULT_LGBM_PARAMS.copy()

    logger.info("=" * 60)
    logger.info("🏋️  开始 Walk-Forward 训练")
    logger.info(f"   target: {target_col}")
    logger.info(f"   features: {feature_cols}")
    logger.info(f"   windows: {len(windows)}")
    logger.info("=" * 60)

    models = {}
    metrics_list = []
    importance_list = []
    pred_oos_list = []

    for i, window in enumerate(windows):
        logger.info(f"\n--- 窗口 {window['name']} ---")

        dates = data.index.get_level_values("Date")
        train_mask = (dates >= window["train_start"]) & (
            dates <= window["train_end"]
        )
        val_mask = (dates >= window["val_start"]) & (dates <= window["val_end"])

        train_df = data.loc[train_mask]
        val_df = data.loc[val_mask]

        logger.info(f"  训练: {len(train_df)} 行, 验证: {len(val_df)} 行")

        try:
            model, metrics, importance = train_single_window(
                train_df=train_df,
                val_df=val_df,
                feature_cols=feature_cols,
                target_col=target_col,
                lgbm_params=lgbm_params,
                num_boost_round=num_boost_round,
                early_stopping_rounds=early_stopping_rounds,
            )
            model.params["seed"] = 42

            models[window["name"]] = model
            metrics["window"] = window["name"]
            metrics_list.append(metrics)
            importance["window"] = window["name"]
            importance_list.append(importance)

            pred_oos = predict_oos(model, val_df, feature_cols, target_col)
            pred_oos["window"] = window["name"]
            pred_oos_list.append(pred_oos)

            logger.info(
                f"  预测: {len(pred_oos)} 行, "
                f"pred_mean={pred_oos['pred'].mean():.4f}, "
                f"pred_std={pred_oos['pred'].std():.4f}"
            )

        except (ValueError, Exception) as e:
            logger.error(f"❌ 窗口 {window['name']} 训练失败: {e}")
            continue

    metrics_df = pd.DataFrame(metrics_list) if metrics_list else pd.DataFrame()
    importance_df = (
        pd.concat(importance_list, ignore_index=True) if importance_list
        else pd.DataFrame()
    )
    pred_oos_df = (
        pd.concat(pred_oos_list) if pred_oos_list
        else pd.DataFrame()
    )

    # 最终模型
    logger.info("\n--- 最终模型（测试集预测）---")
    from src.data.preprocess import split_by_window

    train_all_df, test_df, _ = split_by_window(data, test_window)

    if len(train_all_df) > 0 and len(test_df) > 0:
        final_model, final_metrics, _ = train_single_window(
            train_df=train_all_df,
            val_df=test_df,
            feature_cols=feature_cols,
            target_col=target_col,
            lgbm_params=lgbm_params,
            num_boost_round=num_boost_round,
            early_stopping_rounds=early_stopping_rounds,
        )
        final_model.params["seed"] = 42
        test_pred = predict_oos(final_model, test_df, feature_cols, target_col)
        test_pred["window"] = "test"
    else:
        logger.warning("⚠️  测试集数据不足，跳过最终模型训练")
        final_model = None
        test_pred = pd.DataFrame()

    results = {
        "models": models,
        "final_model": final_model,
        "metrics": metrics_df,
        "importance": importance_df,
        "pred_oos": pred_oos_df,
        "pred_test": test_pred,
        "data_ranges": {
            "full_start": str(data.index.get_level_values("Date").min().date()),
            "full_end": str(data.index.get_level_values("Date").max().date()),
            "n_windows": len(windows),
            "n_features": len(feature_cols),
            "target": target_col,
        },
    }

    avg_val_rmse = metrics_df["val_rmse"].mean() if len(metrics_df) > 0 else float("nan")
    logger.info("=" * 60)
    logger.info(f"🏁 Walk-Forward 训练完成")
    logger.info(f"   窗口: {len(metrics_list)}/{len(windows)} 成功")
    logger.info(f"   平均验证 RMSE: {avg_val_rmse:.6f}")
    if importance_df is not None and len(importance_df) > 0:
        top_feat = importance_df.groupby("feature")["gain"].mean().idxmax()
        logger.info(f"   最重要的特征: {top_feat}")
    logger.info("=" * 60)

    return results
