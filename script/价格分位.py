# -*- coding: utf-8 -*-
"""用新浪日K线计算当前价格在区间内的历史分位（东方财富/akshare 在本机常因代理或断连失败）。"""
import json
import re
from datetime import datetime

import pandas as pd
import requests

SINA_KLINE_URL = (
    "https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_data=/"
    "CN_MarketDataService.getKLineData"
)
HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def _to_sina_symbol(stock_code: str) -> str:
    """601166 / sh601166 / 518800 -> 新浪 symbol。"""
    code = stock_code.strip().lower()
    if code.startswith(("sh", "sz")):
        return code
    # 5/6/9 开头多为沪市，其余按深市
    prefix = "sh" if code[0] in "569" else "sz"
    return f"{prefix}{code}"


def _fetch_sina_kline(symbol: str, datalen: int = 320) -> list[dict]:
    session = requests.Session()
    session.trust_env = False  # 不走系统/环境代理
    resp = session.get(
        SINA_KLINE_URL,
        params={"symbol": symbol, "scale": 240, "ma": "no", "datalen": datalen},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    text = resp.text.strip()
    if not text:
        raise ValueError(f"接口返回空内容，HTTP {resp.status_code}")

    m = re.search(r"(\[[\s\S]*\])", text)
    if m:
        payload = m.group(1)
    else:
        payload = text
        if payload.startswith("var"):
            payload = payload.split("=", 1)[1].strip()
        payload = payload.rstrip(";").strip()
        if payload.startswith("(") and payload.endswith(")"):
            payload = payload[1:-1].strip()

    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError(f"接口返回格式异常: {str(data)[:200]}")
    return data


def get_price_quantile(stock_code, start_date="20260101", end_date="20261231"):
    """
    获取指定股票的历史数据并计算当前价格的历史分位数
    :param stock_code: 股票代码，如 "600000" / "sh518800"
    :param start_date: 历史数据开始日期 YYYYMMDD
    :param end_date: 历史数据结束日期 YYYYMMDD
    :return: 当前价格, 历史分位数
    """
    try:
        symbol = _to_sina_symbol(stock_code)
        raw = _fetch_sina_kline(symbol)
        if not raw:
            return None, None

        df = pd.DataFrame(raw)
        df["day"] = pd.to_datetime(df["day"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
        df = df[(df["day"] >= start) & (df["day"] <= end)].dropna(subset=["close"])
        if df.empty:
            return None, None

        current_price = float(df["close"].iloc[-1])
        percentile_rank = (df["close"] < current_price).sum() / len(df)
        return current_price, float(percentile_rank)

    except Exception as e:
        print(f"获取数据或计算出错: {e}")
        return None, None


# 测试
# 兴业：601166 招商：600036 中国平安：601318
# 黄金etf:sh518800 国债etf：sh511100
if __name__ == "__main__":
    code = "600036"
    price, quantile = get_price_quantile(code)

    if price is not None:
        print(f"股票代码: {code}")
        print(f"当前收盘价: {price}")
        print(f"历史价格分位: {quantile:.2%}")
    else:
        print("未能获取到有效数据，请检查股票代码或网络连接。")
