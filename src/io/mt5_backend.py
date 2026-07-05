"""
MT5Backend — 预留：Exness 实盘报价（MetaTrader5）

当工程化改造进入"执行层"阶段时实现此接口。
"""

import logging

import pandas as pd

from src.io.base import DataBackend

logger = logging.getLogger(__name__)


class MT5Backend(DataBackend):
    """MT5 实盘后端（未实现）"""

    name = "mt5"

    def fetch(self, symbols, start="", end=None):
        raise NotImplementedError(
            "MT5Backend 尚未实现——请在工程化改造执行层阶段接入。"
            "参考 CONSTITUTION.md 二.5 执行层约束。"
        )