---
name: backtest-reviewer
description: Review backtest code and results for correctness, bias, and completeness. Use whenever a backtest is run, modified, or presented.
user-invocable: false
---

# Backtest review checklist

When reviewing a backtest:

1. **Look-ahead bias**
   - Are signal values computed using data available at the decision point?
   - Check that rolling joins, shift, and groupby operations don't leak future info
   - Verify that factor computation uses only data up to `t-1` for position at `t`

2. **Signal and execution alignment**
   - Does the signal timestamp match the execution timestamp?
   - Is there a gap between signal generation and trade execution?
   - Are fills assumed at open / close / VWAP consistently?

3. **Transaction costs**
   - Are commissions, spread, slippage, and market impact included?
   - Are cost assumptions realistic for the asset class and trade size?
   - Does leverage or margin affect the return calculation?

4. **Price adjustments**
   - Are dividends, splits, and corporate actions handled correctly?
   - Are adjusted prices used consistently?
   - Does the backtest correctly handle trading halts and limit up/down?

5. **Performance metrics**
   - Annualized return: is the compounding method correct?
   - Sharpe ratio: is the risk-free rate and annualization factor correct?
   - Maximum drawdown: is it measured from peak, not from inception?
   - Benchmark: is an appropriate benchmark included?

6. **Statistical significance**
   - Are results tested for overfitting?
   - Has the strategy been tested across different market regimes?
   - Is the backtest period long enough to draw meaningful conclusions?

7. **Suspicious patterns**
   - Perfect entry / exit at extremes
   - 100% win rate over many trades
   - Returns far above asset class norms
   - Nearly zero turnover with high returns
