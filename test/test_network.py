"""检查网络连通性"""
import requests
import os

# 1. 检查环境中的代理设置
print("=== 环境代理设置 ===")
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "REQUESTS_CA_BUNDLE"]:
    val = os.environ.get(var)
    if val:
        print(f"  {var}={val}")

# 2. 测试基础连通性
targets = [
    ("百度", "https://www.baidu.com"),
    ("Yahoo", "https://finance.yahoo.com"),
    ("EastMoney", "https://push2his.eastmoney.com"),
    ("AlphaVantage", "https://www.alphavantage.co"),
    ("Google", "https://www.google.com"),
    ("GitHub", "https://raw.githubusercontent.com"),
]

print("\n=== 连通性测试 ===")
for name, url in targets:
    try:
        r = requests.get(url, timeout=10, verify=False)
        print(f"  {name}: {r.status_code} ({len(r.content)} bytes)")
    except requests.exceptions.SSLError as e:
        print(f"  {name}: SSL错误 - {str(e)[:60]}")
    except requests.exceptions.ProxyError as e:
        print(f"  {name}: 代理错误 - {str(e)[:60]}")
    except requests.exceptions.ConnectionError as e:
        print(f"  {name}: 连接失败 - {str(e)[:60]}")
    except requests.exceptions.Timeout:
        print(f"  {name}: 超时")
    except Exception as e:
        print(f"  {name}: {type(e).__name__} - {str(e)[:60]}")