"""
RiskManager — 风控检查与硬止损执行

遵循 CONSTITUTION.md §5.2 实盘风控约束：
  - 单笔最大风险：不超过总资金的 2%
  - 单市场最大暴露：不超过总资金的 30%
  - 必须有硬性的止损机制（代码自动执行，不依赖人工）
  - 每日最大交易次数：Swing 频率下不超过 4 次/天
  - 安全杠杆上限 ≤ 7x（v0.5.0 验证结论）

风控检查流程：
  1. check_order(order) → bool         下单前检查是否通过风控
  2. enforce_stop_loss(positions) → list 遍历持仓，返回需强平的 ticket
  3. record_trade(pnl) → None          记录当日交易次数（日内限制）
  4. get_daily_stats() → dict          获取当日交易统计
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, date

import pandas as pd

logger = logging.getLogger(__name__)


class RiskConfig:
    """风控参数（默认值遵循 CONSTITUTION.md §5.2）。"""

    def __init__(
        self,
        max_loss_per_trade_pct: float = 0.02,   # 单笔最大亏损 2%
        max_daily_loss_pct: float = 0.05,        # 单日最大亏损 5%
        max_leverage: float = 7.0,               # 安全杠杆上限 7x（v0.5.0 验证）
        max_position_pct: float = 0.30,          # 单标的最大暴露 30%
        max_daily_trades: int = 4,               # 每日最大交易次数 4
        hard_stop_loss_pct: float = 0.08,        # 单笔硬止损 8%（2x 单笔风险上限）
    ):
        self.max_loss_per_trade_pct = max_loss_per_trade_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_leverage = max_leverage
        self.max_position_pct = max_position_pct
        self.max_daily_trades = max_daily_trades
        self.hard_stop_loss_pct = hard_stop_loss_pct


class RiskManager:
    """风控管理器。

    Parameters
    ----------
    config : RiskConfig, optional
        风控参数，默认使用 CONSTITUTION.md 约束。
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()
        self._daily_trades: Dict[date, int] = {}
        self._daily_pnl: Dict[date, float] = {}

    # ------------------------------------------------------------------
    # 下单前检查
    # ------------------------------------------------------------------

    def check_order(
        self,
        order: Dict,
        account: Dict,
        open_positions: pd.DataFrame,
    ) -> tuple:
        """
        下单前风控检查。

        Parameters
        ----------
        order : dict
            {"symbol", "side", "volume", "price", "stop_loss"(可选)}
        account : dict
            {"balance", "equity", "margin", "free_margin"}
        open_positions : pd.DataFrame
            当前持仓（来自 Broker.get_positions()）

        Returns
        -------
        (bool, str)
            (是否通过, 原因)
        """
        symbol = order["symbol"]
        volume = float(order["volume"])
        price = float(order["price"])
        notional = volume * price
        equity = account.get("equity", account.get("balance", 0))

        # 0. 计算已有持仓总名义本金（用于全组合杠杆检查）
        existing_notional = 0.0
        if len(open_positions) > 0:
            existing_notional = (
                open_positions["volume"] * open_positions["price_open"]
            ).sum()

        # 1. 全组合杠杆检查（已有 + 新单）
        if equity > 0:
            total_notional = existing_notional + notional
            total_leverage = total_notional / equity
            if total_leverage > self.config.max_leverage:
                return False, (
                    f"全组合杠杆 {total_leverage:.1f}x（已有 {existing_notional/equity:.1f}x "
                    f"+ 新单 {notional/equity:.1f}x）超过上限 {self.config.max_leverage}x"
                )

        # 2. 单标的暴露检查
        existing_exposure = 0.0
        if len(open_positions) > 0:
            same_symbol = open_positions[open_positions["symbol"] == symbol]
            if len(same_symbol) > 0:
                existing_exposure = (
                    same_symbol["volume"] * same_symbol["price_open"]
                ).sum()
        total_exposure = existing_exposure + notional
        if equity > 0 and total_exposure / equity > self.config.max_position_pct:
            return False, (
                f"{symbol} 暴露 {total_exposure/equity:.1%} 超过上限 "
                f"{self.config.max_position_pct:.0%}"
            )

        # 3. 当日交易次数检查
        today = date.today()
        if self._daily_trades.get(today, 0) >= self.config.max_daily_trades:
            return False, (
                f"当日交易次数 {self._daily_trades[today]} 已达上限 "
                f"{self.config.max_daily_trades}"
            )

        # 4. 当日亏损检查
        daily_pnl = self._daily_pnl.get(today, 0)
        if daily_pnl < 0 and equity > 0:
            daily_loss_pct = -daily_pnl / equity
            if daily_loss_pct >= self.config.max_daily_loss_pct:
                return False, (
                    f"当日亏损 {daily_loss_pct:.1%} 达上限 "
                    f"{self.config.max_daily_loss_pct:.0%}，停止交易"
                )

        # 5. 单笔风险检查（基于 stop_loss 或默认硬止损）
        sl_pct = order.get("stop_loss", self.config.hard_stop_loss_pct)
        max_loss = notional * sl_pct
        if equity > 0 and max_loss / equity > self.config.max_loss_per_trade_pct + 1e-10:
            return False, (
                f"单笔潜在亏损 {max_loss/equity:.2%} 超过上限 "
                f"{self.config.max_loss_per_trade_pct:.0%}"
            )

        return True, "OK"

    # ------------------------------------------------------------------
    # 硬止损执行
    # ------------------------------------------------------------------

    def enforce_stop_loss(self, positions: pd.DataFrame) -> List[Dict]:
        """
        遍历持仓，返回触发硬止损需平仓的列表。

        Returns
        -------
        list of dict
            [{"ticket", "symbol", "reason", "current_price", "open_price"}]
        """
        to_close = []
        if len(positions) == 0:
            return to_close

        for _, pos in positions.iterrows():
            open_p = float(pos["price_open"])
            cur_p = float(pos["price_current"])
            if open_p <= 0 or cur_p <= 0:
                continue

            # 计算浮动亏损百分比
            if pos["type"] == "buy":
                pnl_pct = (cur_p - open_p) / open_p
            else:
                pnl_pct = (open_p - cur_p) / open_p

            if pnl_pct <= -self.config.hard_stop_loss_pct:
                to_close.append({
                    "ticket": int(pos["ticket"]),
                    "symbol": pos["symbol"],
                    "reason": f"硬止损触发: {pnl_pct:.2%} ≤ "
                              f"-{self.config.hard_stop_loss_pct:.0%}",
                    "current_price": cur_p,
                    "open_price": open_p,
                    "pnl_pct": pnl_pct,
                })
                logger.warning(
                    f"🛑 硬止损触发: ticket={pos['ticket']} {pos['symbol']} "
                    f"{pnl_pct:.2%}"
                )

        return to_close

    # ------------------------------------------------------------------
    # 每日限制记录
    # ------------------------------------------------------------------

    def record_trade(self, pnl: float = 0.0):
        """记录一笔交易（用于每日次数和盈亏统计）。"""
        today = date.today()
        self._daily_trades[today] = self._daily_trades.get(today, 0) + 1
        self._daily_pnl[today] = self._daily_pnl.get(today, 0) + pnl

    def get_daily_stats(self) -> Dict:
        """返回当日交易统计。"""
        today = date.today()
        return {
            "date": str(today),
            "n_trades": self._daily_trades.get(today, 0),
            "pnl": self._daily_pnl.get(today, 0),
            "max_trades": self.config.max_daily_trades,
            "max_daily_loss_pct": self.config.max_daily_loss_pct,
        }

