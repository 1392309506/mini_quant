"""
cache.py — parquet 缓存管理

职责：缓存读写 + 过期判断，不涉及业务逻辑。
"""

import logging
from typing import Optional

import pandas as pd

from quant.config import CACHE_FILE, STALE_DAYS, DATA_DIR

logger = logging.getLogger(__name__)


class CacheManager:
    """parquet 缓存管理器"""

    def __init__(self, cache_file: str = CACHE_FILE, stale_days: int = STALE_DAYS):
        self.cache_file = cache_file
        self.stale_days = stale_days

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def load(self) -> Optional[pd.DataFrame]:
        """加载缓存，过期或不存在时返回 None"""
        if not self.cache_file.exists():
            return None

        df = pd.read_parquet(self.cache_file)
        age = self._cache_age(df)
        if age <= self.stale_days:
            logger.info(f"📂 缓存有效（{age} 天前更新），跳过下载")
            return df

        logger.info(f"⚠️  缓存距今 {age} 天，重新下载")
        return None

    def load_or_fresh(self, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """加载缓存，除非 force_refresh 为 True"""
        if force_refresh:
            return None
        return self.load()

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------

    def save(self, df: pd.DataFrame) -> None:
        """写入 parquet"""
        DATA_DIR.mkdir(exist_ok=True)
        df.to_parquet(self.cache_file)
        logger.info(f"💾 已缓存到 {self.cache_file}（{df.shape[0]} 天 × {df.shape[1]} 列）")

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _cache_age(self, df: pd.DataFrame) -> int:
        """计算缓存距今多少天"""
        idx = df.index
        last = idx.max() if isinstance(idx, pd.DatetimeIndex) else idx.get_level_values("Date").max()
        return (pd.Timestamp.today() - last).days