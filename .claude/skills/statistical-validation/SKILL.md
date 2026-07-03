---
name: statistical-validation
description: Apply statistical tests and validation techniques to strategy results, factor IC, and performance metrics. Use when evaluating strategy significance, overfitting risk, or factor predictive power.
user-invocable: false
---

# Statistical validation standards

## 1. Significance testing

- Report t-statistics and p-values for key performance metrics
- Test Sharpe ratio significance using the Mertens / Lo (2002) correction for autocorrelation
- Use bootstrap hypothesis testing for non-normal return distributions

## 2. Bootstrap methods

- Block bootstrap (preserve serial dependence)
- Stationary bootstrap (random block lengths)
- Report confidence intervals for Sharpe ratio, drawdown, and CAGR
- Minimum 10,000 bootstrap replications

## 3. Multiple testing correction

- Bonferroni correction: `p_adj = p * N`
- Holm-Bonferroni: sequential step-down procedure
- Benjamini-Hochberg FDR: control expected proportion of false discoveries
- Report both raw and adjusted p-values
- Apply correction across all tested strategies, parameters, and factor variants

## 4. Deflated Sharpe Ratio

- Replace the standard Sharpe test with the Deflated Sharpe Ratio (DSR) of Bailey et al. (2014)
- DSR accounts for: number of trials, return non-normality, and dependencies
- `DSR > 2` is a reasonable minimum threshold for significance

## 5. Parameter stability

- Sensitivity analysis on key parameters (show contour plots or heat maps)
- Parameter stability across sub-periods
- Avoid over-optimization — prefer simple, robust parameter choices

## 6. Out-of-sample testing

- Never report in-sample as final performance
- Apply walk-forward analysis with fixed or expanding windows
- Report OOS performance degradation (IC decay, Sharpe decay)

## 7. Monte Carlo permutation tests

- Permute returns or signal labels (preserve temporal order when shuffling)
- Test whether the observed Sharpe could arise from random ordering
- Minimum 5,000 permutations

## 8. Data mining bias check

- Document the full search space: number of factors tried, parameters tested, strategy variants explored
- Apply corrections proportional to the search space
- Report the "selection bias adjusted" performance
