"""
vectorbt 回测包装器

遵循 CONSTITUTION.md 约束：
  - 工具: vectorbt Portfolio.from_signals
  - 入场: open[t+1]
  - 持仓: 5-30 天
  - 成本: 单边 0.1%
  - 信号频率: 每周最多 2 次调仓
"""

import logging
from typing import Optional, Dict

import pandas as pd
import numpy as np

from src.models.signals import (
    generate_rebalance_calendar,
    generate_entry_signals,
    generate_exit_signals,
    filter_by_market_regime,
)

logger = logging.getLogger(__name__)


def run_backtest(
    open_price: pd.DataFrame,
    close: pd.DataFrame,
    entries: pd.DataFrame,
    exits: pd.DataFrame,
    init_cash: float = 100_000,
    fees: float = 0.0017,
    slippage: float = 0.0005,
    top_k: int = 5,
    position_scale: float = 1.0,
    n_trading_days: int = 0,
    oos_start: str = "",
    oos_end: str = "",
    name: str = "quant_strategy",
) -> dict:
    """
    使用 vectorbt 的 Portfolio.from_signals 运行回测。

    成本模型: 佣金(fees) + 滑点(slippage) + 点差(已含在 fees 中)。

    Parameters
    ----------
    position_scale : float
        头寸规模倍数。1.0 = 等权 (1/top_k)，3.0 = 3 倍杠杆。
    n_trading_days : int
        实际交易天数（年化用）。0 = 自动从 entries 推算。
    oos_start, oos_end : str
        OOS 期起止日期，用于正确计算年化波动率。
    """
    try:
        import vectorbt as vbt
    except ImportError:
        logger.error("❌ vectorbt 未安装，请运行: pip install vectorbt")
        raise

    total_cost = fees + slippage
    logger.info(
        f"📊 运行回测: {len(entries)} 天, {entries.shape[1]} 个标的, "
        f"费用={total_cost:.2%}, 资金={init_cash:,.0f}"
    )

    if top_k is None or top_k <= 0:
        top_k = 5
    position_size = 1.0 / top_k * position_scale

    pf = vbt.Portfolio.from_signals(
        open_price,
        close,
        entries,
        exits,
        price=open_price,
        init_cash=init_cash,
        size=position_size,
        cash_sharing=True,
        fees=total_cost,
        freq="D",
        slippage=0.0,  # vectorbt 的 slippage 模型与我们的手续费有重叠，用 fees 统一处理
    )

    # 实际交易天数：从 entries 中至少有 1 笔入场的第一天到最后一天
    if n_trading_days <= 0:
        trade_dates = entries.index[(entries.sum(axis=1) > 0)]
        n_trading_days = len(trade_dates) if len(trade_dates) > 0 else len(entries)

    metrics = _compute_portfolio_metrics(pf, n_trading_days=n_trading_days)
    metrics["n_trades"] = int(metrics.get("num_trades", 0))
    metrics["total_return"] = round(float(metrics.get("total_return", 0)), 6)
    metrics["total_fees_paid"] = round(float(metrics.get("total_fees_paid", 0)), 2)

    logger.info(
        f"✅ 回测完成: 收益率={metrics['total_return']:+.2%}, "
        f"夏普={metrics.get('sharpe_ratio', 0):.2f}, "
        f"最大回撤={metrics.get('max_drawdown', 0):.2%}, "
        f"交易次数={metrics['n_trades']}"
    )

    return {
        "portfolio": pf,
        "metrics": metrics,
        "entries": entries,
        "exits": exits,
    }


