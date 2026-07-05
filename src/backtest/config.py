"""
回测参数配置 — 所有回测参数集中管理
"""

# ---- 信号生成 ----
TOP_K = 5                     # 每个调仓日最多买入数
MIN_PRED = 0.0                # 最小预测收益（0 = 仅正预测）
MIN_HOLD = 5                  # 最短持仓天数
MAX_HOLD = 30                 # 最长持仓天数（强制平仓）
MAX_REBALANCES_PER_WEEK = 2   # 每周最大调仓次数

# ---- 成本 ----
ONE_WAY_FEE = 0.001           # 单边交易成本（含滑点）

# ---- 投资组合 ----
INITIAL_CASH = 100_000        # 初始资金

# ---- 市场状态过滤器 ----
USE_REGIME_FILTER = True      # 是否使用 SPY > MA200 过滤器
REGIME_MA_WINDOW = 200        # 均线窗口