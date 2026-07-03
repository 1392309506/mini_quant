"""
Fetcher — 数据下载与管理模块

支持两个数据后端，通过 .env 的 DATA_BACKEND 配置：
  - yfinance (默认): 数据完整、历史长，但在中国需代理（v2rayN/clash）
  - alpha_vantage:   免费层仅 100 天 compact 数据，无需代理，作为兜底

.env 配置示例:
  DATA_BACKEND=yfinance
  HTTP_PROXY=http://127.0.0.1:10808      # v2rayN 默认 HTTP 端口
  HTTPS_PROXY=http://127.0.0.1:10808
  ALPHA_VANTAGE_KEY=你的KEY               # AV 兜底用

输出：MultiIndex DataFrame (列: ticker × OHLCV)，缓存到 data/market_data.parquet
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import pandas as pd
import numpy as np
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

CACHE_FILE = DATA_DIR / "market_data.parquet"

# 交易标的池
TRADE_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "NVDA", "TSLA", "JPM", "V",
    "JNJ", "WMT", "PG", "MA", "UNH",
    "HD", "DIS", "NFLX", "ADBE", "CRM",
    "BAC", "KO", "COST", "PEP", "CVX",
    "GLD", "QQQ",
]

STALE_DAYS = 7  # 缓存多少天后视为过期

# Alpha Vantage 免费限制：5 次/分钟，500 次/天
AV_CALL_INTERVAL = 12.0

# yfinance 批量下载间隔（避免限流）
YF_BATCH_SIZE = 8
YF_PAUSE = 0.5


# ---------------------------------------------------------------------------
# .env 读取
# ---------------------------------------------------------------------------

def _load_env() -> Dict[str, str]:
    """从 .env 文件读取配置（不依赖 python-dotenv，保持零额外依赖）"""
    env: Dict[str, str] = {}
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("\"'")
    # 环境变量优先级高于 .env
    for k in ["DATA_BACKEND", "HTTP_PROXY", "HTTPS_PROXY", "ALPHA_VANTAGE_KEY"]:
        if k in os.environ:
            env[k] = os.environ[k]
    return env


def _get_backend() -> str:
    return _load_env().get("DATA_BACKEND", "yfinance").lower()


def _get_proxies() -> Optional[Dict[str, str]]:
    env = _load_env()
    proxy = env.get("HTTPS_PROXY") or env.get("HTTP_PROXY")
    if not proxy:
        return None
    return {"http": env.get("HTTP_PROXY", proxy), "https": proxy}


# ---------------------------------------------------------------------------
# yfinance 后端（默认，需代理）
# ---------------------------------------------------------------------------

def _make_yf_session() -> requests.Session:
    """构造带代理的 requests session 供 yfinance 使用"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    })
    proxies = _get_proxies()
    if proxies:
        session.proxies.update(proxies)
        logger.info(f"🌐 yfinance 使用代理: {proxies['https']}")
    else:
        logger.warning("⚠️  未配置代理，yfinance 在中国大概率被限流。"
                       "请在 .env 中设置 HTTP_PROXY/HTTPS_PROXY（如 http://127.0.0.1:10808）")
    return session


def fetch_yfinance(
    symbols: List[str],
    start: str = "2015-01-01",
    end: Optional[str] = None,
) -> pd.DataFrame:
    """
    用 yfinance 批量下载日线数据。

    Returns
    -------
    pd.DataFrame
        MultiIndex columns: (ticker, field)，field ∈ {Open,High,Low,Close,Volume}
    """
    import yfinance as yf

    if end is None:
        end = datetime.today().strftime("%Y-%m-%d")

    session = _make_yf_session()
    all_frames: List[pd.DataFrame] = []

    # 分批下载，避免一次请求过多标的触发限流
    for i in range(0, len(symbols), YF_BATCH_SIZE):
        batch = symbols[i:i + YF_BATCH_SIZE]
        logger.info(f"  [{i + 1}~{i + len(batch)}/{len(symbols)}] {batch}")
        for attempt in range(3):
            try:
                raw = yf.download(
                    " ".join(batch),
                    start=start,
                    end=end,
                    progress=False,
                    auto_adjust=False,
                    actions=False,
                    session=session,
                    group_by="ticker",
                )
                if not raw.empty:
                    all_frames.append(raw)
                else:
                    logger.warning(f"    空数据，可能限流")
                break
            except Exception as e:
                logger.warning(f"    下载失败 (attempt {attempt + 1}/3): {str(e)[:80]}")
                time.sleep(5 * (attempt + 1))
        else:
            logger.error(f"    批次 {batch} 3 次重试均失败")
        time.sleep(YF_PAUSE)

    if not all_frames:
        raise RuntimeError("yfinance 所有批次下载均失败——请检查代理是否开启")

    raw = pd.concat(all_frames, axis=1)
    # 归一化列格式为 (ticker, field)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = pd.MultiIndex.from_tuples(
            [(t, f) for t, f in raw.columns],
            names=["ticker", "field"],
        )
    else:
        # 单标的情况
        sym = symbols[0]
        raw.columns = pd.MultiIndex.from_product([[sym], raw.columns])

    # 标准化字段名
    rename = {"Adj Close": "Close"}  # 用 adjusted close 作为 Close
    raw = raw.rename(columns=rename)
    keep = ["Open", "High", "Low", "Close", "Volume"]
    raw = raw.xs(slice(None), axis=1, level=1) if False else raw  # noop placeholder
    # 选取需要的字段
    fields_present = [f for f in keep if (raw.columns.get_level_values(1) == f).any()]
    raw = raw.loc[:, (slice(None), fields_present)]

    raw = raw.dropna(how="all").sort_index(axis=1)
    return raw


