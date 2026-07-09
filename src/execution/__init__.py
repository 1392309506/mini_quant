"""
Execution Layer — 实盘执行与风控

遵循 CONSTITUTION.md §5.2 实盘风控约束：
  - 默认模拟盘，显式切换才进入实盘
  - 单笔最大风险：不超过总资金的 2%
  - 单市场最大暴露：不超过总资金的 30%
  - 必须有硬性的止损机制（代码自动执行）
  - 每日最大交易次数：Swing 频率下不超过 4 次/天

模块组成：
  - Broker        : MT5 经纪商封装（含模拟模式）
  - RiskManager   : 风控检查与止损执行
  - OrderManager  : 订单生命周期管理 + 审计日志
"""

from src.execution.broker import Broker
from src.execution.risk import RiskManager
from src.execution.order_manager import OrderManager

__all__ = ["Broker", "RiskManager", "OrderManager"]
