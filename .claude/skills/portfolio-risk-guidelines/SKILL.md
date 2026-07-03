---
name: portfolio-risk-guidelines
description: Risk management and portfolio construction rules — position sizing, exposure limits, drawdown control, and leverage constraints. Use whenever designing, modifying, or reviewing portfolio weights and risk parameters.
user-invocable: false
---

# Portfolio risk management standards

## 1. Position sizing

- Single position max allocation: 20% of total capital (hard limit)
- Sector exposure cap: 40% of total capital
- Use Kelly fraction mode (Fractional Kelly, `f = f_kelly * 0.25`)
- Position size = `(risk_budget_per_trade) / (stop_loss_pct)`

## 2. Leverage constraints

- Maximum leverage ratio: 2x for long-only, 1.5x for long-short
- Margin-to-equity ratio must stay below 85%
- Leverage must be dynamic: reduce during high-volatility regimes
- Document margin call thresholds and liquidation logic

## 3. Volatility targeting

- Target annualized volatility: 15% (equity), 8% (balanced), 5% (conservative)
- Volatility scaling: position_size = `target_vol / realized_vol`
- EWMA volatility estimation with λ = 0.94
- Rebalance volatility target weekly

## 4. Drawdown control

- Hard stop: reduce total exposure by 50% when drawdown exceeds 15%
- Full stop: liquidate positions when drawdown exceeds 25%
- Cooling-off period: minimum 5 trading days before re-entry after full stop
- Trailing drawdown stop on individual positions: 25% from peak

## 5. VaR and CVaR

- Report daily VaR (95% and 99%) and CVaR (Expected Shortfall)
- VaR estimation method: historical simulation preferred, parametric as reference
- Backtest VaR: Kupiec POF test, Christoffersen independence test

## 6. Risk contribution

- Risk parity or equal risk contribution (ERC) preferred over equal weight
- Report marginal risk contribution per position
- Herfindahl-Hirschman Index (HHI) of risk concentration < 0.2

## 7. Stress testing

- Historical scenarios: 2008 GFC, 2020 COVID, 2022 rate hike
- Hypothetical scenarios: +30% VIX spike, -20% equity crash, FX sudden move
- Correlations: test with correlation matrices shifted +0.2
- Report worst-case portfolio loss under each scenario

## 8. Liquidity constraints

- Position size must not exceed 5% of daily volume
- For smaller cap stocks: reduce to 1% of daily volume
- Skip illiquid assets during market stress
- Slippage model: linear with position size relative to volume
