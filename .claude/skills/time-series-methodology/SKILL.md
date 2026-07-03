---
name: time-series-methodology
description: Time series analysis standards for financial data — stationarity, cointegration, model selection, and data alignment. Use when building forecasting models, pairs trading, or analyzing price dynamics.
user-invocable: false
---

# Time-series methodology standards

## 1. Stationarity and unit root tests

- Test each series for stationarity before applying ARIMA/GARCH:
  - ADF test (Augmented Dickey-Fuller)
  - KPSS test (Kwiatkowski-Phillips-Schmidt-Shin)
  - PP test (Phillips-Perron)
- Apply differencing or transformation based on test results
- Document the test critical values and decisions

## 2. Cointegration and pairs

- Test cointegration with Engle-Granger or Johansen procedure
- Verify residual stationarity before trading the spread
- Report hedge ratio estimation method (OLS vs. Kalman filter)
- Account for transaction costs in deviation thresholds

## 3. Time-series models

- **ARIMA**: select p,d,q via AIC/BIC, not by searching every combination blindly
- **VAR**: test lag length, Granger causality, impulse response
- **GARCH**: test ARCH effects first; consider asymmetric GARCH (EGARCH, GJR-GARCH) for leverage effects

## 4. Cross-sectional and time-series partitioning

- Training/validation/test splits must be chronological — never random
- Expanding window vs. rolling window: state the choice and its implications
- Minimum training period should cover at least one full market cycle

## 5. Time-series cross-validation

- Use purged walk-forward (like López de Prado CV)
- No leakage from training to test sets
- Gap between training and test sets when necessary (e.g., for overlapped labels)

## 6. Missing values and outliers

- Forward-fill for price data; use interpolation with caution
- Outlier handling: winsorization vs. trimming — document the threshold and rationale
- Missing data patterns: MCAR/MAR/MNAR
- Never fill missing returns with 0

## 7. Multi-frequency alignment

- Align daily, intraday, and fundamental data to the lowest common frequency
- Document timestamp handling (exchange time vs. local time, DST transitions)
- Avoid mixing IB start-of-bar with close-of-bar timestamps

## 8. Persistence and autocorrelation

- Test return autocorrelation (Ljung-Box Q-test)
- Report half-life of mean reversion for stationary spreads
- Account for serial correlation in Sharpe ratio calculation (Lo 2002 adjustment)
