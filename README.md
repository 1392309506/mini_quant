# Quant Trading System

一个面向个人研究者的自动化量化交易系统：**数据采集 → 因子计算 → 模型训练 → 回测验证 → 实盘执行**。

当前阶段已打通「数据采集 + 因子计算」，模型训练与回测为路线图。

---

## 特性

- **多后端数据采集**：yfinance（默认，数据全）+ Alpha Vantage（兜底，无需代理），统一缓存为 parquet。
- **8 个技术因子**：动量（MOMO_20/60、MOM_RATIO）、均值回归（RSI_14、BB_POS、VOL_MA_RATIO）、波动率（ATR_20_NORM、VOLATILITY_20），均为纯函数，可独立测试。
- **数据完整性 & 因子质量检查**：自动检测缺失值、异常波动、数据量不足、因子值域越界。
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

---

## 项目结构

```
Quant/
├── quant/                   # 核心库（包）
│   ├── config.py            # 集中配置（缓存、代理、批大小等稳定参数）
│   ├── universe.py          # 交易标的池加载器（读取 universe.txt）
│   ├── universe.txt          # 交易标的池（一行一个 ticker，# 注释分割板块）
│   ├── io/                  # 数据后端层（DataBackend 协议）
│   │   ├── base.py          #   DataBackend 抽象协议
│   │   ├── cache.py         #   parquet 缓存管理
│   │   ├── yfinance_backend.py  # yfinance 实现（默认）
│   │   ├── alpha_vantage.py     # Alpha Vantage 兜底
│   │   └── mt5_backend.py       # MT5 实盘报价（预留）
│   ├── fetcher.py           # 数据获取编排层（注册表分发）
│   ├── engine.py            # 因子计算引擎
│   └── factor.py            # 因子模块公开接口
├── data/                    # 数据缓存（.gitignore 忽略）
├── docs/                    # 文档
├── data_fetcher.py          # 数据获取入口
├── factor_engine.py         # 因子计算入口
├── requirements.txt
├── .env.example             # 配置模板
└── .gitignore
```

---

## 数据流

```
.env (代理/Key)  ──►  config.py  ──►  io/  ──►  data/market_data.parquet  ──►  engine  ──►  factor panel
                       (配置中心)        (DataBackend 注册表)   (MultiIndex: ticker×OHLCV)        (ticker×factor)
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
- [ ] 工程化重构（配置中心、Backend 协议、统一 CLI、pytest）— 见 [docs/工程化改造.md](docs/工程化改造.md)
- [ ] 因子探索（Jupyter 可视化）
- [ ] 模型训练（LightGBM + Walk-Forward）
- [ ] 回测验证（vectorbt）
- [ ] 实盘执行（MetaTrader5 对接 Exness）

---

## License

MIT
