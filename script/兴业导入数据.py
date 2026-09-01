# -*- coding: utf-8 -*-
"""
使用新浪财经接口获取兴业银行(601166)近一年日K线数据，写入 SQLite kline 表
依赖：pip install requests
"""
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta

import requests

# ========== 配置 ==========
# 相对本脚本定位，避免调试时 cwd 不同导致连错库
DB_PATH = "D:\\app\\StockWidget\\SW_quotes.db"
CODE    = "601166"         # 兴业银行股票代码
NAME    = "兴业银行"
SYMBOL  = "sh601166"       # 新浪代码：sh=上海交易所, sz=深圳交易所

_CREATE_KLINE_SQL = """
CREATE TABLE IF NOT EXISTS kline (
    code TEXT NOT NULL,
    name TEXT,
    trade_date TEXT NOT NULL,
    "open" REAL,
    high REAL,
    low REAL,
    "close" REAL,
    volume REAL,
    amount REAL,
    updated_at TEXT,
    PRIMARY KEY (code, trade_date)
)
"""

# 新浪日K线接口
# scale=240 表示日K线（一天240分钟）；datalen 为返回条数，一年约250个交易日
URL = "https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_data=/CN_MarketDataService.getKLineData"

params = {
    "symbol": SYMBOL,
    "scale": 240,
    "ma": "no",
    "datalen": 300,          # 多取一些，稍后按近一年日期本地过滤
}

headers = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
# ==========================


def fetch_kline(url, params, headers):
    """请求新浪接口并解析为 list[dict]（兼容 JSON 与 JSONP 两种返回）"""
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    # 接口声明 charset=gbk，按响应头解码更稳妥
    resp.encoding = resp.apparent_encoding or "utf-8"
    text = resp.text.strip()
    if not text:
        raise ValueError(f"接口返回空内容，HTTP {resp.status_code}")

    # 实际返回形如：
    # /*<script>...</script>*/
    # var _data=([{...}, ...]);
    # 优先抽取最外层 JSON 数组，兼容纯 JSON / 带括号的 JSONP
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

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"无法解析接口返回为 JSON: {e}; 正文前 200 字: {text[:200]!r}"
        ) from e

    if not isinstance(data, list):
        raise ValueError(f"接口返回格式异常: {str(data)[:200]}")
    return data


def main():
    # ---------- 1. 拉取数据 ----------
    print(f"正在从新浪接口拉取 {NAME}({SYMBOL}) 日K线 ...")
    data = fetch_kline(URL, params, headers)
    print(f"接口返回 {len(data)} 条原始K线")

    if not data:
        raise SystemExit("未获取到数据，请检查网络或代码是否正确")

    # ---------- 2. 过滤近一年并映射字段 ----------
    cutoff = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    today  = datetime.now().strftime("%Y-%m-%d")
    now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows, seen = [], set()
    for item in data:
        d = item["day"]
        # 只保留近一年且不超过今天的交易日
        if not (cutoff <= d <= today):
            continue
        if d in seen:                 # 去重
            continue
        seen.add(d)

        rows.append((
            CODE,
            NAME,
            d,
            float(item["open"]),      # 开盘
            float(item["high"]),      # 最高
            float(item["low"]),       # 最低
            float(item["close"]),     # 收盘
            float(item.get("volume", 0)),   # 成交量（股）
            float(item.get("amount", 0)),   # 成交额（元，部分新浪接口可能不含）
            now,
        ))

    if not rows:
        raise SystemExit("过滤后没有符合近一年范围的数据")

    print(f"过滤后共 {len(rows)} 条（{rows[0][2]} ~ {rows[-1][2]}）")
    print("示例：", rows[0][2], "开", rows[0][3], "高", rows[0][4],
          "低", rows[0][5], "收", rows[0][6])

    # ---------- 3. 写入 SQLite ----------
    print(f"写入数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(_CREATE_KLINE_SQL)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kline_code_date "
            "ON kline(code, trade_date)"
        )
        # INSERT OR REPLACE：已存在的日期覆盖更新，重复运行安全
        sql = """
            INSERT OR REPLACE INTO kline
                (code, name, trade_date, "open", high, low, "close",
                 volume, amount, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        conn.executemany(sql, rows)
        conn.commit()

        # ---------- 4. 校验 ----------
        cur = conn.execute(
            "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) "
            "FROM kline WHERE code = ?",
            (CODE,),
        )
        cnt, dmin, dmax = cur.fetchone()
        print(f"写入完成！kline 表中 {NAME} 共 {cnt} 条，区间 {dmin} ~ {dmax}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()