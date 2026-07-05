#!/usr/bin/env python3
"""
data_fetcher.py — 入口脚本

用法:
  python data_fetcher.py                     # 增量更新（有缓存则跳过）
  python data_fetcher.py --force             # 强制刷新所有数据
  python data_fetcher.py --max 5             # 只下载 5 个标的
"""

import sys
import logging
from src.data.fetcher import (
    fetch_all_data,
    extract_close_matrix,
    check_data_integrity,
    print_integrity_report,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("data_fetcher")

if __name__ == "__main__":
    force = "--force" in sys.argv[1:]
    max_sym = None

    for i, arg in enumerate(sys.argv):
        if arg == "--max" and i + 1 < len(sys.argv):
            max_sym = int(sys.argv[i + 1])

    logger.info("📥 数据下载启动")
    df = fetch_all_data(force_refresh=force, max_symbols=max_sym or 20)

    if df.empty:
        logger.error("❌ 未获取到数据，请检查 API Key 和网络连接")
        sys.exit(1)

    closes = extract_close_matrix(df)
    logger.info(f"📊 收盘价矩阵: {closes.shape}, {len(closes.columns)} 个标的")

    issues = check_data_integrity(df)
    print_integrity_report(issues)

    logger.info("✅ 完成")