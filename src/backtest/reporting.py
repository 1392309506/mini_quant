"""
回测结果可视化与报告

生成 equity curve、drawdown、pred vs actual 等图表。
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["axes.unicode_minus"] = False

logger = logging.getLogger(__name__)


def print_backtest_summary(metrics: dict):
    """打印格式化的回测指标摘要。"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Backtest Summary")
    logger.info("=" * 60)

    rows = [
        ("Total Return", f"{metrics.get('total_return_pct', 0):.2f}%"),
        ("Ann. Return", f"{metrics.get('annualized_return', 0)*100:.2f}%"),
        ("Ann. Volatility", f"{metrics.get('annualized_volatility', 0)*100:.2f}%"),
        ("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}"),
        ("Sortino Ratio", f"{metrics.get('sortino_ratio', 0):.2f}"),
        ("Max Drawdown", f"{metrics.get('max_drawdown_pct', 0):.2f}%"),
        ("Win Rate", f"{metrics.get('win_rate', 0)*100:.1f}%"),
        ("Profit Factor", f"{metrics.get('profit_factor', 0):.2f}"),
        ("Num Trades", f"{int(metrics.get('num_trades', 0))}"),
        ("Total Fees", f"${metrics.get('total_fees_paid', 0):.2f}"),
    ]

    for label, value in rows:
        logger.info(f"  {label:<16} {value}")

    logger.info("")


def plot_equity_curve(
    returns: pd.Series,
    save_path: str,
    title: str = "Equity Curve",
):
    """绘制并保存 equity curve 图。"""
    if returns is None or len(returns) == 0:
        logger.warning("No returns data, skipping equity curve")
        return

    equity = (1 + returns.fillna(0)).cumprod()

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(equity.index, equity.values, linewidth=1.5, color="#2196F3")
    ax.fill_between(equity.index, 1, equity.values, alpha=0.15, color="#2196F3")
    ax.axhline(y=1, color="gray", linestyle="--", linewidth=0.5)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel("Cumulative Return")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis="x", rotation=30)

    final_ret = equity.iloc[-1] - 1
    ax.text(
        0.02, 0.95, f"Total Return: {final_ret:+.2%}",
        transform=ax.transAxes, fontsize=11,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Equity curve saved: {save_path}")


def plot_drawdown(
    returns: pd.Series,
    save_path: str,
):
    """绘制并保存回撤图。"""
    if returns is None or len(returns) < 2:
        return

    equity = (1 + returns.fillna(0)).cumprod()
    cummax = equity.cummax()
    drawdown = (equity / cummax - 1) * 100

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(drawdown.index, 0, drawdown.values, color="#F44336", alpha=0.5)
    ax.set_title("Drawdown", fontsize=14, fontweight="bold")
    ax.set_ylabel("Drawdown (%)")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis="x", rotation=30)

    max_dd = drawdown.min()
    ax.text(
        0.02, 0.05, f"Max Drawdown: {max_dd:.1f}%",
        transform=ax.transAxes, fontsize=11,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round", facecolor="salmon", alpha=0.5),
    )

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Drawdown chart saved: {save_path}")


def plot_predictions_vs_actuals(
    pred_df: pd.DataFrame,
    save_path: str,
):
    """预测 vs 实际收益散点图。"""
    if "pred" not in pred_df.columns or "actual" not in pred_df.columns:
        logger.warning("Missing pred/actual columns")
        return

    pred = pred_df["pred"].dropna()
    actual = pred_df["actual"].dropna()
    common = pred.index.intersection(actual.index)
    if len(common) == 0:
        return
    pred = pred.loc[common]
    actual = actual.loc[common]

    if len(pred) < 10:
        return

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(pred, actual, alpha=0.3, s=5, color="#2196F3")
    lim = max(pred.max(), actual.max(), -pred.min(), -actual.min())
    ax.plot([-lim, lim], [-lim, lim], "r--", linewidth=1, alpha=0.5)
    ax.set_title("Predictions vs Actuals", fontsize=14, fontweight="bold")
    ax.set_xlabel("Predicted Return")
    ax.set_ylabel("Actual Return")
    ax.grid(True, alpha=0.3)
    ax.axis("equal")

    corr = pred.corr(actual)
    ax.text(
        0.05, 0.95, f"Pearson r = {corr:.3f}",
        transform=ax.transAxes, fontsize=11,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Pred vs actual chart saved: {save_path}")


def save_backtest_report(
    bt_dir: str,
    bt_id: str,
    metrics: dict,
    config: dict,
    result: dict,
) -> str:
    """保存完整的回测报告。"""
    report_path = Path(bt_dir) / bt_id
    report_path.mkdir(parents=True, exist_ok=True)

    with open(report_path / "bt_config.json", "w", encoding="utf-8") as f:
        json.dump(
            {k: str(v) if not isinstance(v, (int, float, str, bool, list, dict)) else v
             for k, v in config.items()},
            f, indent=2,
        )

    metrics_clean = {}
    for k, v in metrics.items():
        if k == "returns":
            continue
        if isinstance(v, (np.floating, float)):
            metrics_clean[k] = round(float(v), 6)
        elif isinstance(v, (np.integer, int)):
            metrics_clean[k] = int(v)
        else:
            metrics_clean[k] = str(v)

    with open(report_path / "bt_summary.json", "w", encoding="utf-8") as f:
        json.dump(metrics_clean, f, indent=2)

    returns = metrics.get("returns")
    if returns is not None and len(returns) > 0:
        plot_equity_curve(returns, str(report_path / "equity_curve.png"))
        plot_drawdown(returns, str(report_path / "drawdown.png"))

    predictions = result.get("predictions")
    if predictions is not None:
        plot_predictions_vs_actuals(
            predictions, str(report_path / "pred_vs_actual.png")
        )

    logger.info(f"Backtest report saved to: {report_path}")
    return str(report_path)