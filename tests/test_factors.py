"""
因子计算纯函数单元测试。

测试 13 个因子函数的：
  - 输入输出形状
  - 值域范围
  - NaN 处理
  - 边界稳定性
"""

import pytest
import pandas as pd
import numpy as np

# ── 测试数据生成 ────────────────────────────────────────


@pytest.fixture
def sample_close():
    """100 天连续上涨的收盘价序列。"""
    return pd.Series(np.linspace(100, 200, 100), name="AAPL")


@pytest.fixture
def sample_high():
    return pd.Series(np.linspace(101, 202, 100), name="AAPL")


@pytest.fixture
def sample_low():
    return pd.Series(np.linspace(99, 198, 100), name="AAPL")


@pytest.fixture
def sample_volume():
    return pd.Series(np.ones(100) * 1_000_000, name="AAPL")


@pytest.fixture
def flat_close():
    """50 天无波动的收盘价序列。"""
    return pd.Series(np.ones(50) * 100, name="AAPL")


# ════════════════════════════════════════════════════
# 动量类因子
# ════════════════════════════════════════════════════

class TestMomentum:

    def test_momo_20_shape(self, sample_close):
        from src.factors.momentum import momo_20
        result = momo_20(sample_close)
        assert len(result) == 100
        assert result.iloc[-1] > 0  # 上涨趋势

    def test_momo_20_range(self, sample_close):
        from src.factors.momentum import momo_20
        result = momo_20(sample_close)
        assert result.min() >= -1.0  # 最大跌幅 -100%
        assert result.iloc[-1] <= 2.0  # 连续涨 100 天不超 200%

    def test_momo_20_flat(self, flat_close):
        from src.factors.momentum import momo_20
        result = momo_20(flat_close)
        assert np.isclose(result.iloc[-1], 0, atol=1e-6)

    def test_momo_60_shape(self, sample_close):
        from src.factors.momentum import momo_60
        result = momo_60(sample_close)
        assert len(result) == 100

    def test_mom_ratio(self, sample_close):
        from src.factors.momentum import momo_20, momo_60, mom_ratio
        m20 = momo_20(sample_close)
        m60 = momo_60(sample_close)
        ratio = mom_ratio(m20, m60)
        assert len(ratio) == 100
        assert ratio.min() >= -5.0
        assert ratio.max() <= 5.0


# ════════════════════════════════════════════════════
# 均值回归类因子
# ════════════════════════════════════════════════════

class TestMeanReversion:

    def test_rsi_14_shape(self, sample_close):
        from src.factors.mean_reversion import rsi_14
        result = rsi_14(sample_close)
        assert len(result) == 100

    def test_rsi_14_range(self, sample_close):
        from src.factors.mean_reversion import rsi_14
        result = rsi_14(sample_close)
        assert result.min() >= 0
        assert result.max() <= 100

    def test_rsi_14_rising(self, sample_close):
        """连续上涨 -> RSI 接近 100。"""
        from src.factors.mean_reversion import rsi_14
        result = rsi_14(sample_close)
        assert result.iloc[-1] > 70

    def test_bb_position(self, sample_close):
        from src.factors.mean_reversion import bb_position
        result = bb_position(sample_close)
        assert len(result) == 100
        assert result.min() >= -0.1
        assert result.max() <= 1.1

    def test_vol_ma_ratio(self, sample_volume):
        from src.factors.mean_reversion import vol_ma_ratio
        result = vol_ma_ratio(sample_volume)
        assert len(result) == 100
        # 恒定成交量 → 比值 ≈ 1.0
        assert np.isclose(result.iloc[-1], 1.0, atol=0.1)


# ════════════════════════════════════════════════════
# 波动率类因子
# ════════════════════════════════════════════════════

