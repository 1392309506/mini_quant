"""测试 AKShare 获取美股数据"""
import akshare as ak
import pandas as pd

print("AKShare 版本:", getattr(ak, "__version__", "unknown"))

# 测试获取 AAPL 历史数据
print("\n--- 测试: 获取 AAPL 日线数据 ---")
try:
    df = ak.stock_us_hist(symbol="AAPL", period="daily")
    print(f"形状: {df.shape}")
    print(f"列: {list(df.columns)}")
    if not df.empty:
        print(f"日期范围: {df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]}")
        print(df.tail(3))
    print("OK - AAPL 美股数据获取成功")
except Exception as e:
    print(f"失败: {type(e).__name__}: {str(e)[:200]}")

print("\n测试结束")