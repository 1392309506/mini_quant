"""
Universe — 交易标的池

数据源存储在 universe.txt（一行一个 ticker，# 开头的是注释）。
增删标的只需编辑 universe.txt。
"""

from pathlib import Path

_TXT_PATH = Path(__file__).resolve().parent / "universe.txt"


def _load():
    """读取 universe.txt，返回 (ticker列表, 元数据列表)。"""
    tickers = []
    metadata = []
    current_sector = None
    with open(_TXT_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 注释行：提取板块名
            if line.startswith("#"):
                # 尝试提取 === ... === 内的板块名
                if "===" in line:
                    # 取第一个 === 到最后一个 === 之间的内容
                    start = line.index("===") + 3
                    end = line.rindex("===")
                    sector = line[start:end].strip()
                    if sector and "|" in sector:
                        sector = sector.split("|")[0].strip()
                    if sector:
                        current_sector = sector
                continue
            # ticker 行
            ticker = line.upper()
            tickers.append(ticker)
            metadata.append({"symbol": ticker, "sector": current_sector or "其他"})
    return tickers, metadata


# 纯 ticker 列表，向下兼容
TRADE_UNIVERSE, UNIVERSE = _load()

# 为每个 symbol 自动创建模块级常量（如 AAPL = "AAPL"），方便 IDE 补全
for sym in TRADE_UNIVERSE:
    globals()[sym] = sym