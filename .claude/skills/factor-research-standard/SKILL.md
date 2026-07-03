---
name: factor-research-standard
description: Standards for factor construction, evaluation, and reporting in equity multi-factor models. Use when building, testing, or reviewing factors.
user-invocable: false
---

# Factor research standards

## 1. Factor construction

- Document the factor formula precisely (LaTeX or code reference)
- Factor universe: state the starting universe and any filters applied
- Frequency: daily, weekly, monthly — match factor horizon to prediction horizon
- Data source: document vendor, symbol mapping, corporate action treatment
- Outlier handling: cross-sectional winsorization at 1%/99% or median ± 5x MAD

## 2. Normalization and neutralization

- **De-extreme**: winsorize or rank — rank is more robust
- **Standardize**: z-score transformation, or rank-based percentile
- **Neutralize**: market, sector, and size (Fama-French industry, log market cap)
- Orthogonalization: residual after regressing out control variables
- Re-normalize each period (cross-sectionally), never use in-sample moments

## 3. IC-based evaluation

- **IC (Information Coefficient)**: Spearman rank correlation between factor and forward returns
- **Rank IC**: same, preferred over Pearson for robustness
- **ICIR (Information Coefficient ICIR)**: IC mean / IC std — measures IC consistency
- Report daily/weekly/monthly IC time series
- IC decay: report IC at `t+1, t+2, t+5, t+10, t+21` to see signal half-life

## 4. Layer-based evaluation

- Decile or quintile portfolios: long top decile, short bottom decile
- Report cumulative returns of each layer
- Net of transaction costs: layers with higher turnover cost more
- Report layer spread: annualized return, Sharpe, max DD
- Monotonicity: layers should show monotonic return progression

## 5. Turnover analysis

- Report one-way and two-way turnover per layer
- Net-of-costs spread: apply realistic cost per layer
- For high-turnover factors: extend holding period or use trading signal aggregation

## 6. Exposure analysis

- Report factor exposure to sectors and market cap
- Effective spread after neutralization
- Time-series of factor crowding (correlation with other active factors)

## 7. Factor redundancy

- Pairwise correlation matrix across all candidate factors
- Cluster correlated factors (>0.6) and retain representative
- Variance inflation factor (VIF) test: VIF < 5 is acceptable
- Principal component analysis: number of components retained

## 8. Factor decay and monitoring

- Run IC and layer performance in a rolling 12-month window
- Signal for factor decay: ICIR trending toward zero
- Regime dependence: test factor performance across bull/bear/high-vol regimes
- Redundancy review: re-check correlation matrix quarterly — add new, retire decaying factors
