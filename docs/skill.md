有。这里的“量化”我按**量化金融、策略研究、回测和风险分析**理解。

先说明一下：**被动型 / 主动型不是 Claude Code 或 Codex 的官方分类**，但非常适合管理量化 Skills：

* **被动型 Skill**：提供规则、知识和检查标准，不主动运行脚本或访问数据。
* **主动型 Skill**：执行数据下载、回测、优化、绘图、生成报告等操作，通常带 `scripts/`、API 或命令行工具。

项目级目录应分别使用：

```text
你的项目/
├── .claude/
│   └── skills/
└── .agents/
    └── skills/
```

Claude Code 官方项目级目录是 `.claude/skills/`；Codex 当前官方项目级目录是 `.agents/skills/`，不是一些旧项目里写的 `.codex/skills/`。([Claude][1])

---

# 一、被动型量化 Skills

被动型最适合先安装，因为风险低，也不会擅自下载数据、运行长回测或修改文件。

## 1. quant-research-guidelines

作用：

* 防止未来函数和数据泄漏
* 明确训练集、验证集、测试集划分
* 要求使用 walk-forward validation
* 检查复权、退市偏差、幸存者偏差
* 强制报告交易成本和滑点
* 规定策略研究输出格式

它相当于整个量化项目的“研究宪法”。

推荐程度：**必装**

---

## 2. backtest-reviewer

作用：

* 审查已有回测代码
* 检查 look-ahead bias
* 检查信号和成交时间是否错位
* 检查手续费、滑点、停牌和涨跌停
* 检查年化收益率、夏普比率和最大回撤计算
* 检查 benchmark 是否合适

它不负责直接开发策略，主要负责“挑错”。

推荐程度：**必装**

---

## 3. statistical-validation

作用：

* 显著性检验
* Bootstrap
* 多重检验修正
* Deflated Sharpe Ratio
* 参数稳定性分析
* 样本外检验
* 蒙特卡洛置换检验
* 检查过拟合和数据挖掘偏差

推荐程度：**强烈推荐**

---

## 4. time-series-methodology

作用：

* 平稳性与单位根检验
* 协整关系
* ARIMA、VAR、GARCH
* 横截面与时间序列划分
* 时序交叉验证
* 缺失值和异常值处理
* 高频与低频数据对齐

推荐程度：**强烈推荐**

---

## 5. portfolio-risk-guidelines

作用：

* 仓位限制
* 单资产和行业暴露限制
* 波动率目标
* VaR、CVaR
* 最大回撤控制
* 风险贡献
* 杠杆和保证金约束
* 压力测试规范

推荐程度：**必装**

---

## 6. factor-research-standard

适合股票多因子项目：

* 因子构建规范
* 去极值、标准化、中性化
* IC、Rank IC、ICIR
* 分层回测
* 换手率
* 行业和市值暴露
* 因子衰减
* 因子相关性与冗余分析

推荐程度：做股票因子时必装。

---

## 7. quant-code-conventions

作用：

* 统一 pandas / NumPy 使用规范
* 统一数据字段命名
* 时间索引和时区规范
* 禁止原地修改原始行情
* 固定随机种子
* 要求配置与代码分离
* 要求测试核心收益指标
* 规范实验结果保存目录

推荐程度：**必装**

---

# 二、主动型量化 Skills

主动型会真正执行任务，建议默认设为**只能手动调用**。

Claude Code 可在 `SKILL.md` 中加入：

```yaml
disable-model-invocation: true
```

这样 Claude 不会因为看到策略代码就自行启动回测，必须由你输入 `/skill-name` 才能运行。Claude Code 官方也建议对部署、提交和其他有副作用的工作流这样设置。([Claude][1])

Codex 支持显式通过 `/skills` 或 `$skill-name` 调用，也可以根据描述自动选择。([OpenAI 开发者][2])

## 1. data-profiler

执行：

* 读取 CSV、Parquet、HDF5
* 检查字段类型
* 检查缺失值
* 检查时间覆盖
* 检查重复时间戳
* 检查资产覆盖
* 识别异常价格和成交量
* 输出数据质量报告

推荐程度：**必装**

调用示例：

```text
/data-profiler data/daily_prices.parquet
```

---

