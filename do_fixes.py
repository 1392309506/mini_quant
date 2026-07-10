import re

# P4: Remove check_daily_limits from risk.py
with open('src/execution/risk.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and remove the check_daily_limits method
old = '''    def check_daily_limits(self, account: Dict) -> tuple:
        """检查当日是否触发整体停止交易条件。"""
        today = date.today()
        equity = account.get("equity", account.get("balance", 0))

        # 交易次数
        if self._daily_trades.get(today, 0) >= self.config.max_daily_trades:
            return True, f"当日交易次数达上限 {self.config.max_daily_trades}"

        # 当日亏损
        daily_pnl = self._daily_pnl.get(today, 0)
        if equity > 0 and daily_pnl < 0:
            loss_pct = -daily_pnl / equity
            if loss_pct >= self.config.max_daily_loss_pct:
                return True, (
                    f"当日亏损 {loss_pct:.1%} 达上限 "
                    f"{self.config.max_daily_loss_pct:.0%}"
                )

        return False, "OK"

'''

if old in content:
    content = content.replace(old, '')
    with open('src/execution/risk.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("P4: removed check_daily_limits")
else:
    print("P4: NOT FOUND in file")

# P5: Add log to active_returns filter in backtest/engine.py
with open('src/backtest/engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

old2 = '''    active_returns = all_returns[all_returns.abs() > 1e-10]
    if len(active_returns) < 20:
        active_returns = all_returns  # fallback'''

new2 = '''    dropped = len(all_returns) - (all_returns.abs() > 1e-10).sum()
    if dropped > 0:
        logger.debug(f"active_returns: 过滤 {dropped}/{len(all_returns)} 个平坦期")
    active_returns = all_returns[all_returns.abs() > 1e-10]
    if len(active_returns) < 20:
        logger.warning(f"active_returns 仅 {len(active_returns)} 个有效值，使用全部 {len(all_returns)} 个")
        active_returns = all_returns  # fallback'''

if old2 in content:
    content = content.replace(old2, new2)
    with open('src/backtest/engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("P5: added active_returns logging")
else:
    print("P5: old pattern NOT FOUND")

# P2: Derive N_BASE_FEATURES from FACTOR_NAMES
with open('train_model.py', 'r', encoding='utf-8') as f:
    content = f.read()

old3 = '''    N_BASE_FEATURES = 13
    data = add_cross_sectional_features(data, FEATURE_COLS[:N_BASE_FEATURES])
    data = clip_outliers(data, FEATURE_COLS[:N_BASE_FEATURES], CLIP_STD_THRESHOLD)'''
new3 = '''    from src.factors.assembly import FACTOR_NAMES
    N_BASE_FEATURES = len(FACTOR_NAMES)
    data = add_cross_sectional_features(data, FEATURE_COLS[:N_BASE_FEATURES])
    data = clip_outliers(data, FEATURE_COLS[:N_BASE_FEATURES], CLIP_STD_THRESHOLD)'''

if old3 in content:
    content = content.replace(old3, new3)
    with open('train_model.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("P2: train_model.py N_BASE_FEATURES derived from FACTOR_NAMES")
else:
    print("P2: train_model.py old pattern NOT FOUND")

with open('scripts/daily_inference.py', 'r', encoding='utf-8') as f:
    content = f.read()

old4 = '''    N_BASE_FEATURES = 13
    data = add_cross_sectional_features(data, FEATURE_COLS[:N_BASE_FEATURES])
    data = clip_outliers(data, FEATURE_COLS[:N_BASE_FEATURES], CLIP_STD_THRESHOLD)'''
new4 = '''    from src.factors.assembly import FACTOR_NAMES
    N_BASE_FEATURES = len(FACTOR_NAMES)
    data = add_cross_sectional_features(data, FEATURE_COLS[:N_BASE_FEATURES])
    data = clip_outliers(data, FEATURE_COLS[:N_BASE_FEATURES], CLIP_STD_THRESHOLD)'''

if old4 in content:
    content = content.replace(old4, new4)
    with open('scripts/daily_inference.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("P2: daily_inference.py N_BASE_FEATURES derived from FACTOR_NAMES")
else:
    print("P2: daily_inference.py old pattern NOT FOUND")

print("All done")