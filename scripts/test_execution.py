#!/usr/bin/env python3
"""Verify execution layer components."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src.execution import Broker, RiskManager, OrderManager
from src.execution.risk import RiskConfig

print("=" * 50)
print("TEST 1: Broker (simulate mode)")
print("=" * 50)
b = Broker(simulate=True)

# Clear old audit log
from src.config import DATA_DIR
audit = DATA_DIR / "execution_audit.csv"
if audit.exists():
    audit.unlink()

assert b.simulate == True, "Should be in simulate mode"
acc = b.get_account()
assert acc["balance"] == 10_000.0, f"Expected 10000, got {acc['balance']}"
print(f"  Account: balance={acc['balance']}, equity={acc['equity']} ✅")

print("\n" + "=" * 50)
print("TEST 2: RiskManager - check_order")
print("=" * 50)
cfg = RiskConfig()
r = RiskManager(cfg)
assert cfg.max_leverage == 7.0, "Safe leverage should be 7x"
order = {"symbol": "AAPL", "side": "buy", "volume": 10, "price": 150.0}
positions = pd.DataFrame()
passed, reason = r.check_order(order, acc, positions)
assert passed == True, f"Should pass: {reason}"
print(f"  check_order(10 shares @ $150): PASS ({reason}) ✅")

# Test leverage limit: 100 shares @ $150 = $15,000 notional vs $10,000 equity = 1.5x -> OK
order2 = {"symbol": "AAPL", "side": "buy", "volume": 500, "price": 150.0}
passed2, reason2 = r.check_order(order2, acc, positions)
assert passed2 == False, "500 shares @ $150 should fail leverage check"
print(f"  check_order(500 shares @ $150): REJECTED ({reason2}) ✅")

print("\n" + "=" * 50)
print("TEST 3: RiskManager - enforce_stop_loss")
print("=" * 50)
b._sim_fill_order("AAPL", "buy", 10, 150.0)
b.update_sim_prices({"AAPL": 130.0})  # -13% -> triggers 8% hard stop
positions = b.get_positions()
to_close = r.enforce_stop_loss(positions)
assert len(to_close) == 1, f"Expected 1 stop-loss, got {len(to_close)}"
print(f"  Hard stop-loss triggered: {len(to_close)} positions ✅")
print(f"  Reason: {to_close[0]['reason']}")

print("\n" + "=" * 50)
print("TEST 4: OrderManager - place_market & close")
print("=" * 50)
om = OrderManager(b)
result = om.place_market("MSFT", "buy", 5)
assert result["status"] == "filled", f"Order should be filled: {result}"
print(f"  place_market MSFT: {result['status']} ✅")

result2 = om.close_all()
assert len(result2) >= 1, "Should have closed positions"
print(f"  close_all: {len(result2)} positions closed ✅")

print("\n" + "=" * 50)
print("TEST 5: OrderManager - audit log")
print("=" * 50)
log = om.get_audit_log()
assert len(log) >= 1, "Audit log should have entries"
print(f"  Audit log entries: {len(log)} ✅")
print(f"  Columns: {list(log.columns)}")

print("\n" + "=" * 60)
print("ALL EXECUTION LAYER TESTS PASSED ✅")
print("=" * 60)