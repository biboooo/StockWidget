# -*- coding: utf-8 -*-
"""从新浪财经接口抓取A股股票基本信息，写入 SW_quotes.db 的 stock_info 表"""
import json
import sqlite3
import time

import requests

DB_PATH = "D:\\app\\StockWidget\\SW_quotes.db"   # 请按实际数据库文件路径修改
SINA_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn",
}


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_page(node, page, num=100):
    """抓取一页数据，新浪返回 GBK 编码的 JSON"""
    params = {"page": page, "num": num, "sort": "symbol", "asc": 1, "node": node, "_s_r_a": "page"}
    resp = requests.get(SINA_URL, params=params, headers=HEADERS, timeout=15)
    text = resp.content.decode("gbk", errors="ignore")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(resp.content.decode("utf-8", errors="ignore"))


def fetch_all_stocks(nodes=("hs_a",)):
    """循环分页抓取全部A股"""
    stocks = []
    for node in nodes:
        page = 1
        while True:
            data = fetch_page(node, page)
            if not data:
                break
            stocks.extend(data)
            print(f"[{node}] 第 {page} 页，累计 {len(stocks)} 条")
            if len(data) < 100:
                break
            page += 1
            time.sleep(0.3)
    return stocks


def detect_exchange(code):
    if code.startswith("6"):
        return "上交所"
    if code.startswith(("0", "3")):
        return "深交所"
    if code.startswith(("4", "8")):
        return "北交所"
    return "未知"


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 确保表存在（幂等）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_info (
            code             TEXT PRIMARY KEY,
            name             TEXT,
            exchange         TEXT,
            industry         TEXT,
            listing_date     TEXT,
            total_shares     REAL,
            float_shares     REAL,
            total_market_cap REAL,
            float_market_cap REAL,
            updated_at       TEXT
        )
    """)
    # 添加扩展列（已存在则忽略）
    for col_sql in ("ALTER TABLE stock_info ADD COLUMN per REAL",
                    "ALTER TABLE stock_info ADD COLUMN pb REAL",
                    "ALTER TABLE stock_info ADD COLUMN turnoverratio REAL"):
        try:
            cur.execute(col_sql)
        except sqlite3.OperationalError:
            pass

    stocks = fetch_all_stocks()
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    for s in stocks:
        code = s.get("code", "")
        if not code:
            continue
        cur.execute("""
            INSERT OR REPLACE INTO stock_info
            (code, name, exchange, total_market_cap, float_market_cap,
             per, pb, turnoverratio, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            code,
            s.get("name", ""),
            detect_exchange(code),
            to_float(s.get("mktcap")),      # 总市值(元)
            to_float(s.get("nmc")),         # 流通市值(元)
            to_float(s.get("per")),
            to_float(s.get("pb")),
            to_float(s.get("turnoverratio")),
            now,
        ))

    conn.commit()
    print(f"完成：共写入 {len(stocks)} 条记录")
    conn.close()


if __name__ == "__main__":
    main()