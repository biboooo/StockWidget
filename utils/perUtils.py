# -*- coding: utf-8 -*-
"""价格 / 估值（PE·PB·PS·PCF）历史分位。

价格走新浪日K；估值走东方财富 datacenter（push2his 在本机常断连，datacenter 可用）。
请求均 trust_env=False，避开失效代理。
"""
import json
import re
from datetime import datetime

import pandas as pd
import requests

SINA_KLINE_URL = (
    "https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_data=/"
    "CN_MarketDataService.getKLineData"
)
EM_VALUE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
HEADERS_SINA = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
HEADERS_EM = {
    "Referer": "https://data.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# 估值字段：展示名 -> 接口列名
VALUATION_FIELDS = {
    "PE": "PE_TTM",    # 市盈率(TTM)
    "PB": "PB_MRQ",    # 市净率
    "PS": "PS_TTM",    # 市销率(TTM)
    "PCF": "PCF_OCF_TTM",  # 市现率(经营现金流 TTM)
}


def _session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False  # 不走系统/环境代理
    return s


def _to_sina_symbol(stock_code: str) -> str:
    """601166 / sh601166 / 518800 -> 新浪 symbol。"""
    code = stock_code.strip().lower()
    if code.startswith(("sh", "sz")):
        return code
    # 5/6/9 开头多为沪市，其余按深市
    prefix = "sh" if code[0] in "569" else "sz"
    return f"{prefix}{code}"


def _to_plain_code(stock_code: str) -> str:
    """sh600036 / 600036.SH / 600036 -> 600036。"""
    code = stock_code.strip().upper()
    if "." in code:
        code = code.split(".", 1)[0]
    if code.startswith(("SH", "SZ")):
        code = code[2:]
    return code


def _percentile_rank(series: pd.Series, current: float) -> float:
    """当前值在序列中的历史分位（低于当前值的占比）。"""
    return float((series < current).sum() / len(series))


def _fetch_sina_kline(symbol: str, datalen: int = 320) -> list[dict]:
    resp = _session().get(
        SINA_KLINE_URL,
        params={"symbol": symbol, "scale": 240, "ma": "no", "datalen": datalen},
        headers=HEADERS_SINA,
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


def _fetch_em_valuation(plain_code: str, page_size: int = 500) -> list[dict]:
    """东方财富个股日频估值：PE_TTM / PB_MRQ / PS_TTM / PCF_OCF_TTM。"""
    cols = "SECURITY_CODE,TRADE_DATE," + ",".join(VALUATION_FIELDS.values())
    resp = _session().get(
        EM_VALUE_URL,
        params={
            "reportName": "RPT_VALUEANALYSIS_DET",
            "columns": cols,
            "filter": f'(SECURITY_CODE="{plain_code}")',
            "pageNumber": "1",
            "pageSize": str(page_size),
            "sortTypes": "-1",
            "sortColumns": "TRADE_DATE",
            "source": "WEB",
            "client": "WEB",
        },
        headers=HEADERS_EM,
        timeout=20,
    )
    resp.raise_for_status()
    body = resp.json()
    result = body.get("result") or {}
    data = result.get("data") or []
    if not data:
        raise ValueError(f"估值接口无数据: {plain_code} / {str(body)[:200]}")
    return data


def get_price_quantile(stock_code, start_date="20250901", end_date="20261231"):
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
        return current_price, _percentile_rank(df["close"], current_price)

    except Exception as e:
        print(f"获取价格分位出错: {e}")
        return None, None


def get_valuation_quantiles(stock_code, start_date="20250901", end_date="20261231"):
    """
    计算 PE / PB / PS / PCF 在区间内的历史分位。
    :return: dict，如 {"PE": {"value": 6.79, "quantile": 0.25}, ...}；失败项为 None
    """
    out = {k: None for k in VALUATION_FIELDS}
    try:
        plain = _to_plain_code(stock_code)
        raw = _fetch_em_valuation(plain)
        df = pd.DataFrame(raw)
        df["TRADE_DATE"] = pd.to_datetime(df["TRADE_DATE"])
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
        df = df[(df["TRADE_DATE"] >= start) & (df["TRADE_DATE"] <= end)]
        if df.empty:
            return out

        df = df.sort_values("TRADE_DATE")
        for key, col in VALUATION_FIELDS.items():
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if s.empty:
                continue
            current = float(s.iloc[-1])
            out[key] = {"value": current, "quantile": _percentile_rank(s, current)}
        return out

    except Exception as e:
        print(f"获取估值分位出错: {e}")
        return out


def _val_pair(vals: dict, key: str):
    item = vals.get(key) if vals else None
    if not item:
        return None, None
    return item.get("value"), item.get("quantile")


def save_quantiles_to_db(
    db_path: str,
    stock_code: str,
    start_date: str = "20250901",
    end_date: str = "20261231",
):
    """拉取价格+估值分位并写入 SW_quotes.db 的 valuation_quantile 表。"""
    from widget.quote_db import init_db

    price, price_q = get_price_quantile(stock_code, start_date, end_date)
    vals = get_valuation_quantiles(stock_code, start_date, end_date)
    pe, pe_q = _val_pair(vals, "PE")
    pb, pb_q = _val_pair(vals, "PB")
    ps, ps_q = _val_pair(vals, "PS")
    pcf, pcf_q = _val_pair(vals, "PCF")

    # 与行情库统一用 sh/sz 前缀
    store_code = _to_sina_symbol(stock_code)
    db = init_db(db_path)
    db.upsert_valuation_quantile(
        store_code,
        range_start=start_date,
        range_end=end_date,
        price=price,
        price_q=price_q,
        pe=pe,
        pe_q=pe_q,
        pb=pb,
        pb_q=pb_q,
        ps=ps,
        ps_q=ps_q,
        pcf=pcf,
        pcf_q=pcf_q,
    )
    return db.load_valuation_quantile(store_code)


# 测试
# 兴业：601166 招商：600036 中国平安：601318
# 黄金etf:sh518800 国债etf：sh511100
# 伊利：sh600887
if __name__ == "__main__":
    import os
    import sys

    # ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # if ROOT not in sys.path:
    #     sys.path.insert(0, ROOT)

    code = "sh600887"
    start, end = "20250901", "20261231"
    db_path = "D:\\app\\StockWidget\\SW_quotes.db"
    row = save_quantiles_to_db(db_path, code, start, end)

    print(f"股票代码: {code}")
    if row and row.get("price") is not None:
        print(f"当前收盘价: {row['price']}")
        print(f"历史价格分位: {row['price_q']:.2%}")
    else:
        print("未能获取价格分位")

    labels = {
        "pe": "PE（市盈率）分位",
        "pb": "PB（市净率）分位",
        "ps": "PS（市销率）分位",
        "pcf": "PCF（市现率）分位",
    }
    for key, label in labels.items():
        q = row.get(f"{key}_q") if row else None
        v = row.get(key) if row else None
        if q is not None and v is not None:
            print(f"{label}: {q:.2%}（当前 {v:.4f}）")
        else:
            print(f"{label}: 无数据")
    print(f"已写入: {db_path} -> valuation_quantile")
