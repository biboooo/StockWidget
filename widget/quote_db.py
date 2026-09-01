# -*- coding: utf-8 -*-
"""SQLite：行情日快照 + 自选 watchlist。"""
import json
import sqlite3
from datetime import datetime
from typing import Any, Iterable, List, Optional, Sequence, Tuple


def _now() -> datetime:
    return datetime.now().astimezone().replace(microsecond=0)


def _norm_code(c: Any) -> str:
    if isinstance(c, dict):
        c = c.get("code", "")
    return str(c or "").strip().lower()


def _row_to_json(row: list) -> str:
    out = []
    for cell in row:
        if isinstance(cell, dict) and "k" in cell:
            k = cell["k"]
            out.append({"k": list(k) if isinstance(k, (list, tuple)) else k})
        else:
            out.append(cell)
    return json.dumps(out, ensure_ascii=False)


def _json_to_row(raw: str) -> list:
    out = []
    for cell in json.loads(raw):
        if isinstance(cell, dict) and "k" in cell:
            k = cell["k"]
            out.append({"k": tuple(k) if isinstance(k, list) else k})
        else:
            out.append(cell)
    return out


_CREATE_QUOTES_SQL = """
CREATE TABLE IF NOT EXISTS quotes (
    code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    name TEXT,
    row_json TEXT NOT NULL,
    sign_json TEXT NOT NULL,
    pnl_value REAL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (code, trade_date)
)
"""

_CREATE_WATCHLIST_SQL = """
CREATE TABLE IF NOT EXISTS watchlist (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    checked INTEGER NOT NULL DEFAULT 1,
    buy_point REAL,
    sell_point REAL,
    updated_at TEXT NOT NULL
)
"""


def _parse_point(v) -> Optional[float]:
    """将买卖点解析为 >0 的 float；无效返回 None。"""
    if v is None:
        return None
    try:
        f = float(v)
    except Exception:
        return None
    return f if f > 0 else None


class QuoteDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        '''启动时把「按股票一条」的旧行情表升级成「按股票+交易日」的日快照表，并确保自选表和索引齐全'''
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='quotes'"
            ).fetchone()
            if exists:
                cols = {r[1] for r in conn.execute("PRAGMA table_info(quotes)").fetchall()}
                if "trade_date" not in cols:
                    conn.execute("ALTER TABLE quotes RENAME TO quotes_legacy")
                    conn.execute(_CREATE_QUOTES_SQL)
                    conn.execute(
                        """
                        INSERT INTO quotes (code, trade_date, name, row_json, sign_json, pnl_value, updated_at)
                        SELECT code,
                               CASE WHEN length(updated_at) >= 10 THEN substr(updated_at, 1, 10)
                                    ELSE date('now', 'localtime') END,
                               name, row_json, sign_json, pnl_value, updated_at
                        FROM quotes_legacy
                        """
                    )
                    conn.execute("DROP TABLE quotes_legacy")
            conn.execute(_CREATE_QUOTES_SQL)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_quotes_code_date ON quotes(code, trade_date DESC)"
            )
            conn.execute(_CREATE_WATCHLIST_SQL)
            wl_cols = {r[1] for r in conn.execute("PRAGMA table_info(watchlist)").fetchall()}
            if "buy_point" not in wl_cols:
                conn.execute("ALTER TABLE watchlist ADD COLUMN buy_point REAL")
            if "sell_point" not in wl_cols:
                conn.execute("ALTER TABLE watchlist ADD COLUMN sell_point REAL")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_watchlist_sort ON watchlist(sort_order, code)"
            )
            conn.commit()

    def upsert_quotes(
        self,
        items: Sequence[Tuple[str, str, list, dict, Optional[float]]],
    ) -> None:
        """同日更新、异日新增。item: (code, name, row, sign, pnl_value)。"""
        if not items:
            return
        now = _now()
        trade_date = now.date().isoformat()
        now_iso = now.isoformat()
        rows = []
        for code, name, row, sign, pnl_value in items:
            key = _norm_code(code)
            if not key:
                continue
            rows.append(
                (
                    key,
                    trade_date,
                    name or "",
                    _row_to_json(row),
                    json.dumps(sign, ensure_ascii=False),
                    pnl_value,
                    now_iso,
                )
            )
        if not rows:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO quotes (code, trade_date, name, row_json, sign_json, pnl_value, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, trade_date) DO UPDATE SET
                    name=excluded.name,
                    row_json=excluded.row_json,
                    sign_json=excluded.sign_json,
                    pnl_value=excluded.pnl_value,
                    updated_at=excluded.updated_at
                """,
                rows,
            )
            conn.commit()

    def load_quotes(
        self, codes: Iterable[Any]
    ) -> Tuple[List[list], List[dict], float, bool]:
        """按顺序加载每个 code 最新一日快照。"""
        keys, seen = [], set()
        for c in codes:
            key = _norm_code(c)
            if key and key not in seen:
                seen.add(key)
                keys.append(key)
        if not keys:
            return [], [], 0.0, False

        placeholders = ",".join("?" * len(keys))
        with self._connect() as conn:
            cur = conn.execute(
                f"""
                SELECT q.code, q.row_json, q.sign_json, q.pnl_value
                FROM quotes q
                INNER JOIN (
                    SELECT code, MAX(trade_date) AS trade_date
                    FROM quotes WHERE code IN ({placeholders})
                    GROUP BY code
                ) latest ON q.code = latest.code AND q.trade_date = latest.trade_date
                """,
                keys,
            )
            by_code = {row[0]: row for row in cur.fetchall()}

        price_data, sign_data = [], []
        total_pnl, has_pnl = 0.0, False
        for key in keys:
            hit = by_code.get(key)
            if not hit:
                continue
            _, row_json, sign_json, pnl_value = hit
            try:
                row = _json_to_row(row_json)
                sign = json.loads(sign_json)
            except Exception:
                continue
            if not isinstance(sign, dict):
                sign = {}
            price_data.append(row)
            sign_data.append(sign)
            if pnl_value is not None:
                try:
                    total_pnl += float(pnl_value)
                    has_pnl = True
                except Exception:
                    pass
        return price_data, sign_data, total_pnl, has_pnl

    def load_watchlist(self) -> Tuple[List[str], List[str], dict, dict]:
        """返回 (codes, checked_codes, code_names, trade_points)。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT code, name, checked, buy_point, sell_point "
                "FROM watchlist ORDER BY sort_order ASC, code ASC"
            ).fetchall()

        codes, checked_codes, names, trade_points = [], [], {}, {}
        for code, name, checked, buy_point, sell_point in rows:
            key = _norm_code(code)
            if not key:
                continue
            codes.append(key)
            nm = str(name or "").strip()
            if nm:
                names[key] = nm
            if int(checked or 0):
                checked_codes.append(key)
            buy = _parse_point(buy_point)
            sell = _parse_point(sell_point)
            if buy is not None or sell is not None:
                trade_points[key] = {
                    "buy": buy if buy is not None else 0.0,
                    "sell": sell if sell is not None else 0.0,
                }
        return codes, checked_codes, names, trade_points

    def save_watchlist(
        self,
        codes: Sequence[Any],
        checked_codes: Sequence[Any],
        code_names: Optional[dict] = None,
        trade_points: Optional[dict] = None,
    ) -> None:
        """全量覆盖自选；checked_codes 标记浮窗勾选；trade_points 写入买卖点。"""
        name_map = code_names or {}
        points_map = trade_points or {}
        checked_set = {_norm_code(c) for c in (checked_codes or []) if _norm_code(c)}
        now_iso = _now().isoformat()
        rows, seen = [], set()
        for i, c in enumerate(codes or []):
            if isinstance(c, dict):
                key = _norm_code(c)
                nm = str(c.get("name", "") or "").strip()
            else:
                key = _norm_code(c)
                nm = ""
            if not key or key in seen:
                continue
            seen.add(key)
            name = nm or str(name_map.get(key) or "").strip()
            pt = points_map.get(key) or {}
            buy = _parse_point(pt.get("buy") if isinstance(pt, dict) else None)
            sell = _parse_point(pt.get("sell") if isinstance(pt, dict) else None)
            rows.append(
                (key, name, i, 1 if key in checked_set else 0, buy, sell, now_iso)
            )

        if not rows:
            rows = [("sh000001", "上证指数", 0, 1, None, None, now_iso)]

        with self._connect() as conn:
            conn.execute("DELETE FROM watchlist")
            conn.executemany(
                "INSERT INTO watchlist "
                "(code, name, sort_order, checked, buy_point, sell_point, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()


def init_db(db_path: str) -> QuoteDB:
    return QuoteDB(db_path)
