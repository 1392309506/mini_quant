"""测试 AKShare 获取美股 - 多方案"""
import akshare as ak
import pandas as pd

print("AKShare 版本:", getattr(ak, "__version__", "unknown"))
print()

# 方法1: 标准接口
tests = [
    ("stock_us_hist", lambda: ak.stock_us_hist(symbol="AAPL", period="daily")),
    ("stock_us_hist_em", lambda: ak.stock_us_hist_em(symbol="AAPL")),
    ("stock_us_spot_em", lambda: ak.stock_us_spot_em().head(3)),
]

for name, fn in tests:
    print(f"--- {name} ---")
    try:
        df = fn()
        print(f"形状: {df.shape}")
        print(f"列: {list(df.columns)}")
        if not df.empty:
            print(df.head(1).to_string())
        print("OK\n")
    except Exception as e:
        print(f"失败: {type(e).__name__}: {str(e)[:300]}\n")