# ---------------------------------------------------------------------------
# Alpha Vantage 后端（兜底，无需代理，但免费层仅 100 天）
# ---------------------------------------------------------------------------

def _av_request(params: Dict) -> Optional[dict]:
    env = _load_env()
    key = env.get("ALPHA_VANTAGE_KEY")
    if not key:
        logger.error("未配置 ALPHA_VANTAGE_KEY，无法使用 Alpha Vantage 兜底")
        return None

    params["apikey"] = key
    proxies = _get_proxies()

    for attempt in range(3):
        try:
            time.sleep(AV_CALL_INTERVAL)
            resp = requests.get(
                "https://www.alphavantage.co/query",
                params=params,
                timeout=30,
                proxies=proxies,
            )
            if resp.status_code == 429:
                logger.warning("AV 限流，等待 60s...")
                time.sleep(60)
                continue
            data = resp.json()
            if "Error Message" in data:
                logger.error(f"AV API 错误: {data['Error Message']}")
                return None
            if "Information" in data:
                logger.warning(f"AV 提示: {data['Information'][:120]}")
                return None
            if "Note" in data:
                logger.warning(f"AV 频率提醒: {data['Note'][:100]}")
                time.sleep(60)
                continue
            return data
        except requests.exceptions.Timeout:
            logger.warning(f"AV 请求超时，重试 {attempt + 1}/3")
            time.sleep(30)
        except requests.exceptions.RequestException as e:
            logger.warning(f"AV 连接失败，重试 {attempt + 1}/3: {str(e)[:60]}")
            time.sleep(30)
    return None


def fetch_alpha_vantage(symbols: List[str]) -> pd.DataFrame:
    """Alpha Vantage 批量下载。注意：免费层 outputsize=compact 仅返回最近 100 天。"""
    logger.warning("⚠️  Alpha Vantage 免费层仅返回最近 100 天数据，"
                   "不足以计算 200 日均线等因子。建议优先使用 yfinance + 代理。")

    all_data: Dict[str, pd.DataFrame] = {}
    for i, sym in enumerate(symbols):
        logger.info(f"  [{i + 1}/{len(symbols)}] {sym}")
        data = _av_request({
            "function": "TIME_SERIES_DAILY",
            "symbol": sym,
            "outputsize": "compact",
            "datatype": "json",
        })
        if data is None or "Time Series (Daily)" not in data:
            logger.warning(f"    ❌ {sym} 下载失败")
            continue

        rows = []
        for date_str, v in data["Time Series (Daily)"].items():
            rows.append({
                "Date": pd.Timestamp(date_str),
                "Open": float(v["1. open"]),
                "High": float(v["2. high"]),
                "Low": float(v["3. low"]),
                "Close": float(v["4. close"]),
                "Volume": int(v["5. volume"]),
            })
        df = pd.DataFrame(rows).sort_values("Date").set_index("Date")
        all_data[sym] = df
        logger.info(f"    ✅ {sym}: {len(df)} 条")

    if not all_data:
        raise RuntimeError("Alpha Vantage 所有标的下载均失败")

    parts = []
    for sym, df in all_data.items():
        df.columns = pd.MultiIndex.from_product([[sym], df.columns])
        parts.append(df)
    return pd.concat(parts, axis=1).sort_index(axis=1)


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
    # 缓存检查
    if not force_refresh and CACHE_FILE.exists():
        cached = pd.read_parquet(CACHE_FILE)
        idx = cached.index
        last = idx.max() if isinstance(idx, pd.DatetimeIndex) else idx.get_level_values("Date").max()
        age = (pd.Timestamp.today() - last).days
        if age <= STALE_DAYS:
            logger.info(f"📂 缓存有效（{age} 天前更新），跳过下载")
            return cached
        logger.info(f"⚠️  缓存距今 {age} 天，重新下载")

    symbols = list(symbols or TRADE_UNIVERSE)
    if max_symbols:
        symbols = symbols[:max_symbols]

    backend = (backend or _get_backend()).lower()
    logger.info(f"🌐 数据后端: {backend}，标的数: {len(symbols)}")

    if backend == "yfinance":
        df = fetch_yfinance(symbols)
    elif backend in ("alpha_vantage", "av"):
        df = fetch_alpha_vantage(symbols)
    else:
        raise ValueError(f"未知后端: {backend}（应为 yfinance 或 alpha_vantage）")

    df.to_parquet(CACHE_FILE)
    logger.info(f"💾 已缓存到 {CACHE_FILE}（{df.shape[0]} 天 × {df.shape[1]} 列）")
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
