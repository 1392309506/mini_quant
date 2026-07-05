"""
DataBackend — 数据后端抽象协议

所有数据源（yfinance / Alpha Vantage / MT5 等）必须实现此接口。
"""

from abc import ABC, abstractmethod
from typing import List, Optional

import pandas as pd


class DataBackend(ABC):
    """数据后端协议：fetch(symbols) → MultiIndex DataFrame"""

    @abstractmethod
    def fetch(
        self,
        symbols: List[str],
        start: str = "2015-01-01",
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        下载日线行情数据。

        Parameters
        ----------
        symbols : list of str
            股票代码列表
        start, end : str
            日期范围 "YYYY-MM-DD"

        Returns
        -------
        pd.DataFrame
            MultiIndex columns: (ticker, field)，field ∈ {Open,High,Low,Close,Volume}
            行 = DatetimeIndex
        """
        ...