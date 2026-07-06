"""
回测参数配置 — 所有回测参数集中管理
"""

# ---- 信号生成 ----
TOP_K = 2                     # 每个调仓日最多买入数
MIN_PRED = -999.0             # 最小预测收益（负值 = 不限制，永远选 top_k）
MIN_HOLD = 2                  # 最短持仓天数
MAX_HOLD = 30                 # 最长持仓天数
MAX_REBALANCES_PER_WEEK = 5   # 每周最大调仓次数（每天可调仓）

# ---- 成本（真实模拟） ----
ONE_WAY_FEE = 0.001           # 单边交易佣金（0.1%）
SLIPPAGE = 0.0005             # 滑点（0.05%，美国大盘股）
SPREAD_ESTIMATE = 0.0002      # 点差（0.02%，美国大盘股平均）
TOTAL_COST_PER_SIDE = ONE_WAY_FEE + SLIPPAGE + SPREAD_ESTIMATE  # 0.17%

# ---- 投资组合 ----
INITIAL_CASH = 100_000        # 初始资金
POSITION_SCALE = 20.0         # 杠杆倍数（v0.4.0 基线: p=20 ≈ 1:10 杠杆，回撤 <30%）

# ---- 市场状态过滤器（默认关闭，放开仓位限制） ----
USE_REGIME_FILTER = False     # 关闭 SPY > MA200 过滤器
REGIME_MA_WINDOW = 200        # 均线窗口