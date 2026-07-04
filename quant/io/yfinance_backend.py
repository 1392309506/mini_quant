"""
YFinanceBackend — yfinance 数据后端（默认）

在中国需要 HTTP 代理（v2rayN / Clash）才能正常访问。
"""

import time
import logging
from datetime import datetime
from typing import List, Optional

import pandas as pd
import requests

from quant.io.base import DataBackend
from quant.config import YF_BATCH_SIZE, YF_PAUSE, get_proxies

logger = logging.getLogger(__name__)


class YFinanceBackend(DataBackend):
    """yfinance 后端"""

    name = "yfinance"

    def fetch(
        self,
        symbols: List[str],
        start: str = "2015-01-01",
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        import yfinance as yf

        if end is None:
            end = datetime.today().strftime("%Y-%m-%d")

        session = self._make_session()
        all_frames: List[pd.DataFrame] = []

        for i in range(0, len(symbols), YF_BATCH_SIZE):
            batch = symbols[i : i + YF_BATCH_SIZE]
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
                        logger.warning("    空数据，可能限流")
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

        # 归一化 MultiIndex 列
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = pd.MultiIndex.from_tuples(
                [(t, f) for t, f in raw.columns],
                names=["ticker", "field"],
            )
        else:
            raw.columns = pd.MultiIndex.from_product([[symbols[0]], raw.columns])

        # 保留标准字段
        keep = ["Open", "High", "Low", "Close", "Volume"]
        raw = raw.loc[:, (slice(None), keep)]
        raw = raw.dropna(how="all").sort_index(axis=1)
        return raw

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    @staticmethod
    def _make_session() -> requests.Session:
        """构造带代理的 requests session"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        })
        proxies = get_proxies()
        if proxies:
            session.proxies.update(proxies)
            logger.info(f"🌐 yfinance 使用代理: {proxies['https']}")
        else:
            logger.warning(
                "⚠️  未配置代理，yfinance 在中国大概率被限流。"
                "请在 .env 中设置 HTTP_PROXY/HTTPS_PROXY"
            )
        return session