"""
src.factors — 因子计算子包

暴露所有因子函数和组装工具，方便外部导入：

    from src.factors import (
        compute_all_factors, build_factor_panel, validate_factors,
        momo_20, rsi_14, atr_20, market_regime_filter, ...
    )
"""

from src.factors.momentum import momo_20, momo_60, mom_ratio
from src.factors.mean_reversion import rsi_14, bb_position, vol_ma_ratio
from src.factors.volatility import atr_20, volatility_20
from src.factors.regime import market_regime_filter
from src.factors.assembly import compute_all_factors, build_factor_panel, FACTOR_NAMES
from src.factors.validation import validate_factors

__all__ = [
    "compute_all_factors",
    "build_factor_panel",
    "validate_factors",
    "momo_20", "momo_60", "mom_ratio",
    "rsi_14", "bb_position", "vol_ma_ratio",
    "atr_20", "volatility_20",
    "market_regime_filter",
    "FACTOR_NAMES",
]