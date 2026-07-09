#!/usr/bin/env python3
"""
daily_inference.py — 每日信号生成 Pipeline

流程：
  1. 从 models/ 加载指定版本的模型 (Model Registry)
  2. 拉取最新行情数据（缓存 ≤7 天则跳过）
  3. 计算所有因子
  4. 模型推理 → 预测
  5. 生成入场/出场信号
  6. 保存信号到 data/signals/

用法：
  python scripts/daily_inference.py                    # 默认：V2 (118只)
  python scripts/daily_inference.py --model V1         # 用旧模型 (28只)
  python scripts/daily_inference.py --dry-run          # 预览不保存
  python scripts/daily_inference.py --date 2026-07-06  # 指定日期

输出：
  data/signals/{date}_signals.parquet   ← 当日信号
  data/signals/latest.parquet           ← 最新信号（覆盖）
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import date

import pandas as pd

# 项目根路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daily_inference")

from src.data.fetcher import fetch_all_data, extract_close_matrix, extract_volume_matrix
from src.factors.assembly import build_factor_panel
from src.models.registry import load_model, load_manifest, list_models
from src.models.signals import (
    generate_rebalance_calendar,
    generate_entry_signals,
    generate_exit_signals,
    filter_by_market_regime,
)
from src.config import SIGNALS_DIR


def parse_args():
    parser = argparse.ArgumentParser(description="每日信号生成 Pipeline")
    parser.add_argument(
        "--model", default="V2",
        help="模型版本，如 V1 (28只, fwd_21) 或 V2 (118只, fwd_10)，默认 V2"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="预览模式：打印信号但不保存文件"
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="指定信号日期 (YYYY-MM-DD)，默认今天"
    )
    parser.add_argument(
        "--force-fetch", action="store_true",
        help="强制重新拉取数据（忽略缓存）"
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="每期买入数，默认 5"
    )
    parser.add_argument(
        "--no-regime", action="store_true",
        help="关闭市场状态过滤器"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 1. 加载模型
    logger.info(f"📂 加载模型: {args.model}")
    try:
        model = load_model(args.model, "final")
        manifest = load_manifest(args.model)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"❌ 模型加载失败: {e}")
        logger.info("可用模型:")
        for m in list_models():
            logger.info(f"  {m.get('dir', '?')}")
        sys.exit(1)

    target = manifest.get("target", "forward_return_10")
    logger.info(f"   预测目标: {target}")
    logger.info(f"   特征数: {manifest.get('n_features', '?')}")

    # 2. 拉取数据
    logger.info("📥 加载行情数据...")
    df = fetch_all_data(force_refresh=args.force_fetch)
    if df.empty:
        logger.error("❌ 无数据可用")
        sys.exit(1)

    closes = extract_close_matrix(df)
    volumes = extract_volume_matrix(df)
    highs = df.xs("High", axis=1, level=1).sort_index(axis=1).sort_index()
    lows = df.xs("Low", axis=1, level=1).sort_index(axis=1).sort_index()

    # Explicit None check: [] (empty list) should not fallback to universe
    model_tickers = manifest.get("tickers") if manifest.get("tickers") is not None else manifest.get("universe")
    if model_tickers:
        tickers = [t for t in model_tickers if t in closes.columns]
        missing_tickers = sorted(set(model_tickers) - set(tickers))
        if missing_tickers:
            logger.error(f"❌ 行情缺少 {len(missing_tickers)} 个模型标的: {missing_tickers[:5]}...")
            sys.exit(1)
    else:
        n_tickers = manifest.get("n_tickers")
        if n_tickers and closes.shape[1] < int(n_tickers):
            logger.error(
                f"❌ {args.model} 需要 {n_tickers} 个标的，当前行情只有 {closes.shape[1]} 个；"
                "请恢复对应 universe 或改用匹配模型"
            )
            sys.exit(1)
        tickers = closes.columns[:int(n_tickers)].tolist() if n_tickers else closes.columns.tolist()
    if not tickers:
        logger.error("❌ 模型标的池与行情数据没有交集")
        sys.exit(1)
    closes = closes[tickers]
    volumes = volumes[tickers]
    highs = highs[tickers]
    lows = lows[tickers]

    logger.info(f"   数据: {closes.shape[0]} 天 × {closes.shape[1]} 个标的")

    # 3. 计算因子
    logger.info("🔢 计算因子...")
    factor_panel = build_factor_panel(closes, volumes, highs, lows)

    # 4. 预测
    logger.info("🧠 模型推理...")
    from src.data.preprocess import add_cross_sectional_features, clip_outliers
    from src.models.config import FEATURE_COLS, CLIP_STD_THRESHOLD

    try:
        data = factor_panel.stack(level="ticker", future_stack=True)
    except TypeError:
        data = factor_panel.stack(level="ticker")
    data.index.names = ["Date", "ticker"]

    # 添加横截面特征（rank + zscore），使特征数与训练时一致
    N_BASE_FEATURES = 13
    data = add_cross_sectional_features(data, FEATURE_COLS[:N_BASE_FEATURES])
    data = clip_outliers(data, FEATURE_COLS[:N_BASE_FEATURES], CLIP_STD_THRESHOLD)

    # Priority: model file feature list > manifest (manifest may be stale)
    feature_cols = model.feature_name() or (manifest.get("feature_cols") or manifest.get("features"))

    if feature_cols:
        # 用模型训练时的特征列（更精确）
        missing = [c for c in feature_cols if c not in data.columns]
        if missing:
            logger.error(f"❌ 缺少 {len(missing)} 个模型特征: {missing[:5]}...")
            sys.exit(1)
        data = data.dropna(subset=feature_cols)
        if data.empty:
            logger.error("❌ 特征全为空，无法生成预测")
            sys.exit(1)
        data["pred"] = model.predict(data[feature_cols].values)
    else:
        # 最终 fallback: 用 FEATURE_COLS（含 rank/zscore）
        data = data.dropna(subset=FEATURE_COLS)
        if data.empty:
            logger.error("❌ 特征全为空，无法生成预测")
            sys.exit(1)
        data["pred"] = model.predict(data[FEATURE_COLS].values)

    # 5. 生成信号
    logger.info("📈 生成交易信号...")
    signal_date = args.date or str(date.today())
    signal_date_ts = pd.Timestamp(signal_date)

    # 取最新一天的数据
    latest_data = data[data.index.get_level_values("Date") == data.index.get_level_values("Date").max()]

    # 展平为 ticker → pred 的 Series
    if isinstance(latest_data.index, pd.MultiIndex):
        tickers = latest_data.index.get_level_values("ticker")
        pred_values = pd.Series(
            latest_data["pred"].values,
            index=tickers,
        )
    else:
        pred_values = latest_data["pred"]

    logger.info(f"   最新预测 ({signal_date}): {len(pred_values)} 个标的")

    # 生成多日信号：往后延伸 N 天
    latest_market_date = closes.index[-1]
    if latest_market_date < signal_date_ts.normalize():
        hint = "美股最新可用数据可能尚未到当日收盘" if args.force_fetch else "如需刷新请加 --force-fetch"
        logger.warning(
            f"⚠️  行情最新日期 {latest_market_date.date()} 早于信号日期 "
            f"{signal_date_ts.date()}，{hint}"
        )

    bt_start = pd.bdate_range(signal_date_ts, signal_date_ts + pd.offsets.BDay(1))[0]
    bt_end = signal_date_ts + pd.Timedelta(days=90)  # 预测未来 90 天（~63 交易日），覆盖 max_hold=30 的出场信号
    if bt_end > closes.index[-1] + pd.Timedelta(days=120):
        bt_end = closes.index[-1] + pd.Timedelta(days=120)

    # 构建 predictions DataFrame for signal generation
    # 用最近一次预测作为未来信号的依据
    pred_dates = pd.bdate_range(bt_start, bt_end)
    signal_index = pd.bdate_range(bt_start, bt_end + pd.offsets.BDay(1))
    pred_dict = {t: pred_values.get(t, 0) for t in closes.columns}

    pred_rows = []
    for d in pred_dates:
        for t in sorted(closes.columns):
            pred_rows.append({"Date": d, "ticker": t, "pred": pred_dict.get(t, 0)})
    pred_df = pd.DataFrame(pred_rows)
    pred_df = pred_df.set_index(["Date", "ticker"])

    # 生成信号
    rebalance_dates = generate_rebalance_calendar(
        bt_start, bt_end, max_per_week=5
    )
    entries = generate_entry_signals(
        pred_df,
        rebalance_dates,
        pd.DataFrame(index=signal_index, columns=closes.columns),
        top_k=args.top_k, min_pred=0.0,
    )

    if not args.no_regime and "SPY" in closes.columns:
        entries = filter_by_market_regime(entries, closes["SPY"], ma_window=200)

    exits = generate_exit_signals(entries, min_hold=2, max_hold=30)

    # 6. 统计
    n_entries = entries.sum().sum()
    action_date = signal_index[1] if len(signal_index) > 1 else signal_index[0]
    tickers_with_signal = entries.columns[entries.loc[action_date]].tolist()

    logger.info(f"   信号覆盖: {len(pred_dates)} 个交易日")
    logger.info(f"   总入场信号: {int(n_entries)} 笔")
    logger.info(f"   下个交易日({action_date.date()})信号标的: {tickers_with_signal}")

    # 7. 保存
    if args.dry_run:
        logger.info("\n📋 DRY RUN — 信号预览:")
        logger.info(f"   日期范围: {pred_dates[0].date()} → {pred_dates[-1].date()}")
        logger.info(f"   入场信号: {int(n_entries)} 笔")
        logger.info(f"   下个交易日建议入场: {tickers_with_signal}")
        logger.info(f"   文件未保存 (--dry-run)")
    else:
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

        # 保存今天信号
        signal_date_str = signal_date_ts.date().isoformat()
        entries.to_parquet(SIGNALS_DIR / f"{signal_date_str}_entries.parquet")
        exits.to_parquet(SIGNALS_DIR / f"{signal_date_str}_exits.parquet")

        # 保存 latest（供执行层读取）
        entries.to_parquet(SIGNALS_DIR / "latest_entries.parquet")
        exits.to_parquet(SIGNALS_DIR / "latest_exits.parquet")

        # 保存预测值
        pred_df.to_parquet(SIGNALS_DIR / "latest_predictions.parquet")

        # 摘要
        summary = {
            "date": signal_date_str,
            "action_date": action_date.date().isoformat(),
            "model": args.model,
            "n_tickers": len(pred_values),
            "n_entry_signals": int(n_entries),
            "n_exit_signals": int(exits.sum().sum()),
            "action_entry_tickers": tickers_with_signal,
            "prediction_days": len(pred_dates),
        }
        import json
        with open(SIGNALS_DIR / "latest_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"💾 信号已保存: {SIGNALS_DIR}/")
        logger.info(f"   {signal_date_str}_entries.parquet — 完整入场信号")
        logger.info(f"   latest_entries.parquet — 最新完整信号")

    logger.info("✅ 信号生成完成")


if __name__ == "__main__":
    main()
