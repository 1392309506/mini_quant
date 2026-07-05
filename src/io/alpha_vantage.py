"""
AlphaVantageBackend — Alpha Vantage 兜底后端

无需代理，但免费层仅返回最近 100 天数据（compact）。
"""

import time
import logging
from typing import List, Optional, Dict

import pandas as pd
import requests

from src.io.base import DataBackend
from src.config import AV_CALL_INTERVAL, get_proxies, get_av_key

logger = logging.getLogger(__name__)


class AlphaVantageBackend(DataBackend):
    """Alpha Vantage 兜底后端"""

    name = "alpha_vantage"

    def fetch(
        self,
        symbols: List[str],
        start: str = "",       # AV 免费层忽略 start/end
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        logger.warning(
            "⚠️  Alpha Vantage 免费层仅返回最近 100 天数据，"
            "不足以计算 200 日均线等因子。建议优先使用 yfinance + 代理。"
        )

        all_data: Dict[str, pd.DataFrame] = {}
        for i, sym in enumerate(symbols):
            logger.info(f"  [{i + 1}/{len(symbols)}] {sym}")
            data = self._request({
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

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _request(self, params: Dict) -> Optional[dict]:
        """发送 AV API 请求并处理限流/错误"""
        key = get_av_key()
        if not key:
            logger.error("未配置 ALPHA_VANTAGE_KEY，无法使用 Alpha Vantage 兜底")
            return None

        params["apikey"] = key
        proxies = get_proxies()

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