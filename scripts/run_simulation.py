#!/usr/bin/env python3
"""
run_simulation.py — 模拟盘启动脚本

每日自动运行流程：
  1. 运行 daily_inference 生成交易信号
  2. 从 data/signals/ 读取最新信号
  3. 加载/恢复模拟账户状态
  4. 处理出场信号（先平仓再开仓）
  5. 硬止损检查
  6. 风控检查 → 入场信号开仓
  7. 更新持仓市值
  8. 输出每日状态摘要
  9. 保存状态（供下次运行恢复）

用法:
  python scripts/run_simulation.py                     # 默认运行（V1 模型，28只更稳定）
  python scripts/run_simulation.py --model V2          # 用 V2 模型
  python scripts/run_simulation.py --no-inference      # 不重新生成信号（使用已有信号）
  python scripts/run_simulation.py --initial-balance 50000  # 指定初始资金
  python scripts/run_simulation.py --scale 3           # 3x 杠杆（安全范围内）
  python scripts/run_simulation.py --top-k 10          # 每期最多买入 10 只

输出:
  data/execution_audit.csv          ← 审计日志（每笔交易）
  data/simulation_state.json        ← 状态快照（恢复用）
  data/simulation_log/<date>.log    ← 每日日志文件（可选）
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import date, datetime

# 项目根路径（确保 import 能找到 src/）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("simulation")

import pandas as pd
import numpy as np

from src.execution.broker import Broker
from src.execution.risk import RiskManager, RiskConfig
from src.execution.order_manager import OrderManager
from src.config import DATA_DIR, SIGNALS_DIR
from src.data.fetcher import fetch_all_data, extract_close_matrix


# ── 文件路径 ────────────────────────────────────────────────
STATE_FILE = DATA_DIR / "simulation_state.json"


# ── 参数解析 ────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="模拟盘启动脚本")
    parser.add_argument("--initial-balance", type=float, default=10_000,
                        help="初始资金（默认 $10,000）")
    parser.add_argument("--no-inference", action="store_true",
                        help="不重新运行 daily_inference，使用已有信号")
    parser.add_argument("--model", default="V1",
                        help="模型版本（默认 V1，模拟盘用 28 只更稳定）")
    parser.add_argument("--top-k", type=int, default=5,
                        help="每期买入数（默认 5）")
    parser.add_argument("--scale", type=float, default=7.0,
                        help="杠杆倍数（默认 7x，安全上限内）")
    return parser.parse_args()


# ── 状态管理 ────────────────────────────────────────────────

def load_state(broker) -> dict:
    """从文件恢复模拟账户状态（持仓和余额）。

    Returns
    -------
    dict : 额外元信息 {"run_count", "last_date"}，若首次运行则为空 dict。
    """
    meta = {}
    if not STATE_FILE.exists():
        logger.info("  ℹ️  无历史状态，使用初始余额")
        return meta

    with open(STATE_FILE, encoding="utf-8") as f:
        state = json.load(f)

    broker._sim_account["balance"] = state.get("balance", 10_000.0)
    broker._sim_account["equity"] = state.get("equity", 10_000.0)
    broker._sim_ticket = state.get("last_ticket", 100000)

    positions = state.get("positions", [])
    for p in positions:
        p["time"] = datetime.fromisoformat(p["time"])
        broker._sim_positions.append(p)

    meta["run_count"] = state.get("run_count", 0) + 1
    meta["last_date"] = state.get("date")
    logger.info(
        f"  ✅ 状态恢复: balance={broker._sim_account['balance']:.2f}, "
        f"持仓={len(positions)} 笔, 运行次数={meta['run_count']}"
    )
    return meta


def save_state(broker, meta: dict):
    """保存模拟账户状态到文件。"""
    positions = []
    for p in broker._sim_positions:
        pos = dict(p)
        if isinstance(pos.get("time"), datetime):
            pos["time"] = pos["time"].isoformat()
        positions.append(pos)

    state = {
        "date": date.today().isoformat(),
        "balance": broker._sim_account["balance"],
        "equity": broker._sim_account["equity"],
        "last_ticket": broker._sim_ticket,
        "positions": positions,
        "run_count": meta.get("run_count", 0),
        "updated_at": datetime.now().isoformat(),
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ── 信号读取 ────────────────────────────────────────────────

def read_signals() -> dict:
    """从 data/signals/ 读取最新信号。"""
    signals = {}

    entries_path = SIGNALS_DIR / "latest_entries.parquet"
    exits_path = SIGNALS_DIR / "latest_exits.parquet"
    pred_path = SIGNALS_DIR / "latest_predictions.parquet"
    summary_path = SIGNALS_DIR / "latest_summary.json"

    if entries_path.exists():
        signals["entries"] = pd.read_parquet(entries_path)
    else:
        signals["entries"] = None

    if exits_path.exists():
        signals["exits"] = pd.read_parquet(exits_path)
    else:
        signals["exits"] = None

    if summary_path.exists():
        with open(summary_path, encoding="utf-8") as f:
            signals["summary"] = json.load(f)
    else:
        signals["summary"] = None

    return signals


# ── 开盘价获取 ──────────────────────────────────────────────

def get_latest_prices() -> dict:
    """从缓存行情数据获取最新收盘价。

    Returns {ticker: price}, 获取失败时返回空 dict。
    """
    try:
        df = fetch_all_data(force_refresh=False)
        closes = extract_close_matrix(df)
        latest = closes.iloc[-1]
        return {t: float(latest[t]) for t in latest.index if pd.notna(latest[t])}
    except Exception as e:
        logger.warning(f"⚠️  获取最新行情失败: {e}")
        return {}


# ── 风控配置 ────────────────────────────────────────────────

def create_risk_config(max_leverage: float) -> RiskConfig:
    """创建风控配置（模拟盘使用保守参数）。"""
    return RiskConfig(
        max_leverage=max_leverage,        # 杠杆上限（默认 7x）
        max_daily_trades=4,               # 每日最多 4 笔
        max_daily_loss_pct=0.05,          # 单日最大亏损 5%
        hard_stop_loss_pct=0.08,          # 单笔硬止损 8%
        max_loss_per_trade_pct=0.02,      # 单笔最大风险 2%
        max_position_pct=0.30,            # 单标的暴露上限 30%
    )


# ── 每日摘要 ────────────────────────────────────────────────

def print_summary(broker, risk_mgr, order_mgr, meta: dict, signals: dict,
                  initial_balance: float = 10_000):
    """打印每日状态摘要。"""
    account = broker.get_account()
    positions = broker.get_positions()
    summary = signals.get("summary", {})
    today = date.today()

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"📊  模拟盘状态 — {today.isoformat()}")
    logger.info("=" * 60)

    # 账户概览
    nlv = (account["equity"] / initial_balance - 1) * 100
    logger.info(f"权益: {account['equity']:>10,.2f}  余额: {account['balance']:>10,.2f}")
    logger.info(f"净值变化: {nlv:+.2f}%  |  持仓: {len(positions)} 笔")

    # 持仓明细
    if len(positions) > 0:
        logger.info("")
        logger.info(f"{'ticket':<8} {'symbol':<7} {'方向':<4} {'数量':<7} "
                    f"{'开仓价':<9} {'盈亏':<10}")
        logger.info("-" * 50)
        for _, pos in positions.iterrows():
            pnl = pos.get("profit", 0)
            logger.info(f"{int(pos['ticket']):<8} "
                        f"{pos['symbol']:<7} "
                        f"{'多' if pos['type'] == 'buy' else '空':<4} "
                        f"{pos['volume']:<7.2f} "
                        f"{pos['price_open']:<9.2f} "
                        f"{pnl:<+10.2f}")

    # 今日信号
    action_entry = summary.get("action_entry_tickers", [])
    if action_entry:
        logger.info(f"\n📈 入场信号: {action_entry}")
    else:
        logger.info(f"\n进场信号: 无")

    # 当日交易统计
    daily_stats = risk_mgr.get_daily_stats()
    logger.info(f"📋 今日交易: {daily_stats['n_trades']} 笔 | "
                f"上限 {daily_stats['max_trades']}")
    daily_pnl = daily_stats.get("pnl", 0)
    logger.info(f"💰 今日盈亏: {daily_pnl:+,.2f}")

    # 运行统计
    audit = order_mgr.get_audit_log()
    logger.info(f"📁 审计日志: {len(audit)} 条总计")
    logger.info(f"🔁 运行次数: {meta.get('run_count', 0)}")

    logger.info("=" * 60)


# ── 计算仓位 ────────────────────────────────────────────────

def calc_volume(equity: float, price: float, top_k: int,
                position_scale: float) -> float:
    """计算每只股票的买入数量（等权分配，受风控约束）。

    volume = (equity / top_k * position_scale) / price
    但不超过单笔风险上限约束：

      风控规则:  单笔最大亏损 ≤ 2% × equity
                 硬止损 8%
     → 最大敞口 = equity × 2% / 8% × 0.995（留 0.5% 浮点安全裕量）≈ equity × 24.875%
    """
    target_exposure = (equity / top_k) * position_scale
    max_risk_exposure = equity * (0.02 / 0.08) * 0.995
    exposure = min(target_exposure, max_risk_exposure)
    if price <= 0:
        return 0
    return round(exposure / price, 2)


# ── 主流程 ──────────────────────────────────────────────────

def main():
    args = parse_args()
    today = date.today()

    # 1. 运行 daily_inference 生成信号
    if not args.no_inference:
        logger.info("📡 运行 daily_inference 生成信号...")
        from scripts.daily_inference import main as inference_main
        # 构造 daily_inference 参数（--dry-run 去掉，需要保存文件）
        infer_args = [
            "daily_inference.py",
            "--model", args.model,
            "--top-k", str(args.top_k),
        ]
        sys.argv = infer_args
        try:
            inference_main()
        except SystemExit:
            pass
        logger.info("✅ 信号生成完成")
    else:
        logger.info("📡 跳过 daily_inference（--no-inference）")

    # 2. 初始化执行层
    logger.info("🏦 初始化模拟账户...")
    broker = Broker(simulate=True)
    broker._sim_account["balance"] = args.initial_balance
    broker._sim_account["equity"] = args.initial_balance

    risk_config = create_risk_config(max_leverage=args.scale)
    risk_mgr = RiskManager(config=risk_config)
    order_mgr = OrderManager(broker)

    # 3. 恢复历史状态
    meta = load_state(broker)

    # 4. 读取信号
    signals = read_signals()
    if signals["entries"] is None:
        logger.error("❌ 无信号文件，请先运行 daily_inference")
        sys.exit(1)

    # 5. 获取最新行情（用于持仓定价和交易）
    prices = get_latest_prices()
    if prices:
        broker.update_sim_prices(prices)
        logger.info(f"📊 行情更新: {len(prices)} 个标的")

    # 6. 处理出场信号（先平仓再开仓）
    if signals["exits"] is not None:
        exits_df = signals["exits"]
        # 找到最近一个交易日的出场信号
        exit_dates = exits_df.index[exits_df.index <= today.isoformat()]
        if len(exit_dates) > 0:
            exit_date = exit_dates[-1]
            exit_row = exits_df.loc[exit_date]
            to_close = exit_row.index[exit_row].tolist()
            if to_close:
                logger.info(f"📉 出场标的: {to_close}")
                positions = broker.get_positions()
                for _, pos in positions.iterrows():
                    if pos["symbol"] in to_close:
                        result = order_mgr.close_position(
                            int(pos["ticket"]), reason="signal"
                        )
                        if result["status"] == "filled":
                            risk_mgr.record_trade(pnl=result.get("pnl", 0))
                            logger.info(f"  ✅ 平仓: {pos['symbol']}")

    # 7. 硬止损检查
    positions = broker.get_positions()
    stop_losses = risk_mgr.enforce_stop_loss(positions)
    for sl in stop_losses:
        logger.warning(f"🛑 硬止损触发: {sl['symbol']} ({sl['reason']})")
        result = order_mgr.close_position(sl["ticket"], reason="stop_loss")
        if result["status"] == "filled":
            risk_mgr.record_trade(pnl=result.get("pnl", 0))

    # 8. 处理入场信号
    if signals["entries"] is not None:
        entries_df = signals["entries"]
        entry_dates = entries_df.index[entries_df.index <= today.isoformat()]
        if len(entry_dates) > 0:
            entry_date = entry_dates[-1]
            entry_row = entries_df.loc[entry_date]
            to_buy = entry_row.index[entry_row].tolist()
            if to_buy:
                logger.info(f"📈 入场标的: {to_buy}")
                account = broker.get_account()
                positions = broker.get_positions()
                equity = account.get("equity", args.initial_balance)

                for ticker in to_buy:
                    # 检查是否已持仓
                    if len(positions) > 0 and ticker in positions["symbol"].values:
                        logger.info(f"  ℹ️  已持仓 {ticker}，跳过")
                        continue

                    price = prices.get(ticker, 100.0)
                    volume = calc_volume(equity, price, args.top_k, args.scale)
                    if volume <= 0:
                        logger.warning(f"  ⚠️  {ticker} 价格无效，跳过")
                        continue

                    order = {
                        "symbol": ticker,
                        "side": "buy",
                        "volume": volume,
                        "price": price,
                    }
                    ok, reason = risk_mgr.check_order(order, account, positions)
                    if ok:
                        result = order_mgr.place_market(
                            ticker, "buy", volume, reason="signal"
                        )
                        if result["status"] == "filled":
                            risk_mgr.record_trade()
                            logger.info(f"  ✅ 开仓: {ticker} {volume:.1f}股 @{price:.2f}")
                    else:
                        logger.warning(f"  ⛔ 风控拒绝 {ticker}: {reason}")

    # 9. 用最新价格更新持仓市值
    if prices:
        broker.update_sim_prices(prices)

    # 10. 打印每日摘要
    print_summary(broker, risk_mgr, order_mgr, meta, signals,
                  initial_balance=args.initial_balance)

    # 11. 保存状态
    save_state(broker, meta)
    logger.info(f"💾 状态已保存: {STATE_FILE}")


if __name__ == "__main__":
    main()
