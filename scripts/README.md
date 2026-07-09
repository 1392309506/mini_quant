# scripts/ — 脚本工具包

> 可独立运行的脚本，用于模型训练、信号生成、回测验证等日常操作。

---

## 文件列表

| 脚本 | 作用 | 文档 |
|:---|:---|:---:|
| `daily_inference.py` | 每日信号生成 Pipeline | [下文](#daily_inferencepy) |
| `run_simulation.py` | 模拟盘自动交易循环 | [下文](#run_simulationpy) |
| `test_execution.py` | 执行层组件验证 | [下文](#test_executionpy) |
| `../train_model.py` | 模型训练入口 | [train_model.py](../train_model.py) |

---

## daily_inference.py

**每日信号生成 Pipeline** — 生产环境核心脚本。

### 功能

```
1. 从 models/ 加载指定版本的模型（V1 / V2）
2. 拉取最新行情（缓存 ≤7 天自动跳过）
3. 检查标的池数量与模型匹配
4. 计算 13 个因子 → 39 个特征（含横截面 rank + zscore）
5. LightGBM 推理 → 每只股票预测分
6. 生成调仓日历 → 入场信号（top_k） → 出场信号（max_hold）
7. 保存信号到 data/signals/
```

### 用法

```bash
# 默认：V2 模型（需要 118 只标的的数据）
python scripts/daily_inference.py

# 用 V1 模型（28 只标的，当前数据池）
python scripts/daily_inference.py --model V1

# 预览模式（不保存文件）
python scripts/daily_inference.py --model V1 --dry-run

# 指定日期
python scripts/daily_inference.py --model V1 --date 2026-07-06

# 强制刷新数据缓存
python scripts/daily_inference.py --model V1 --force-fetch
```

### 参数

| 参数 | 默认 | 说明 |
|:---|:---:|:---|
| `--model` | V2 | 模型版本 (V1=28只, V2=118只) |
| `--dry-run` | — | 预览模式，不保存文件 |
| `--date` | 今天 | 信号日期 (YYYY-MM-DD) |
| `--force-fetch` | — | 强制重新拉取数据（忽略缓存） |
| `--top-k` | 5 | 每期买入数 |
| `--no-regime` | — | 关闭 SPY 200日均线市场过滤器 |

### 输出

```
data/signals/
  {date}_entries.parquet     ← 入场信号（bool 矩阵，行=日期，列=ticker）
  {date}_exits.parquet       ← 出场信号（bool 矩阵）
  latest_entries.parquet     ← 最新入场信号（覆盖）
  latest_exits.parquet       ← 最新出场信号（覆盖）
  latest_predictions.parquet ← 所有标的预测值
  latest_summary.json        ← 信号摘要（JSON）
```

### 依赖模块

- `src.data.fetcher` — 行情数据拉取
- `src.factors.assembly` — 因子计算
- `src.models.registry` — 模型加载
- `src.models.signals` — 入场/出场信号生成

---

## run_simulation.py

**模拟盘启动脚本** — 每日自动交易循环。

### 功能

```
1. 调用 daily_inference 生成信号（或跳过，使用已有信号）
2. 加载/恢复模拟账户状态（从 data/simulation_state.json）
3. 处理出场信号 → 先平仓
4. 硬止损检查
5. 风控检查（杠杆/暴露/次数/单笔风险）→ 入场信号开仓
6. 用最新行情更新持仓市值
7. 输出每日摘要（持仓明细、盈亏、权益曲线）
8. 保存状态（下次运行恢复）
```

### 用法

```bash
# 默认：V1 模型（28 只），$10,000 初始资金
python scripts/run_simulation.py

# 切换 V2 模型（118 只，需先下载完整数据）
python scripts/run_simulation.py --model V2

# 指定初始资金
python scripts/run_simulation.py --initial-balance 50000

# 不重新生成信号（使用已有信号文件）
python scripts/run_simulation.py --no-inference

# 指定杠杆和每期买入数
python scripts/run_simulation.py --scale 7 --top-k 10
```

### 参数

| 参数 | 默认 | 说明 |
|:---|:---:|:---|
| `--model` | V1 | 模型版本 (V1=28只, V2=118只) |
| `--initial-balance` | 10000 | 初始资金 |
| `--no-inference` | — | 跳过 daily_inference，使用已有信号 |
| `--top-k` | 5 | 每期买入数 |
| `--scale` | 7.0 | 杠杆倍数（受风控规则实际约束） |

### 输出

```
data/execution_audit.csv       ← 每笔交易审计日志
data/simulation_state.json     ← 状态快照（恢复用）
终端每日摘要                   ← 持仓明细、盈亏、风控触发
```

### 依赖模块

- `scripts.daily_inference` — 信号生成
- `src.execution.broker` — 经纪商封装
- `src.execution.risk` — 风控检查
- `src.execution.order_manager` — 订单管理
- `src.data.fetcher` — 行情获取

---

## test_execution.py

**执行层组件验证** — 验证 Broker / RiskManager / OrderManager 在模拟模式下的基本功能。

### 测试内容

| 测试 | 验证内容 |
|:---|:---|
| Test 1 | Broker 模拟模式：账户信息初始化 |
| Test 2 | RiskManager.check_order：杠杆限制、风控拦截 |
| Test 3 | RiskManager.enforce_stop_loss：硬止损触发 |
| Test 4 | OrderManager.place_market + close_all：开平仓 |
| Test 5 | OrderManager 审计日志：CSV 写入与读取 |

### 用法

```bash
python scripts/test_execution.py
```

### 执行条件

- 无需连接 MT5（默认 `Broker(simulate=True)`）
- 无需网络（无数据拉取）
- 本地可独立运行

---

## train_model.py

位于项目根目录，详见 [train_model.py](../train_model.py) 文件头注释。

### 用法摘要

```bash
python train_model.py                               # 完整训练（全量标的）
python train_model.py --quick                       # 快速测试（5 只标的）
python train_model.py --version V3 --universe 28    # 新模型 V3，28 只
python train_model.py --load <exp_id>               # 加载已有实验结果
```

---

## 注意事项

1. **V1 vs V2**: V2 需要 118 只标的完整数据池。当前缓存了 28 只标的，模拟盘默认使用 `--model V1`。
2. **行情延迟**: 美股数据通常在北京时间凌晨更新。`--date` 默认今天，如果数据未就绪会发出警告，不影响正常使用。
3. **信号覆盖**: 入场信号覆盖未来 90 天（保证 max_hold=30 的出场信号落在窗口内），但只有最近一个交易日的信号用于执行。
4. **模拟盘无需账号**: Broker(simulate=True) 纯本地模拟，不需要 MT5 或 Exness 账户。
5. **状态持久化**: 模拟盘状态保存在 `data/simulation_state.json`，关机/重启后自动恢复。删除该文件即重置。