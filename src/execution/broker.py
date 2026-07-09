"""
Broker — MT5 经纪商封装（含模拟模式）

遵循 CONSTITUTION.md §2.5 执行层约束：
  - 经纪商: Exness，首选 Raw Spread 账户
  - 交易终端: MetaTrader5（python 包 `MetaTrader5`）
  - 默认模拟模式，显式 simulate=False 才进入实盘

模拟模式下无需安装 MetaTrader5，所有方法返回符合接口的模拟数据，
便于在本地无 MT5 环境下开发、测试、对接信号生成 pipeline。
"""

import logging
import os
from typing import Optional, Dict, List
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class Broker:
    """MT5 经纪商封装。

    Parameters
    ----------
    simulate : bool
        True = 模拟模式（默认），不连接真实 MT5。
        False = 实盘模式，需配置 MT5_LOGIN / MT5_PASSWORD / MT5_SERVER。
    """

    def __init__(self, simulate: bool = True):
        self.simulate = simulate
        self._mt5 = None
        self._connected = False
        self._sim_account = {
            "balance": 10_000.0,
            "equity": 10_000.0,
            "margin": 0.0,
            "free_margin": 10_000.0,
            "currency": "USD",
        }
        self._sim_positions: List[Dict] = []
        self._sim_ticket = 100000

        if not simulate:
            self._connect_real()

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def _connect_real(self):
        """连接真实 MT5 终端。"""
        try:
            import MetaTrader5 as mt5  # noqa: F401
        except ImportError:
            raise ImportError(
                "实盘模式需要 MetaTrader5 包: pip install MetaTrader5\n"
                "模拟模式请使用 Broker(simulate=True)"
            )

        login = int(os.getenv("MT5_LOGIN", "0"))
        password = os.getenv("MT5_PASSWORD", "")
        server = os.getenv("MT5_SERVER", "")

        if not (login and password and server):
            raise ValueError(
                "实盘模式需要在 .env 中配置 MT5_LOGIN / MT5_PASSWORD / MT5_SERVER"
            )

        import MetaTrader5 as mt5
        if not mt5.initialize(login=login, password=password, server=server):
            raise RuntimeError(f"MT5 初始化失败: {mt5.last_error()}")

        self._mt5 = mt5
        self._connected = True
        logger.info(f"✅ MT5 实盘连接成功: login={login}, server={server}")

    def connect(self):
        """显式连接（模拟模式下为 no-op）。"""
        if self.simulate:
            self._connected = True
            logger.info("📋 Broker 模拟模式就绪（无真实连接）")
        elif not self._connected:
            self._connect_real()
        return self

    def disconnect(self):
        """断开连接。"""
        if not self.simulate and self._mt5 is not None:
            self._mt5.shutdown()
        self._connected = False
        logger.info("Broker 已断开")

    # ------------------------------------------------------------------
    # 账户与持仓查询
    # ------------------------------------------------------------------

    def get_account(self) -> Dict:
        """返回账户信息。"""
        if self.simulate:
            return dict(self._sim_account)

        info = self._mt5.account_info()
        if info is None:
            raise RuntimeError(f"获取账户信息失败: {self._mt5.last_error()}")
        return {
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "currency": info.currency,
        }

    def get_positions(self) -> pd.DataFrame:
        """返回当前持仓（标准化为 DataFrame）。"""
        if self.simulate:
            if not self._sim_positions:
                return pd.DataFrame(
                    columns=["ticket", "symbol", "volume", "type", "price_open",
                             "price_current", "profit", "time"]
                )
            return pd.DataFrame(self._sim_positions)

        positions = self._mt5.positions_get()
        if not positions:
            return pd.DataFrame(
                columns=["ticket", "symbol", "volume", "type", "price_open",
                         "price_current", "profit", "time"]
            )
        rows = []
        for p in positions:
            rows.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "volume": p.volume,
                "type": "buy" if p.type == 0 else "sell",
                "price_open": p.price_open,
                "price_current": p.price_current,
                "profit": p.profit,
                "time": datetime.fromtimestamp(p.time),
            })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # 模拟模式下的辅助方法（实盘模式由 OrderManager 通过 MT5 API 下单）
    # ------------------------------------------------------------------

    def _sim_fill_order(self, symbol: str, side: str, volume: float,
                        price: float) -> Dict:
        """模拟成交，记录到 _sim_positions。"""
        self._sim_ticket += 1
        position = {
            "ticket": self._sim_ticket,
            "symbol": symbol,
            "volume": volume,
            "type": side,
            "price_open": price,
            "price_current": price,
            "profit": 0.0,
            "time": datetime.now(),
        }
        self._sim_positions.append(position)
        logger.info(
            f"  [SIM] 开仓: {symbol} {side} {volume}@{price:.4f} ticket={self._sim_ticket}"
        )
        return {"ticket": self._sim_ticket, **position}

    def _sim_close_position(self, ticket: int, price: float) -> Dict:
        """模拟平仓，更新账户余额。"""
        for i, pos in enumerate(self._sim_positions):
            if pos["ticket"] == ticket:
                pos["price_current"] = price
                pnl = (price - pos["price_open"]) * pos["volume"]
                if pos["type"] == "sell":
                    pnl = -pnl
                self._sim_account["balance"] += pnl
                self._sim_positions.pop(i)
                # 重新计算 equity：balance + 剩余持仓浮动盈亏
                self._sim_account["equity"] = self._sim_account["balance"] + sum(
                    p["profit"] for p in self._sim_positions
                )
                logger.info(
                    f"  [SIM] 平仓: ticket={ticket} {pos['symbol']} pnl={pnl:+.2f}"
                )
                return {"ticket": ticket, "pnl": pnl, **pos}
        raise ValueError(f"模拟持仓不存在: ticket={ticket}")

    def update_sim_prices(self, prices: Dict[str, float]):
        """模拟模式下，用最新价更新持仓的 price_current 和 profit。"""
        if not self.simulate:
            return
        for pos in self._sim_positions:
            if pos["symbol"] in prices:
                pos["price_current"] = prices[pos["symbol"]]
                pnl = (pos["price_current"] - pos["price_open"]) * pos["volume"]
                if pos["type"] == "sell":
                    pnl = -pnl
                pos["profit"] = pnl
        # 更新权益
        total_pnl = sum(p["profit"] for p in self._sim_positions)
        self._sim_account["equity"] = self._sim_account["balance"] + total_pnl
        self._sim_account["margin"] = sum(
            p["volume"] * p["price_open"] * 0.01 for p in self._sim_positions
        )
        self._sim_account["free_margin"] = (
            self._sim_account["equity"] - self._sim_account["margin"]
        )

    def get_symbol_price(self, symbol: str) -> float:
        """获取某标的最新报价。"""
        if self.simulate:
            # 模拟模式应由调用方通过 update_sim_prices 注入价格
            for pos in self._sim_positions:
                if pos["symbol"] == symbol:
                    return pos["price_current"]
            return 100.0  # 占位默认值

        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"获取 {symbol} 报价失败")
        return tick.ask
