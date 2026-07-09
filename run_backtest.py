#!/usr/bin/env python3
"""
run_backtest.py — 回测入口脚本

从已保存实验的 OOS 预测运行回测。

用法:
  python run_backtest.py <exp_id>              # 基于实验 ID 运行回测
  python run_backtest.py <exp_id> --top 10     # 覆盖 TOP_K
  python run_backtest.py <exp_id> --target 21  # 使用 forward_return_21 的预测
  python run_backtest.py <exp_id> --no-regime  # 关闭市场状态过滤器
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_backtest")

from src.data.fetcher import fetch_all_data, extract_close_matrix
from src.config import EXPERIMENTS_DIR
from src.experiment import load_experiment
from src.backtest.engine import run_full_backtest
from src.backtest.reporting import (
    print_backtest_summary,
    save_backtest_report,
)
from src.backtest.config import (
    TOP_K,
    MIN_HOLD,
    MAX_HOLD,
    SLIPPAGE,
    TOTAL_COST_PER_SIDE,
    INITIAL_CASH,
    MAX_REBALANCES_PER_WEEK,
    USE_REGIME_FILTER,
    REGIME_MA_WINDOW,
    MIN_PRED,
    POSITION_SCALE,
)


def parse_args():
    """解析命令行参数"""
    args = {
        "exp_id": None,
        "top_k": TOP_K,
        "min_pred": MIN_PRED,
        "no_regime": "--no-regime" in sys.argv[1:],
    }

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg.startswith("--"):
            if arg == "--top" and i + 1 < len(sys.argv):
                args["top_k"] = int(sys.argv[i + 1])
            elif arg == "--min-pred" and i + 1 < len(sys.argv):
                args["min_pred"] = float(sys.argv[i + 1])
            continue
        if args["exp_id"] is None and not arg.startswith("--"):
            args["exp_id"] = arg

    return args


def main():
    args = parse_args()

    if not args["exp_id"]:
        # 列出所有实验
        exp_root = EXPERIMENTS_DIR
        if exp_root.exists():
            exps = sorted(exp_root.iterdir())
            if exps:
                logger.info("可用实验:")
                for exp in exps:
                    summary_path = exp / "summary.json"
                    if summary_path.exists():
                        import json
                        with open(summary_path) as f:
                            s = json.load(f)
                        logger.info(
                            f"  {exp.name} — "
                            f"avg_val_rmse={s.get('avg_val_rmse', 'N/A')}, "
                            f"target={s.get('target', 'N/A')}"
                        )
                    else:
                        logger.info(f"  {exp.name}")
            else:
                logger.info("没有已保存的实验，请先运行: python train_model.py")
        else:
            logger.info("实验目录不存在，请先运行: python train_model.py")
        sys.exit(1)

    exp_path = EXPERIMENTS_DIR / args["exp_id"]
    if not exp_path.exists():
        logger.error(f"❌ 实验不存在: {exp_path}")
        sys.exit(1)

    # 1. 加载实验
    logger.info(f"📂 加载实验: {args['exp_id']}")
    exp = load_experiment(str(exp_path))

    pred_oos = exp["pred_oos"]
    if pred_oos is None or len(pred_oos) == 0:
        logger.error("❌ 实验中没有 OOS 预测数据")
        sys.exit(1)

    logger.info(f"   加载 {len(pred_oos)} 条 OOS 预测")

    # 2. 加载 OHLCV 数据
    logger.info("📥 加载行情数据...")
    df = fetch_all_data(force_refresh=False)
    if df.empty:
        logger.error("❌ 无数据可用")
        sys.exit(1)

    opens = df.xs("Open", axis=1, level=1).sort_index(axis=1).sort_index()
    closes = extract_close_matrix(df)
    spy_close = closes.get("SPY")

    # 3. 设置回测参数
    bt_config = {
        "top_k": args["top_k"],
        "min_pred": args["min_pred"],
        "min_hold": MIN_HOLD,
        "max_hold": MAX_HOLD,
        "max_rebalances_per_week": MAX_REBALANCES_PER_WEEK,
        "one_way_fee": TOTAL_COST_PER_SIDE,
        "slippage": SLIPPAGE,
        "init_cash": INITIAL_CASH,
        "position_scale": POSITION_SCALE,
        "use_regime_filter": not args["no_regime"] if args["no_regime"] else USE_REGIME_FILTER,
        "regime_ma_window": REGIME_MA_WINDOW,
    }

    logger.info(
        f"📋 回测配置: top_k={bt_config['top_k']}, "
        f"hold=[{bt_config['min_hold']},{bt_config['max_hold']}], "
        f"scale={bt_config['position_scale']}x, "
        f"cost={bt_config['one_way_fee']:.2%}, "
        f"regime_filter={bt_config['use_regime_filter']}"
    )

    # 4. 运行回测
    result = run_full_backtest(
        predictions=pred_oos,
        open_price=opens,
        close=closes,
        bt_config=bt_config,
        spy_close=spy_close,
    )

    # 5. 打印摘要
    print_backtest_summary(result["metrics"])

    # 6. 保存报告
    result["predictions"] = pred_oos
    report_path = save_backtest_report(
        bt_dir=str(exp_path),
        bt_id="backtest",
        metrics=result["metrics"],
        config=bt_config,
        result=result,
    )

    logger.info(f"✅ 回测完成，报告已保存: {report_path}")


if __name__ == "__main__":
    main()