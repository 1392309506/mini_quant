# Quant Trading System

一个面向个人研究者的自动化量化交易系统：**数据采集 → 因子计算 → 模型训练 → 回测验证 → 实盘执行**。

✅ **v0.4.0**: 数据采集、因子计算、模型训练、回测验证全链路已打通，回测验证通过。下一阶段：实盘执行与风控。

---

## 特性

- **多后端数据采集**：yfinance（默认，数据全）+ Alpha Vantage（兜底，无需代理），统一缓存为 parquet。
- **13 个技术因子**：动量（MOMO_20/60、MOM_RATIO）、均值回归（RSI_14、BB_POS、VOL_MA_RATIO）、波动率（ATR_20_NORM、VOLATILITY_20）、统计拓展（BB_WIDTH、HIGH_LOW_RATIO、ULCER_INDEX、MAX_DD_60）、资金流（CHAIKIN_MF），均为纯函数，可独立测试。
- **因子探索**：持续因子寻找流程（factor_hunt.py），以 IC/ICIR/层组合单调性为筛选标准，当前已测试 28 个候选因子，发现 5 个有效因子。
- **增量更新**：parquet 缓存，7 天内不重复下载。
- **代理友好**：自动为 yfinance 注入 HTTP 代理（v2rayN/Clash）。

---

## 快速开始

```bash
# 1. 克隆 & 进入
git clone <your-repo-url> Quant
cd Quant

# 2. 创建 conda 环境
conda create -n quant python=3.12 -y
conda activate quant

# 3. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入代理端口和 API Key

# 5. 下载数据（先小样本测试）
python data_fetcher.py --max 3

# 6. 计算因子
python factor_engine.py
```

详细使用说明（预期输出、参数说明、FAQ、Jupyter 用法）见 [docs/使用指南.md](docs/使用指南.md)。

### 因子探索

```bash
# 列出所有可用新因子
python factor_hunt.py --list

# 测试单个因子（默认 forward_return_10）
python factor_hunt.py BB_WIDTH

# 测试因子在不同周期上
python factor_hunt.py BB_WIDTH --period 21

# 测试多个因子
python factor_hunt.py BB_WIDTH HIGH_LOW_RATIO --period 21

# 批量测试所有新因子
python factor_hunt.py --all
```

因子探索结果记录在 [notes/因子寻找.md](notes/因子寻找.md)。

---

## 项目结构

```
Quant/
├── src/                      # 核心库
│   ├── __init__.py          # 版本号 + 顶层导出
│   ├── config.py            # 配置中心（路径、代理、后端选择）
│   ├── universe.py/.txt     # 交易标的池
│   ├── experiment.py        # 实验保存/加载
│   ├── data/                # 数据流水线
│   │   ├── fetcher.py       #   数据下载 + 缓存 + 完整性检查
│   │   ├── label.py         #   远期收益标签计算
│   │   └── preprocess.py    #   训练数据准备 + Walk-Forward 窗口
│   ├── factors/             # 因子计算（13 个纯函数因子）
│   │   ├── momentum.py      #   MOMO_20, MOMO_60, MOM_RATIO
│   │   ├── mean_reversion.py #  RSI_14, BB_POS, VOL_MA_RATIO
│   │   ├── volatility.py    #   ATR_20, VOLATILITY_20
│   │   ├── new_factors.py   #   BB_WIDTH, HIGH_LOW_RATIO, ULCER_INDEX, MAX_DD_60, CHAIKIN_MF
│   │   ├── regime.py        #   market_regime_filter
│   │   ├── assembly.py      #   因子组装器
│   │   └── validation.py    #   因子质量检查
│   ├── models/              # 模型训练与信号
│   │   ├── config.py        #   训练超参数
│   │   ├── trainer.py       #   LightGBM Walk-Forward 训练
│   │   └── signals.py       #   交易信号生成
│   ├── backtest/            # 回测
│   │   ├── config.py        #   回测参数
│   │   ├── engine.py        #   vectorbt 包装器
│   │   └── reporting.py     #   报告 + 图表
│   └── io/                  # 数据后端（DataBackend 协议）
│       ├── base.py          #   DataBackend 抽象协议
│       ├── cache.py         #   parquet 缓存管理
│       ├── yfinance_backend.py # yfinance 实现（默认）
│       ├── alpha_vantage.py    # Alpha Vantage 兜底
│       └── mt5_backend.py      # MT5 实盘报价（预留）
├── data/                    # 数据缓存（.gitignore 忽略）
├── experiments/             # 实验输出（模型、预测、回测报告）
├── docs/                    # 文档
├── notes/                   # 调研笔记与学习文档
├── data_fetcher.py          # 数据获取入口
├── factor_engine.py         # 因子计算入口
├── factor_hunt.py           # 因子寻找与评估
├── train_model.py           # 模型训练入口
├── run_backtest.py          # 回测入口
├── pyproject.toml           # 包元数据（pip install -e .）
├── requirements.txt
├── .env.example             # 配置模板
└── .gitignore
```

