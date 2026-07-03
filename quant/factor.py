"""
因子计算引擎

从 OHLCV 数据计算所有技术因子，供模型训练和信号生成。
每个因子函数是纯函数（输入 price_df → 输出 factor_df），
便于单元测试和独立验证。
"""

from .engine import (
    compute_all_factors,
    build_factor_panel,
    validate_factors,
    momo_20, momo_60, mom_ratio,
    rsi_14, bb_position, vol_ma_ratio,
    atr_20, volatility_20,
    market_regime_filter,
)

__all__ = [
    "compute_all_factors",
    "build_factor_panel",
    "validate_factors",
    "momo_20", "momo_60", "mom_ratio",
    "rsi_14", "bb_position", "vol_ma_ratio",
    "atr_20", "volatility_20",
    "market_regime_filter",
]
