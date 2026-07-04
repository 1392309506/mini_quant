"""
quant.io — 数据后端 IO 层

提供 DataBackend 协议和注册表，支持按名称获取后端实例。
开闭原则：加新数据源只需实现 DataBackend 并注册，不改分发代码。

用法:
    from quant.io import get_backend
    backend = get_backend("yfinance")
    df = backend.fetch(["AAPL", "MSFT"])
"""

from typing import Type

from quant.io.base import DataBackend
from quant.io.yfinance_backend import YFinanceBackend
from quant.io.alpha_vantage import AlphaVantageBackend
from quant.io.mt5_backend import MT5Backend

# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

_BACKENDS: dict[str, Type[DataBackend]] = {}


def register_backend(name: str, cls: Type[DataBackend]) -> None:
    """注册后端类"""
    _BACKENDS[name] = cls


def get_backend(name: str) -> DataBackend:
    """
    按名称获取后端实例。

    Raises
    ------
    ValueError
        未知后端名称
    """
    name = name.lower()
    cls = _BACKENDS.get(name)
    if cls is None:
        raise ValueError(
            f"未知后端: {name}，可用: {list(_BACKENDS.keys())}"
        )
    return cls()


def list_backends() -> list[str]:
    """列出已注册的后端名称"""
    return list(_BACKENDS.keys())


# ---------------------------------------------------------------------------
# 注册内置后端
# ---------------------------------------------------------------------------

register_backend("yfinance", YFinanceBackend)
register_backend("alpha_vantage", AlphaVantageBackend)
register_backend("av", AlphaVantageBackend)
register_backend("mt5", MT5Backend)

__all__ = [
    "DataBackend",
    "get_backend",
    "list_backends",
    "register_backend",
]