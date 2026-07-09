"""
config.py — 集中配置模块

读取顺序：环境变量 > .env 文件 > 代码默认值。

用法:
    from src.config import DATA_DIR, EXPERIMENTS_DIR, get_backend, get_proxies

交易标的池已移入 src/universe.py（经常调整），不在此处定义。
"""

from pathlib import Path
from typing import Dict, Optional
import os

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 项目路径
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
CACHE_FILE = DATA_DIR / "market_data.parquet"
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"
MODELS_DIR = PROJECT_ROOT / "models"
SIGNALS_DIR = DATA_DIR / "signals"

# ---------------------------------------------------------------------------
# 加载 .env（环境变量优先级高于 .env 文件中的值）
# ---------------------------------------------------------------------------
load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# 业务参数
# ---------------------------------------------------------------------------

# 缓存过期天数
STALE_DAYS = 7

# yfinance 批量下载参数
YF_BATCH_SIZE = 8
YF_PAUSE = 0.5

# Alpha Vantage 参数（免费层限制：5 次/分钟，500 次/天）
AV_CALL_INTERVAL = 12.0


# ---------------------------------------------------------------------------
# 配置读取函数
# ---------------------------------------------------------------------------


def get_backend() -> str:
    """读取数据后端配置，默认 yfinance"""
    return os.getenv("DATA_BACKEND", "yfinance").lower()


def get_proxies() -> Optional[Dict[str, str]]:
    """读取代理配置，返回 requests 兼容的 proxy dict"""
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if not proxy:
        return None
    return {
        "http": os.getenv("HTTP_PROXY", proxy),
        "https": proxy,
    }


def get_av_key() -> Optional[str]:
    """读取 Alpha Vantage API Key"""
    return os.getenv("ALPHA_VANTAGE_KEY")