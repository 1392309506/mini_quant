"""
Fetcher — 数据下载与管理模块（高层编排层）

通过 io/ 子包中的 DataBackend 注册表分发到具体后端。
yfinance / Alpha Vantage 的具体实现已移至 quant/io/。
"""

import json
import logging
from typing import Optional, List, Dict

import pandas as pd
import numpy as np

from quant.config import (
    DATA_DIR,
    CACHE_FILE,
    STALE_DAYS,
    get_backend as get_config_backend,
)
from quant.universe import TRADE_UNIVERSE
from quant.io import get_backend as resolve_backend
from quant.io.cache import CacheManager

logger = logging.getLogger(__name__)

DATA_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------

def fetch_all_data(
    symbols: Optional[List[str]] = None,
    force_refresh: bool = False,
    max_symbols: Optional[int] = None,
    backend: Optional[str] = None,
) -> pd.DataFrame:
    """
    批量获取股票日线数据，自动选择后端并缓存。

    Parameters
    ----------
    symbols : list, optional
        标的列表，默认 TRADE_UNIVERSE
    force_refresh : bool
        True 则忽略缓存
    max_symbols : int, optional
        限制下载数量（测试用）
    backend : str, optional
        'yfinance' 或 'alpha_vantage'，默认从 .env 读取
    """
    cache = CacheManager(CACHE_FILE, STALE_DAYS)
    cached = cache.load_or_fresh(force_refresh)
    if cached is not None:
        return cached

    symbols = list(symbols or TRADE_UNIVERSE)
    if max_symbols:
        symbols = symbols[:max_symbols]

    backend_name = (backend or get_config_backend()).lower()
    logger.info(f"🌐 数据后端: {backend_name}，标的数: {len(symbols)}")

    instance = resolve_backend(backend_name)
    df = instance.fetch(symbols)

    cache.save(df)
    return df


# ---------------------------------------------------------------------------
# 数据完整性检查
# ---------------------------------------------------------------------------

def check_data_integrity(df: pd.DataFrame) -> Dict[str, list]:
    """检查 MultiIndex DataFrame 的数据完整性"""
    issues: Dict[str, list] = {}
    tickers = df.columns.get_level_values(0).unique()

    for t in tickers:
        tk_issues = []
        prices = df[t]

        nan_count = prices.isna().sum().sum()
        if nan_count > 0:
            nan_fields = [c for c in prices.columns if prices[c].isna().any()]
            nan_ratio = nan_count / (prices.shape[0] * prices.shape[1])
            tk_issues.append(f"缺失值: {nan_count}个({nan_ratio:.1%}), 字段: {nan_fields}")

        for col in ["Open", "High", "Low", "Close"]:
            if col in prices.columns:
                neg = (prices[col].dropna() < 0).sum()
                if neg > 0:
                    tk_issues.append(f"负{col}价格: {neg}个")

        if "Volume" in prices.columns:
            vol = prices["Volume"].dropna()
            zero_vol = (vol == 0).sum()
            if zero_vol > 0 and zero_vol / max(vol.notna().sum(), 1) > 0.05:
                tk_issues.append(f"零成交量: {zero_vol}个")

        close = prices["Close"].dropna() if "Close" in prices.columns else pd.Series(dtype=float)
        if len(close) > 1:
            daily_ret = close.pct_change().dropna()
            outliers = daily_ret[abs(daily_ret) > 0.20]
            if len(outliers) > 0:
                tk_issues.append(f"异常波动>±20%: {len(outliers)}天")

        if len(close) < 200:
            tk_issues.append(f"数据偏少: {len(close)}天 (<200，无法算 MA200)")

        if len(close) > 0:
            last = close.index[-1]
            age = (pd.Timestamp.today() - last).days
            status = "新鲜" if age <= STALE_DAYS else f"老旧({age}天前)"
            tk_issues.append(f"最后更新: {last.date()}({status})")

        issues[t] = tk_issues

    return issues


def print_integrity_report(issues: Dict[str, list]) -> None:
    """打印完整性报告"""
    total = len(issues)
    ok_count = sum(1 for v in issues.values() if v and all("新鲜" in i for i in v))
    warn_count = total - ok_count
    logger.info(f"检查: OK={ok_count}({ok_count / total:.0%}), 需关注={warn_count}/{total}")

    for ticker, tk_issues in issues.items():
        if not tk_issues:
            continue
        if not all("新鲜" in i for i in tk_issues):
            for msg in tk_issues:
                logger.info(f"  [{ticker}] {msg}")


# ---------------------------------------------------------------------------
# 便利函数
# ---------------------------------------------------------------------------

def extract_close_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """提取收盘价矩阵"""
    return df.xs("Close", axis=1, level=1).sort_index(axis=1).sort_index()


def extract_volume_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """提取成交量矩阵"""
    return df.xs("Volume", axis=1, level=1).sort_index(axis=1).sort_index()


def load_data() -> pd.DataFrame:
    """一键加载数据"""
    return fetch_all_data(force_refresh=False)


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("Fetcher 启动")
    df = fetch_all_data(force_refresh=False)
    closes = extract_close_matrix(df)
    logger.info(f"收盘价矩阵: {closes.shape}, {len(closes.columns)} 个标的")
    issues = check_data_integrity(df)
    print_integrity_report(issues)
    logger.info("完成")
