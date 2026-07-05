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
    fees: float = 0.001,
    top_k: int = 5,
    name: str = "quant_strategy",
) -> dict:
    """
    使用 vectorbt 的 Portfolio.from_signals 运行回测。
    """
    try:
        import vectorbt as vbt
    except ImportError:
        logger.error("❌ vectorbt 未安装，请运行: pip install vectorbt")
        raise

    logger.info(
        f"📊 运行回测: {len(entries)} 天, {entries.shape[1]} 个标的, "
        f"费用={fees:.1%}, 资金={init_cash:,.0f}"
    )

    if top_k is None or top_k <= 0:
        top_k = 5
    position_size = 1.0 / top_k

    pf = vbt.Portfolio.from_signals(
        open_price,
        close,
        entries,
        exits,
        price=open_price,
        init_cash=init_cash,
        size=position_size,
        cash_sharing=True,
        fees=fees,
        freq="D",
        slippage=0.0,
    )

    metrics = _compute_portfolio_metrics(pf)
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


def _compute_portfolio_metrics(pf) -> Dict:
    """从 vectorbt Portfolio 提取标准回测指标。"""
    try:
        portfolio_value = pf.value()
    except Exception:
        portfolio_value = None

    if portfolio_value is not None and len(portfolio_value) > 1:
        if isinstance(portfolio_value, pd.DataFrame):
            portfolio_value = portfolio_value.sum(axis=1)

        total_return = float((portfolio_value.iloc[-1] / portfolio_value.iloc[0]) - 1)
        total_return_pct = total_return * 100

        if isinstance(portfolio_value, pd.DataFrame):
            portfolio_value = portfolio_value.iloc[:, 0]
        returns = portfolio_value.pct_change().dropna()

        n_days = len(returns)
        ann_factor = 252 / n_days if n_days > 0 else 0
        annualized_return = total_return * ann_factor if ann_factor > 0 else 0
        annualized_vol = float(returns.std() * (252 ** 0.5)) if n_days > 0 else 0
        sharpe = (annualized_return / annualized_vol) if annualized_vol > 0 else 0

        cummax = portfolio_value.cummax()
        drawdown = float((portfolio_value / cummax - 1).min())
        max_drawdown = drawdown
        max_drawdown_pct = drawdown * 100

        try:
            trades = pf.trades
            if isinstance(trades, dict):
                all_trades = pd.concat(trades.values(), ignore_index=True)
                num_trades = len(all_trades)
                if num_trades > 0:
                    pnl_col = [c for c in all_trades.columns if "pnl" in c.lower()][0]
                    win_rate = (all_trades[pnl_col] > 0).sum() / num_trades
                    profits = all_trades[all_trades[pnl_col] > 0][pnl_col].sum()
                    losses = abs(all_trades[all_trades[pnl_col] < 0][pnl_col].sum())
                    profit_factor = profits / losses if losses > 0 else float("inf")
                else:
                    win_rate = 0
                    profit_factor = 0
            else:
                num_trades = len(trades)
                if num_trades > 0:
                    win_rate = (trades["pnl"] > 0).sum() / num_trades
                    profit_factor = (
                        trades[trades["pnl"] > 0]["pnl"].sum()
                        / abs(trades[trades["pnl"] < 0]["pnl"].sum())
                    ) if (trades["pnl"] < 0).sum() > 0 else float("inf")
                else:
                    win_rate = 0
                    profit_factor = 0
        except Exception:
            num_trades = 0
            win_rate = 0
            profit_factor = 0

        try:
            total_fees = pf.fees().sum().sum()
        except Exception:
            total_fees = 0

        downside = returns[returns < 0]
        downside_vol = downside.std() * (252 ** 0.5) if len(downside) > 0 else 0
        sortino = (annualized_return / downside_vol) if downside_vol > 0 else 0

    else:
        total_return = 0
        total_return_pct = 0
        annualized_return = 0
        annualized_vol = 0
        sharpe = 0
        sortino = 0
        max_drawdown = 0
        max_drawdown_pct = 0
        win_rate = 0
        profit_factor = 0
        num_trades = 0
        total_fees = 0
        returns = pd.Series(dtype=float)

    metrics = {
        "total_return": total_return,
        "total_return_pct": round(total_return_pct, 2),
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

    return metrics | {"returns": returns}


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
        top_k=bt_config.get("top_k", 5),
    )

    result["entries"] = entries
    result["exits"] = exits
    result["prediction_range"] = {
        "start": str(bt_start.date()),
        "end": str(bt_end.date()),
    }

    return result