---

## 数据流

```
                            ┌──────────────────────────────────┐
                            │         数据获取 (Stage 1)       │
                            │  data_fetcher.py                 │
                            │  └─ src.data.fetcher           │
                            │       ├─ io/ backend (yfinance)  │
                            │       └─ data/market_data.parquet│
                            └──────────┬───────────────────────┘
                                       │ OHLCV MultiIndex
                                       ▼
                            ┌──────────────────────────────────┐
                            │         因子计算 (Stage 2)       │
                            │  factor_engine.py                │
                            │  └─ src.factors.assembly       │
                            │       ├─ momentum.py             │
                            │       ├─ mean_reversion.py       │
                            │       └─ volatility.py           │
                            └──────────┬───────────────────────┘
                                       │ factor_panel (ticker×8因子)
                                       ▼
                            ┌──────────────────────────────────┐
                            │   标签 & 预处理 (Stage 3)       │
                            │  ├─ src.data.label             │
                            │  │    (forward_return_{5,10,21}) │
                            │  └─ src.data.preprocess        │
                            │       (堆叠 + 缩尾 + WF windows) │
                            └──────────┬───────────────────────┘
                                       │ training_data (Date,ticker)
                                       ▼
                            ┌──────────────────────────────────┐
                            │       模型训练 (Stage 4)         │
                            │  train_model.py                  │
                            │  └─ src.models.trainer         │
                            │       (LightGBM Walk-Forward)    │
                            └──────────┬───────────────────────┘
                                       │ 预测 + 模型文件
                                       ▼
                            ┌──────────────────────────────────┐
                            │  信号生成 & 回测 (Stage 5)      │
                            │  run_backtest.py                 │
                            │  ├─ src.models.signals         │
                            │  │    (调仓日历 + 入场/出场)     │
                            │  ├─ src.backtest.engine        │
                            │  │    (vectorbt Portfolio)       │
                            │  └─ src.backtest.reporting     │
                            │       (equity curve + 指标)      │
                            └──────────────────────────────────┘
```

---

## 配置

所有配置集中在 `.env`（模板见 [.env.example](.env.example)）：

| 变量 | 说明 | 默认 |
|---|---|---|
| `DATA_BACKEND` | `yfinance` 或 `alpha_vantage` | `yfinance` |
| `HTTP_PROXY` / `HTTPS_PROXY` | 代理地址（v2rayN 默认 `http://127.0.0.1:10808`） | 无 |
| `ALPHA_VANTAGE_KEY` | AV 兜底用 Key | 无 |

> ⚠️ `.env` 含密钥，已被 `.gitignore` 忽略，**切勿提交**。

---

## 路线图

- [x] 数据采集 + 因子计算
- [x] 工程化重构（配置中心、Backend 协议、IO 层拆分）
- [x] 模型训练（LightGBM + Walk-Forward, 39 特征含横截面, 13 个基础因子）— v0.3.0 ✅
- [x] 回测验证（vectorbt, 年化 64%~81%, 夏普 4.9~5.8）— v0.4.0 ✅
- [x] 扩大标的池（118 只股票全链路训练+回测）— v0.4.0
- [x] 因子探索（已测试 28 候选因子，13 个因子已集成至代码）— v0.4.0
- [x] 实盘就绪评估（结论：研究原型，不可实盘）
- [ ] **回测有效性验证**（Rolling OOS 交叉验证 / Permutation Test / 随机基线）
- [ ] 模型存储至独立 models/ 目录 + 每日推理 pipeline
- [ ] 执行层搭建（MetaTrader5 对接 Exness）
- [ ] 风控与仓位管理（止损/杠杆限制/每日交易次数上限）
- [ ] 模拟盘运行（Exness Demo, 1-3 个月）
- [ ] 实盘（极小资金起步）

---

## License

MIT