def _compute_portfolio_metrics(pf, n_trading_days: int = 0) -> Dict:
    """从 vectorbt Portfolio 提取标准回测指标。

    Parameters
    ----------
    n_trading_days : int
        实际交易天数（OOS 期，用于年化）。0 = 用整个 returns 序列长度。
    """
    # --- 获取组合价值与日收益 ---
    try:
        portfolio_value = pf.value()
    except Exception:
        portfolio_value = None

    if portfolio_value is None or len(portfolio_value) <= 1:
        return _empty_metrics()

    if isinstance(portfolio_value, pd.DataFrame):
        portfolio_value = portfolio_value.sum(axis=1)

    total_return = float((portfolio_value.iloc[-1] / portfolio_value.iloc[0]) - 1)
    all_returns = portfolio_value.pct_change().dropna()

    if len(all_returns) == 0:
        return _empty_metrics()

    # --- 核心指标 ---
    n_days = n_trading_days if n_trading_days > 0 else len(all_returns)
    ann_factor = 252 / n_days if n_days > 0 else 0
    annualized_return = (1 + total_return) ** ann_factor - 1 if ann_factor > 0 else 0

    # 年化波动率：只用有交易活动的期间（排除 0 收益的平坦段）
    active_returns = all_returns[all_returns.abs() > 1e-10]
    if len(active_returns) < 20:
        active_returns = all_returns  # fallback
    annualized_vol = float(active_returns.std() * (252 ** 0.5))
    sharpe = (annualized_return / annualized_vol) if annualized_vol > 1e-10 else 0

    cummax = portfolio_value.cummax()
    max_drawdown = float((portfolio_value / cummax - 1).min())
    max_drawdown_pct = max_drawdown * 100

    # --- 交易统计 ---
    num_trades = 0
    win_rate = 0.0
    profit_factor = 0.0
    try:
        trades = pf.trades
        if hasattr(trades, "count") and not isinstance(trades, pd.DataFrame):
            num_trades = trades.count()
            if num_trades > 0:
                win_rate = float(trades.win_rate())
                pf_val = float(trades.profit_factor())
                profit_factor = pf_val if pf_val != float("inf") else 0
        elif isinstance(trades, dict):
            all_trades = pd.concat(trades.values(), ignore_index=True)
            num_trades = len(all_trades)
            if num_trades > 0:
                pnl_col = [c for c in all_trades.columns if "pnl" in c.lower()][0]
                win_rate = (all_trades[pnl_col] > 0).sum() / num_trades
                profits = all_trades[all_trades[pnl_col] > 0][pnl_col].sum()
                losses = abs(all_trades[all_trades[pnl_col] < 0][pnl_col].sum())
                profit_factor = profits / losses if losses > 0 else 0
        else:
            num_trades = len(trades)
            if num_trades > 0:
                win_rate = (trades["pnl"] > 0).sum() / num_trades
                profit_factor = (trades[trades["pnl"] > 0]["pnl"].sum()
                    / abs(trades[trades["pnl"] < 0]["pnl"].sum())
                ) if (trades["pnl"] < 0).sum() > 0 else 0
    except Exception:
        pass

    total_fees = 0.0
    try:
        fees = pf.fees()
        if hasattr(fees, "sum"):
            total_fees = float(fees.sum())
    except Exception:
        pass

    downside = active_returns[active_returns < 0]
    downside_vol = downside.std() * (252 ** 0.5) if len(downside) > 0 else 0
    sortino = (annualized_return / downside_vol) if downside_vol > 1e-10 else 0

    metrics = {
        "total_return": total_return,
        "total_return_pct": round(total_return * 100, 2),
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_vol,
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "win_rate": round(win_rate, 3),
        "profit_factor": round(profit_factor, 2),
        "num_trades": num_trades,
        "total_fees_paid": round(total_fees, 2),
    }

    return metrics | {"returns": all_returns}


def _empty_metrics() -> Dict:
    """返回空指标字典（数据不足时使用）。"""
    return {
        "total_return": 0, "total_return_pct": 0,
        "annualized_return": 0, "annualized_volatility": 0,
        "sharpe_ratio": 0, "sortino_ratio": 0,
        "max_drawdown": 0, "max_drawdown_pct": 0,
        "win_rate": 0, "profit_factor": 0,
        "num_trades": 0, "total_fees_paid": 0,
        "returns": pd.Series(dtype=float),
    }


def run_full_backtest(
    predictions: pd.DataFrame,
    open_price: pd.DataFrame,
    close: pd.DataFrame,
    bt_config: dict,
    spy_close: Optional[pd.Series] = None,
) -> dict:
    """
    端到端回测：从 OOS 预测 → 信号 → 回测 → 指标。
    """
    pred_dates = predictions.index.get_level_values("Date").unique()
    bt_start = pred_dates.min()
    bt_end = pred_dates.max()

    logger.info(f"📅 回测范围: {bt_start.date()} → {bt_end.date()}")

    rebalance_dates = generate_rebalance_calendar(
        bt_start, bt_end,
        max_per_week=bt_config.get("max_rebalances_per_week", 2),
    )

    entries = generate_entry_signals(
        predictions=predictions,
        rebalance_dates=rebalance_dates,
        close=close,
        top_k=bt_config.get("top_k", 5),
        min_pred=bt_config.get("min_pred", 0.0),
    )

    if bt_config.get("use_regime_filter", True) and spy_close is not None:
        entries = filter_by_market_regime(
            entries, spy_close,
            ma_window=bt_config.get("regime_ma_window", 200),
        )

    exits = generate_exit_signals(
        entries,
        min_hold=bt_config.get("min_hold", 5),
        max_hold=bt_config.get("max_hold", 30),
    )

    common_dates = entries.index.intersection(open_price.index)
    entries = entries.loc[common_dates]
    exits = exits.loc[common_dates]
    open_price_aligned = open_price.loc[common_dates]

    result = run_backtest(
        open_price=open_price_aligned,
        close=close.loc[common_dates],
        entries=entries,
        exits=exits,
        init_cash=bt_config.get("init_cash", 100_000),
        fees=bt_config.get("one_way_fee", 0.001),
        slippage=bt_config.get("slippage", 0.0005),
        top_k=bt_config.get("top_k", 5),
        position_scale=bt_config.get("position_scale", 1.0),
        n_trading_days=len(open_price.loc[bt_start:bt_end]),
    )

    result["entries"] = entries
    result["exits"] = exits
    result["prediction_range"] = {
        "start": str(bt_start.date()),
        "end": str(bt_end.date()),
    }

    # 保存 SPY 收盘价用于基准对比
    if spy_close is not None:
        result["spy_close"] = spy_close

    return result