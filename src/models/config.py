"""
模型训练超参数配置 — 与训练逻辑分离
"""

from typing import List

# ===================================================================
# 特征列（对应 13 个因子，各含 3 个变体 = 39 个特征）
# ===================================================================
FEATURE_COLS: List[str] = [
    # 原始因子（13 个）
    "MOMO_20", "MOMO_60", "MOM_RATIO",
    "RSI_14", "BB_POS", "VOL_MA_RATIO",
    "ATR_20_NORM", "VOLATILITY_20",
    "BB_WIDTH", "HIGH_LOW_RATIO",
    "CHAIKIN_MF", "ULCER_INDEX", "MAX_DD_60",
    # 横截面排名
    "MOMO_20_rank", "MOMO_60_rank", "MOM_RATIO_rank",
    "RSI_14_rank", "BB_POS_rank", "VOL_MA_RATIO_rank",
    "ATR_20_NORM_rank", "VOLATILITY_20_rank",
    "BB_WIDTH_rank", "HIGH_LOW_RATIO_rank",
    "CHAIKIN_MF_rank", "ULCER_INDEX_rank", "MAX_DD_60_rank",
    # 横截面 Z-score
    "MOMO_20_zscore", "MOMO_60_zscore", "MOM_RATIO_zscore",
    "RSI_14_zscore", "BB_POS_zscore", "VOL_MA_RATIO_zscore",
    "ATR_20_NORM_zscore", "VOLATILITY_20_zscore",
    "BB_WIDTH_zscore", "HIGH_LOW_RATIO_zscore",
    "CHAIKIN_MF_zscore", "ULCER_INDEX_zscore", "MAX_DD_60_zscore",
]

# ===================================================================
# 默认预测目标
# ===================================================================
DEFAULT_TARGET = "forward_return_10"

# ===================================================================
# LightGBM 默认参数
# ===================================================================
DEFAULT_LGBM_PARAMS = {
    "objective": "regression_l2",
    "metric": ["rmse", "mae"],
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "min_data_in_leaf": 20,
    "verbose": -1,
    "seed": 42,
    "force_row_wise": True,
}

# ===================================================================
# 训练控制
# ===================================================================
NUM_BOOST_ROUND = 3000
EARLY_STOPPING_ROUNDS = 500

# ===================================================================
# Walk-Forward 默认窗口参数（年）
# ===================================================================
WF_INITIAL_TRAIN_YEARS = 6.0
WF_VAL_YEARS = 1.0
WF_STEP_YEARS = 1.0
WF_TEST_YEARS = 1.5

# ===================================================================
# 缩尾阈值（标准差倍数）
# ===================================================================
CLIP_STD_THRESHOLD = 5.0