## 2. strategy-backtester

执行：

* 读取信号
* 构建仓位
* 模拟交易
* 添加手续费和滑点
* 计算收益曲线
* 输出夏普率、最大回撤、换手率
* 保存交易记录和图表

推荐程度：**必装**

建议不要安装一个“什么策略都做”的巨大 Skill，而是将它限制为你项目中的回测框架，例如：

```text
vectorbt
backtrader
qlib
自研事件驱动框架
```

---

## 3. walk-forward-runner

执行：

* 滚动训练
* 滚动验证
* 样本外预测
* 参数重估
* 汇总各窗口结果
* 比较不同市场阶段的稳定性

推荐程度：**必装**

---

## 4. factor-evaluator

执行：

* 计算 IC、Rank IC
* 分组收益
* 多空组合
* 因子衰减
* 换手率
* 行业、市值中性化
* 因子相关矩阵
* 生成因子报告

推荐程度：因子项目必装。

---

## 5. portfolio-optimizer

执行：

* 均值—方差优化
* 最小方差组合
* 风险平价
* 最大分散化
* Black–Litterman
* 加入仓位、行业、换手率约束
* 输出目标权重和风险贡献

推荐程度：组合项目必装。

---

## 6. stress-test-runner

执行：

* 历史压力情景
* 利率、波动率、汇率冲击
* 相关性上升
* 流动性下降
* 单资产暴跌
* 输出损失分布和风险暴露变化

推荐程度：强烈推荐。

---

## 7. experiment-reporter

执行：

* 收集回测结果
* 生成 Markdown 或 HTML 报告
* 绘制净值、回撤、滚动夏普
* 汇总参数
* 保存 Git commit、配置和数据版本
* 比较基线与新模型

推荐程度：**必装**

---

## 8. market-data-fetcher

执行：

* 从 yfinance、交易所或自定义 API 下载行情
* 缓存原始数据
* 增量更新
* 统一字段
* 写入 Parquet

推荐程度：可装，但需要特别谨慎：

* API 密钥放在 `.env`
* `.env` 加入 `.gitignore`
* Skill 不允许回显密钥
* 原始数据只写入指定目录
* 不允许自动覆盖历史快照

---

# 三、现成的量化 Skill 仓库

## 方案 A：finance-skills

`himself65/finance-skills` 偏向传统金融分析，包含：

* 股票分析
* 财报与预期
* 相关性
* 流动性
* ETF
* 期权收益结构
* 交易策略
* yfinance 数据工作流

它遵循 Agent Skills 开放标准，可供多个兼容 Agent 使用。([GitHub][3])

适合：

* 股票
* ETF
* 基础期权分析
* 市场研究
* 快速原型

不足：

* 更偏金融分析工具箱
* 严格的回测防泄漏规范仍应自己补充
* 不建议不经检查安装整个仓库

---

## 方案 B：claude-trading-skills

`agiprolabs/claude-trading-skills` 目前包含大量交易和量化 Skills，覆盖：

* 市场数据
* 技术指标
* 回测
* 风险管理
* 组合分析
* 可视化
* DeFi 和链上分析

但它明显偏 **Crypto / DeFi**，并非主要为 A 股或传统股票因子研究设计。仓库说明其支持 Claude Code、Codex 等 Agent Skills 兼容工具。([GitHub][4])

适合：

* 数字货币
* 链上数据
* DEX 流动性
* DeFi 收益分析

不建议：

* 一次性把全部 67 个 Skill 放进项目
* 在没有检查脚本和 API 权限前直接信任
* 将加密货币的数据假设直接套到股票和期货

---

## 方案 C：quant-analyst 子代理

`VoltAgent/awesome-claude-code-subagents` 中有一个 `quant-analyst`，涵盖：

* 量化策略
* 统计套利
* 衍生品定价
* 组合风险
* GARCH
* 协整
* 蒙特卡洛
* 因子模型

但它本质上更像一个**大而全的角色提示词**，不是精细拆分的可执行量化流水线。([GitHub][5])

适合：

* 作为量化顾问型子代理
* 方案设计
* 代码审查
* 研究讨论

不适合直接代替：

* 数据检查 Skill
* 回测 Skill
* 风险 Skill
* 实验报告 Skill

