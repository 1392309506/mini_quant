"""测试 yfinance + curl_cffi 绕过封锁（无emoji版本）"""
import yfinance as yf
import sys, os, time

print("=" * 50)
print("yfinance 版本:", getattr(yf, "__version__", "unknown"))

# 检查代理
for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"]:
    val = os.environ.get(env_var)
    if val:
        print(f"发现代理 {env_var}={val}")

# 测试 curl_cffi
try:
    from curl_cffi import requests as curl_requests
    session = curl_requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    print("\n--- curl_cffi 测试 ---")
    df = yf.download("AAPL", start="2025-01-01", end="2025-03-01", progress=False, session=session)
    if not df.empty:
        print(f"OK. 形状: {df.shape}")
    else:
        print("空数据")
except ImportError:
    print("curl_cffi 未安装")
except Exception as e:
    print(f"失败: {type(e).__name__}")

# 测试较长的延时
print("\n--- 长延时重试 ---")
for wait in [10, 20]:
    print(f"等待 {wait}s...")
    time.sleep(wait)
    try:
        df = yf.download("AAPL", start="2025-01-01", end="2025-03-01", progress=False)
        if not df.empty:
            print(f"OK. 形状: {df.shape}")
            break
    except Exception as e:
        print(f"失败: {type(e).__name__}")

print("\n测试结束")