class TestVolatility:

    def test_atr_20(self, sample_high, sample_low, sample_close):
        from src.factors.volatility import atr_20
        result = atr_20(sample_high, sample_low, sample_close)
        assert len(result) == 100
        assert result.min() >= 0

    def test_volatility_20(self, sample_close):
        from src.factors.volatility import volatility_20
        result = volatility_20(sample_close)
        assert len(result) == 100
        assert result.min() >= 0


# ════════════════════════════════════════════════════
# 新因子（BB_WIDTH, HIGH_LOW_RATIO, ULCER_INDEX 等）
# ════════════════════════════════════════════════════

class TestNewFactors:

    def test_bb_width(self, sample_close):
        from src.factors.new_factors import bb_width
        result = bb_width(sample_close)
        assert len(result) == 100
        assert result.iloc[-40:].dropna().min() >= 0

    def test_high_low_ratio(self, sample_high, sample_low, sample_close):
        from src.factors.new_factors import high_low_ratio
        result = high_low_ratio(sample_high, sample_low, sample_close)
        assert len(result) == 100
        assert result.iloc[-40:].dropna().min() >= 0

    def test_chaikin_mf(self, sample_high, sample_low, sample_close, sample_volume):
        from src.factors.new_factors import chaikin_mf
        result = chaikin_mf(sample_high, sample_low, sample_close, sample_volume)
        assert len(result) == 100

    def test_ulcer_index(self, sample_close):
        from src.factors.new_factors import ulcer_index
        result = ulcer_index(sample_close)
        assert len(result) == 100
        assert result.iloc[-40:].dropna().min() >= 0

    def test_max_dd_60(self, sample_close):
        from src.factors.new_factors import max_dd_60
        # 需要 120+ 天数据（60+60 天窗口）
        long_series = pd.Series(
            np.linspace(100, 200, 150), name="AAPL"
        )
        result = max_dd_60(long_series)
        tail = result.iloc[-40:].dropna()
        assert len(tail) > 0
        assert tail.max() <= 0  # 最大回撤为非正值


# ════════════════════════════════════════════════════
# 信号生成
# ════════════════════════════════════════════════════

class TestSignals:

    def test_rebalance_calendar_weekly(self):
        from src.models.signals import generate_rebalance_calendar
        start = pd.Timestamp("2026-01-01")
        end = pd.Timestamp("2026-06-30")
        cal = generate_rebalance_calendar(start, end, max_per_week=2)
        assert len(cal) > 0

    def test_entry_signals_shape(self):
        from src.models.signals import (
            generate_rebalance_calendar, generate_entry_signals
        )
        tickers = ["AAPL", "MSFT", "GOOGL"]
        dates = pd.date_range("2026-01-01", "2026-03-31", freq="B")

        # 生成 multi-index 格式的预测（与真实 daily_inference 输出一致）
        n = len(dates)
        pred_data = []
        for t in tickers:
            for d in dates:
                pred_data.append({"Date": d, "ticker": t, "pred": np.random.randn()})
        pred = pd.DataFrame(pred_data).set_index(["Date", "ticker"])

        close = pd.DataFrame(
            np.random.randn(n, len(tickers)) + 100,
            index=dates, columns=tickers,
        )
        rebal = generate_rebalance_calendar(
            dates[0], dates[-1], max_per_week=2
        )
        entries = generate_entry_signals(pred, rebal, close, top_k=2)
        assert entries.shape == (n, len(tickers))
        assert entries.dtypes.iloc[0] == bool

    def test_exit_signals_shape(self):
        from src.models.signals import generate_exit_signals
        dates = pd.date_range("2026-01-01", "2026-03-31", freq="B")
        tickers = ["AAPL", "MSFT", "GOOGL"]
        entries = pd.DataFrame(
            np.random.rand(len(dates), len(tickers)) > 0.9,
            index=dates, columns=tickers,
        )
        exits = generate_exit_signals(entries, max_hold=10)
        assert exits.shape == entries.shape


if __name__ == "__main__":
    pytest.main([__file__, "-v"])