---

# 四、推荐的项目级安装方案

我建议不要把大量第三方 Skill 全部装进来，而是采用：

```text
7 个被动型 + 6 个主动型
```

目录结构：

```text
quant-project/
├── .claude/
│   └── skills/
│       ├── quant-research-guidelines/
│       ├── quant-code-conventions/
│       ├── backtest-reviewer/
│       ├── statistical-validation/
│       ├── time-series-methodology/
│       ├── portfolio-risk-guidelines/
│       ├── factor-research-standard/
│       ├── data-profiler/
│       ├── strategy-backtester/
│       ├── walk-forward-runner/
│       ├── factor-evaluator/
│       ├── portfolio-optimizer/
│       └── experiment-reporter/
│
├── .agents/
│   └── skills/
│       └── 上述同一批 Skill
│
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── configs/
├── src/
├── tests/
├── reports/
└── results/
```

---

# 五、项目级安装命令

在量化项目根目录运行：

```bash
mkdir -p .claude/skills
mkdir -p .agents/skills
```

克隆第三方仓库到临时目录：

```bash
git clone https://github.com/himself65/finance-skills.git /tmp/finance-skills
```

先查看其中有哪些 Skill：

```bash
find /tmp/finance-skills -name SKILL.md -print
```

不要直接复制全部。选择需要的 Skill 后，复制到 Claude Code：

```bash
cp -r /tmp/finance-skills/path/to/selected-skill \
  .claude/skills/
```

再复制同一份到 Codex：

```bash
cp -r .claude/skills/selected-skill \
  .agents/skills/
```

也可以避免维护两份副本，使用符号链接：

```bash
mkdir -p .agents/skills

for skill in .claude/skills/*; do
    name=$(basename "$skill")
    ln -s "../../.claude/skills/$name" ".agents/skills/$name"
done
```

最终类似：

```text
.agents/skills/strategy-backtester
    -> ../../.claude/skills/strategy-backtester
```

这样 Claude Code 和 Codex 使用同一套 Skill。

---

# 八、我最推荐的安装顺序

第一批先装被动型：

```text
quant-research-guidelines
quant-code-conventions
backtest-reviewer
statistical-validation
portfolio-risk-guidelines
```

第二批安装安全的主动型：

```text
data-profiler
factor-evaluator
experiment-reporter
```

第三批再安装可能长时间运行或改变结果文件的：

```text
strategy-backtester
walk-forward-runner
portfolio-optimizer
market-data-fetcher
```

其中：

* `market-data-fetcher`：需要网络和 API 权限。
* `strategy-backtester`：可能长时间占用 CPU。
* `portfolio-optimizer`：要防止不可行约束和数值不稳定。
* 实盘下单 Skill：**不建议和研究型 Skill 放在同一项目中**。

Agent Skills 可以携带可执行代码，因此第三方 Skill 应当像第三方软件包一样审查；尤其要检查 `SKILL.md`、`scripts/`、shell 命令、网络访问和密钥读取范围。Claude Code 对项目级 Skill 也会要求工作区信任，因为 Skill 可以申请较宽的工具权限。([Claude][1])

最稳妥的组合是：**自己维护核心被动规则，只从第三方仓库挑选少量主动工具，并把所有有副作用的 Skill 设为手动调用。**

[1]: https://code.claude.com/docs/en/skills "Extend Claude with skills - Claude Code Docs"
[2]: https://developers.openai.com/codex/skills "Agent Skills – Codex | OpenAI Developers"
[3]: https://github.com/himself65/finance-skills "GitHub - himself65/finance-skills: A collection of skills for AI financial analysis. · GitHub"
[4]: https://github.com/agiprolabs/claude-trading-skills "GitHub - agiprolabs/claude-trading-skills: 67 trading, DeFi, and quantitative finance Agent Skills. Works with Claude Code, Cursor, Codex, Gemini CLI, and 30+ other tools. · GitHub"
[5]: https://github.com/VoltAgent/awesome-claude-code-subagents/blob/main/categories/07-specialized-domains/quant-analyst.md "awesome-claude-code-subagents/categories/07-specialized-domains/quant-analyst.md at main · VoltAgent/awesome-claude-code-subagents · GitHub"
