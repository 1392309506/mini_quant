"""
OrderManager — 订单生命周期管理 + 审计日志

职责：
  - 接收风控确认后的信号，执行开/平仓
  - 生成订单审计日志（CSV），记录每笔交易
  - 支持批量平仓（停市/收盘清仓）

与 Broker 和 RiskManager 的关系：
  Broker(simulate=True)   ← 模拟成交，无需 MT5
  RiskManager.check()     ← 风控前置检查
  OrderManager.execute()  ← 实际下单 + 记录
"""

import logging
import csv
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import pandas as pd

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

# 审计日志路径
_AUDIT_LOG = DATA_DIR / "execution_audit.csv"


class OrderManager:
    """订单管理器。

    Parameters
    ----------
    broker : Broker
        已连接的 Broker 实例。
    audit_path : str, optional
        审计日志路径，默认 data/execution_audit.csv。
    """

    def __init__(self, broker, audit_path: str = None):
        self.broker = broker
        self._audit_path = Path(audit_path) if audit_path else _AUDIT_LOG
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 下单执行
    # ------------------------------------------------------------------

    def place_market(
        self,
        symbol: str,
        side: str,
        volume: float,
        reason: str = "signal",
    ) -> Dict:
        """
        市价单开仓。

        Parameters
        ----------
        symbol : str
            标的 ticker。
        side : str
            "buy" 或 "sell"。
        volume : float
            手数/股数。
        reason : str
            触发原因（"signal" / "stop_loss" / "manual"）。

        Returns
        -------
        dict : {"ticket", "symbol", "side", "volume", "price", "status"}
        """
        price = self.broker.get_symbol_price(symbol)
        timestamp = datetime.now()

        result = {
            "ticket": None,
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "price": price,
            "timestamp": timestamp,
            "reason": reason,
            "status": "pending",
        }

        try:
            if self.broker.simulate:
                fill = self.broker._sim_fill_order(symbol, side, volume, price)
                result["ticket"] = fill["ticket"]
            else:
                import MetaTrader5 as mt5
                order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": volume,
                    "type": order_type,
                    "price": price,
                    "deviation": 10,
                    "magic": 202607,
                    "comment": reason,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                send_result = mt5.order_send(request)
                if send_result.retcode != mt5.TRADE_RETCODE_DONE:
                    raise RuntimeError(
                        f"MT5 下单失败: retcode={send_result.retcode} "
                        f"{send_result.comment}"
                    )
                result["ticket"] = send_result.order
                logger.info(
                    f"  [MT5] 开仓: {symbol} {side} {volume}@{price:.4f} "
                    f"ticket={send_result.order}"
                )

            result["status"] = "filled"
            logger.info(
                f"📝 {'[SIM]' if self.broker.simulate else '[MT5]'} "
                f"开仓: {symbol} {side} {volume}@{price:.4f}"
            )
        except Exception as e:
            result["status"] = "rejected"
            result["error"] = str(e)
            logger.error(f"❌ 开仓失败 {symbol}: {e}")

        self._log(result)
        return result

    def close_position(self, ticket: int, reason: str = "signal") -> Dict:
        """
        平仓。

        Parameters
        ----------
        ticket : int
            持仓编号（Broker.get_positions() 中的 ticket）。
        reason : str
            平仓原因。

        Returns
        -------
        dict : {"ticket", "symbol", "pnl", "status"}
        """
        positions = self.broker.get_positions()
        target = positions[positions["ticket"] == ticket]
        if len(target) == 0:
            logger.warning(f"⚠️  持仓不存在: ticket={ticket}")
            return {"ticket": ticket, "status": "not_found"}

        pos = target.iloc[0]
        price = self.broker.get_symbol_price(pos["symbol"])
        timestamp = datetime.now()

        result = {
            "ticket": ticket,
            "symbol": pos["symbol"],
            "side": "close",
            "volume": pos["volume"],
            "price": price,
            "timestamp": timestamp,
            "reason": reason,
            "status": "pending",
        }

        try:
            if self.broker.simulate:
                fill = self.broker._sim_close_position(ticket, price)
                result["pnl"] = fill["pnl"]
            else:
                import MetaTrader5 as mt5
                close_side = (
                    mt5.ORDER_TYPE_SELL
                    if pos["type"] == "buy"
                    else mt5.ORDER_TYPE_BUY
                )
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": pos["symbol"],
                    "volume": float(pos["volume"]),
                    "type": close_side,
                    "position": ticket,
                    "price": price,
                    "deviation": 10,
                    "magic": 202607,
                    "comment": reason,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                send_result = mt5.order_send(request)
                if send_result.retcode != mt5.TRADE_RETCODE_DONE:
                    raise RuntimeError(
                        f"MT5 平仓失败: retcode={send_result.retcode} "
                        f"{send_result.comment}"
                    )
                # Calculate PnL from position data (send_result has no .result field for close deals)
                fill_price = send_result.price
                close_pnl = (fill_price - pos["price_open"]) * float(pos["volume"])
                if pos["type"] == "sell":
                    close_pnl = -close_pnl
                result["pnl"] = close_pnl

            result["status"] = "filled"
            logger.info(
                f"📝 {'[SIM]' if self.broker.simulate else '[MT5]'} "
                f"平仓: ticket={ticket} {pos['symbol']} "
                f"pnl={result.get('pnl', 0):+.2f}"
            )
        except Exception as e:
            result["status"] = "rejected"
            result["error"] = str(e)
            logger.error(f"❌ 平仓失败 ticket={ticket}: {e}")

        self._log(result)
        return result

    def close_all(self, reason: str = "end_of_day") -> List[Dict]:
        """
        批量平仓（收盘清仓 / 风控强平）。

        Parameters
        ----------
        reason : str
            平仓原因，默认 "end_of_day"。

        Returns
        -------
        list of dict
            每笔平仓结果。
        """
        positions = self.broker.get_positions()
        if len(positions) == 0:
            logger.info("  无持仓需要平仓")
            return []

        results = []
        for _, pos in positions.iterrows():
            result = self.close_position(int(pos["ticket"]), reason=reason)
            results.append(result)

        logger.info(f"📋 批量平仓完成: {len(results)} 笔")
        return results

    # ------------------------------------------------------------------
    # 审计日志
    # ------------------------------------------------------------------

    def _log(self, record: Dict):
        """写入一条审计日志。"""
        fieldnames = [
            "timestamp", "ticket", "symbol", "side", "volume",
            "price", "reason", "status", "pnl", "error",
        ]
        is_new = not self._audit_path.exists()
        with open(self._audit_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            if is_new:
                writer.writeheader()
            writer.writerow(record)

    def get_audit_log(self) -> pd.DataFrame:
        """读取审计日志。"""
        if not self._audit_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self._audit_path, parse_dates=["timestamp"])

    def clear_audit_log(self):
        """清空审计日志。"""
        if self._audit_path.exists():
            self._audit_path.unlink()
            logger.info(f"审计日志已清空: {self._audit_path}")