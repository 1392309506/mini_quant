"""Test Yahoo Finance connectivity from China"""
import yfinance as yf
import time

for wait in [1, 5, 10]:
    print(f"\n--- 等待 {wait}s 后下载 AAPL ---")
    time.sleep(wait)
    try:
        df = yf.download("AAPL", start="2025-01-01", end="2025-03-01", progress=False)
        print(f"形状: {df.shape}")
        if not df.empty:
            print(f"✅ 成功: {len(df)} 行")
            print(df.tail(2))
        else:
            print(f"⚠️ 空数据")
    except Exception as e:
        print(f"❌ 失败: {type(e).__name__}: {e}")