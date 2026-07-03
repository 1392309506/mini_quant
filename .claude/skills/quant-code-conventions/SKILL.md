---
name: quant-code-conventions
description: Coding conventions for quant finance projects — pandas/NumPy usage, data contracts, testing, config separation, and reproducibility. Use whenever writing or reviewing Python code for this project.
user-invocable: false
---

# Quant code conventions

## 1. pandas / NumPy usage

- Prefer `.loc`, `.iloc`, `.xs` over chained indexing (`df[][][]`)
- Never assign to a slice — always use `.loc[row, col] = value`
- Use `pd.DataFrame` for tabular data, not dict of arrays
- Use `pd.MultiIndex` for panel data (ticker × field)
- Avoid `df.append` or `df.iterrows()` in any performance-sensitive code
- Use vectorized operations over apply/lambda where possible

## 2. Data contracts

- Price data columns: `Date` (index, sorted ascending), `Open`, `High`, `Low`, `Close`, `Volume`
- Index: `pd.DatetimeIndex` with exchange timezone
- Factor panel: `pd.MultiIndex` columns `(ticker, factor_name)`
- Never modify the original OHLCV DataFrame in place

## 3. Time handling

- All timestamps in UTC or exchange-local time — state which
- Never use ambiguous date strings like `"01/02/2025"` — use ISO 8601 (`"2025-01-02"`)
- Use `pd.Timestamp.today()` or `pd.Timestamp.now(tz=...)`, not `datetime.now()`
- DST transitions: avoid ambiguous hours by using UTC

## 4. Configuration

- All tunable parameters go in `config.py`, not hard-coded in functions
- Secrets (API keys, credentials) go in `.env`, never in code
- Use `python-dotenv` to load `.env`, not hand-rolled parsers
- Default parameters should be named constants, not magic numbers

## 5. Random seeds

- Set `np.random.seed(42)` before any stochastic operation
- For ML: set `random_state=42` in all estimators
- For reproducible backtests: use `set_seed(42)` at the start of each run
- Document all seeds in experiment logs

## 6. Testing

- Factor functions are pure functions → write pytest tests for them
- Test edge cases: all-NaN input, single-row input, zero-variance data
- Test IC calculation against a known example
- Test backtest reproducibility with fixed inputs

## 7. Experiment recording

- Save experiment config alongside results (JSON or YAML)
- Record git commit hash in results metadata
- Log all hyperparameters and data range
- Output directory: `data/experiments/<YYYYMMDD_shortdesc>/`
- Never overwrite previous experiment results

## 8. Package structure

- `__init__.py` exports the public API, hides internal functions
- `pyproject.toml` for package metadata and dependencies
- No relative imports: use `from quant.factors import ...`
- CLI entry points via `[project.scripts]` in pyproject.toml
