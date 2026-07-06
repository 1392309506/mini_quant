"""
Quant Trading System — 自动化量化交易核心模块

面向个人研究者的中低频 Swing 交易系统。
技术因子 + 横截面模型 + LightGBM 预测 + vectorbt 回测。
"""

__version__ = "0.5.0"

# 数据层
from src.data.fetcher import (
    fetch_all_data,
    load_data,
    extract_close_matrix,
    extract_volume_matrix,
    check_data_integrity,
    print_integrity_report,
)

# 因子层
from src.factors import (
    compute_all_factors,
    build_factor_panel,
    validate_factors,
    market_regime_filter,
    FACTOR_NAMES,
)

# 标签
from src.data.label import compute_forward_returns, DEFAULT_PERIODS

# 数据预处理
from src.data.preprocess import (
    prepare_training_data,
    clip_outliers,
    build_walk_forward_windows,
    split_by_window,
)

# 模型
from src.models.trainer import train_walk_forward, train_single_window, predict_oos
from src.models.signals import (
    generate_rebalance_calendar,
    generate_entry_signals,
    generate_exit_signals,
    filter_by_market_regime,
)

# 回测
from src.backtest.engine import run_backtest, run_full_backtest
from src.backtest.reporting import (
    print_backtest_summary,
    save_backtest_report,
    plot_equity_curve,
    plot_drawdown,
)

# 实验
from src.experiment import save_experiment, load_experiment

# 配置
from src.config import (
    DATA_DIR,
    CACHE_FILE,
    EXPERIMENTS_DIR,
    STALE_DAYS,
    get_backend,
    get_proxies,
)

__all__ = [
    "__version__",
    # data
    "fetch_all_data", "load_data", "extract_close_matrix", "extract_volume_matrix",
    "check_data_integrity", "print_integrity_report",
    # factors
    "compute_all_factors", "build_factor_panel", "validate_factors",
    "market_regime_filter", "FACTOR_NAMES",
    # labels
    "compute_forward_returns", "DEFAULT_PERIODS",
    # preprocess
    "prepare_training_data", "clip_outliers", "build_walk_forward_windows",
    "split_by_window",
    # models
    "train_walk_forward", "train_single_window", "predict_oos",
    "generate_rebalance_calendar", "generate_entry_signals",
    "generate_exit_signals", "filter_by_market_regime",
    # backtest
    "run_backtest", "run_full_backtest",
    "print_backtest_summary", "save_backtest_report",
    "plot_equity_curve", "plot_drawdown",
    # experiment
    "save_experiment", "load_experiment",
    # config
    "DATA_DIR", "CACHE_FILE", "EXPERIMENTS_DIR", "STALE_DAYS",
    "get_backend", "get_proxies",
]