---
name: quant-research-guidelines
description: Apply rigorous quantitative research standards when designing, reviewing, or modifying trading strategies, factor models, forecasts, backtests, or portfolio experiments. Use whenever the task involves financial time-series modeling or strategy evaluation.
user-invocable: false
---

# Quantitative research standards

When reviewing or implementing quantitative research:

1. **Identify the signal timestamp, decision timestamp, order timestamp, execution timestamp, and return measurement interval.**

2. **Reject any workflow that uses information unavailable at the decision timestamp.**
   - No future data leakage
   - No look-ahead bias in factor computation
   - No using close prices for intraday decisions

3. **Separate training, validation, and test periods chronologically.**
   - Time-series must never use random train-test splitting
   - Preserve temporal order in all cross-validation

4. **Prefer walk-forward or expanding-window validation over random train-test splitting.**
   - Anchored vs. rolling windows should be stated explicitly

5. **Include commissions, spread, slippage, market impact, and turnover when applicable.**
   - Provide explicit cost assumptions, not just "after costs"
   - Report net-of-costs alongside gross returns

6. **Check for survivorship bias, delisting bias, adjusted-price errors, universe leakage, and revised fundamental data.**
   - State what universe was available at each point in time
   - Account for stocks that were delisted or suspended

7. **Report at minimum:**
   - Annualized return
   - Annualized volatility
   - Sharpe / Sortino ratio
   - Maximum drawdown
   - Calmar ratio
   - Turnover
   - Number of observations or trades
   - Benchmark-relative performance

8. **Distinguish in-sample, validation, and final out-of-sample results.**
   - Never present an in-sample result as final OOS performance

9. **Do not claim robustness from a single parameter setting, asset, period, or random seed.**
   - Multiple tests require multiple-test correction (Bonferroni, FDR)

10. **State all assumptions and unresolved data limitations explicitly.**
