"""测试 yfinance 各种姿势"""
import yfinance as yf
import requests

print("yfinance版本:", getattr(yf, "__version__", "unknown"))

# 方式1: 自定义 User-Agent
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
})

for label, kwargs in [
    ("默认", {}),
    ("自定义 UA", {"session": session}),
]:
    print(f"\n--- {label} ---")
    try:
        df = yf.download("AAPL", start="2025-01-01", end="2025-03-01", progress=False, **kwargs)
        print(f"形状: {df.shape}")
        if not df.empty:
            print("✅ 成功")
        else:
            print("⚠️ 空数据")
    except Exception as e:
        print(f"❌ {type(e).__name__}: {str(e)[:200]}")