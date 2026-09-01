# -*- coding: utf-8 -*-
import urllib.parse
import urllib.request

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QLineEdit,
    QAbstractItemView,
)


def search_sina_suggest(keyword: str, limit: int = 20):
    """按关键字调用新浪联想接口，返回 [{"code","name","label"}, ...]。"""
    key = (keyword or "").strip()
    if not key:
        return []
    url = (
        "https://suggest3.sinajs.cn/suggest/"
        "type=11,12,13,14,15,21,22,23,24,25,26,31,32,33,41,42"
        f"&key={urllib.parse.quote(key)}&name=suggestdata_1"
    )
    req = urllib.request.Request(
        url,
        headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        data = resp.read().decode("gbk", errors="ignore")
    start = data.find('="')
    end = data.rfind('";')
    if start < 0 or end <= start:
        return []
    body = data[start + 2 : end]
    results = []
    seen = set()
    for item in body.split(";"):
        if not item.strip():
            continue
        parts = item.split(",")
        if len(parts) < 5:
            continue
        typ = (parts[1] or "").strip()
        raw_code = (parts[2] or "").strip()
        symbol = (parts[3] or "").strip()
        name = (parts[4] or parts[0] or "").strip()
        code = _suggest_item_to_code(typ, raw_code, symbol)
        if not code or code in seen:
            continue
        seen.add(code)
        results.append({
            "code": code,
            "name": name,
            "label": f"{code}  {name}" if name else code,
        })
        if len(results) >= limit:
            break
    return results


def _suggest_item_to_code(typ: str, code: str, symbol: str):
    """将新浪联想条目映射为本程序行情代码。"""
    typ = str(typ or "").strip()
    code = (code or "").strip()
    symbol = (symbol or "").strip()

    # A股 / ETF / 场内基金：优先带交易所前缀的 symbol
    if typ in {"11", "12", "13", "14", "15", "21", "22", "23", "24", "25", "26"}:
        if symbol.lower().startswith(("sh", "sz", "bj")):
            return symbol.lower()
        if code.isdigit() and len(code) == 6:
            if code[0] in "65" or code[:2] == "90":
                return "sh" + code
            if code[0] in "0321":
                return "sz" + code
            if code[0] in "84" or code[:2] == "92":
                return "bj" + code
        return (symbol or code).lower() or None

    # 港股
    if typ in {"31", "32", "33"}:
        digits = code if code.isdigit() else (symbol if symbol.isdigit() else "")
        if digits.isdigit():
            return "rt_hk" + digits.zfill(5)
        return None

    # 美股
    if typ in {"41", "42"}:
        c = (code or symbol).lower().lstrip(".")
        if not c or c.startswith("."):
            return None
        return "gb_" + c

    return None


class AddCodeDialog(QDialog):
    """添加自选：支持代码输入与按名称搜索。"""
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("添加自选")
        self.setModal(True)
        self.setFixedWidth(360)
        self.setMinimumHeight(320)

        self._selected_code = ""
        self._selected_name = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("代码 / 名称："))
        self.edit_code = QLineEdit()
        self.edit_code.setPlaceholderText("输入代码或名称，如 600519、茅台、AAPL")
        layout.addWidget(self.edit_code)

        self.list_suggest = QListWidget()
        self.list_suggest.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.list_suggest, 1)

        tip = QLabel("输入后自动搜索；也可直接输入代码后确定。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #888;")
        layout.addWidget(tip)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        for b in (self.btn_ok, self.btn_cancel):
            b.setFixedWidth(60)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(320)
        self._search_timer.timeout.connect(self._do_search)

        self.edit_code.textChanged.connect(self._on_text_changed)
        self.edit_code.returnPressed.connect(self._on_return)
        self.list_suggest.itemClicked.connect(self._on_item_clicked)
        self.list_suggest.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.btn_ok.clicked.connect(self._on_accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.edit_code.setFocus()

    def _on_text_changed(self, _text: str):
        # 手动改输入时清空已选联想项
        self._selected_code = ""
        self._selected_name = ""
        self._search_timer.start()

    def _do_search(self):
        key = self.edit_code.text().strip()
        self.list_suggest.clear()
        if not key:
            return
        try:
            items = search_sina_suggest(key)
        except Exception:
            items = []
        for it in items:
            row = QListWidgetItem(it["label"])
            row.setData(Qt.UserRole, it)
            self.list_suggest.addItem(row)
        if self.list_suggest.count() > 0:
            self.list_suggest.setCurrentRow(0)

    def _apply_item(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole) or {}
        code = str(data.get("code", "") or "").strip()
        name = str(data.get("name", "") or "").strip()
        if not code:
            return
        self._selected_code = code
        self._selected_name = name
        self.edit_code.blockSignals(True)
        self.edit_code.setText(f"{code}  {name}" if name else code)
        self.edit_code.blockSignals(False)

    def _on_item_clicked(self, item: QListWidgetItem):
        self._apply_item(item)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._apply_item(item)
        self._on_accept()

    def _on_return(self):
        # 有高亮联想项时优先采用
        item = self.list_suggest.currentItem()
        if item is not None and self.list_suggest.count() > 0:
            self._apply_item(item)
        self._on_accept()

    def _on_accept(self):
        code, _name = self.get_result()
        if not code:
            return
        self.accept()

    def get_result(self):
        """返回 (code, name)。优先使用已选联想项。"""
        if self._selected_code:
            return self._selected_code, self._selected_name
        text = (self.edit_code.text() or "").strip()
        if not text:
            return "", ""
        # 兼容「代码  名称」展示文本
        code = text.split()[0] if text.split() else text
        return code, ""

    def get_code(self) -> str:
        code, _name = self.get_result()
        return code


class CostDialog(QDialog):
    """设置持仓成本与数量的对话框。"""
    def __init__(self, parent: QWidget, code: str, cost: float = 0.0, qty: int = 0):
        super().__init__(parent)
        self.setWindowTitle(f"设置成本 - {code}")
        self.setModal(True)
        self.setFixedWidth(260)

        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        layout.addWidget(QLabel("成本价："), 0, 0)
        self.edit_cost = QLineEdit(f"{cost:g}" if cost and cost > 0 else "")
        self.edit_cost.setPlaceholderText("例如 12.345")
        cost_v = QDoubleValidator(0.0, 1e9, 4, self)
        cost_v.setNotation(QDoubleValidator.StandardNotation)
        self.edit_cost.setValidator(cost_v)
        layout.addWidget(self.edit_cost, 0, 1)

        layout.addWidget(QLabel("持仓数量："), 1, 0)
        self.edit_qty = QLineEdit(str(qty) if qty else "")
        self.edit_qty.setPlaceholderText("股数，可为负")
        self.edit_qty.setValidator(QIntValidator(-10**9, 10**9, self))
        layout.addWidget(self.edit_qty, 1, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_clear = QPushButton("清除")
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        for b in (self.btn_clear, self.btn_ok, self.btn_cancel):
            b.setFixedWidth(60)
            btn_row.addWidget(b)
        layout.addLayout(btn_row, 2, 0, 1, 2)

        self._cleared = False
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_clear.clicked.connect(self._on_clear)

    def _on_clear(self):
        self._cleared = True
        self.accept()

    def get_values(self):
        """返回 (cost, qty)。清除时返回 (0.0, 0)。"""
        if self._cleared:
            return 0.0, 0
        try:
            cost = float(self.edit_cost.text().strip() or 0)
        except Exception:
            cost = 0.0
        try:
            qty = int(self.edit_qty.text().strip() or 0)
        except Exception:
            qty = 0
        return cost, qty


class BuySellDialog(QDialog):
    """设置买入点 / 卖出点的对话框。"""
    def __init__(self, parent: QWidget, code: str, buy: float = 0.0, sell: float = 0.0):
        super().__init__(parent)
        self.setWindowTitle(f"编辑买卖点 - {code}")
        self.setModal(True)
        self.setFixedWidth(260)

        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        layout.addWidget(QLabel("买入点："), 0, 0)
        self.edit_buy = QLineEdit(f"{buy:g}" if buy and buy > 0 else "")
        self.edit_buy.setPlaceholderText("例如 12.345")
        buy_v = QDoubleValidator(0.0, 1e9, 4, self)
        buy_v.setNotation(QDoubleValidator.StandardNotation)
        self.edit_buy.setValidator(buy_v)
        layout.addWidget(self.edit_buy, 0, 1)

        layout.addWidget(QLabel("卖出点："), 1, 0)
        self.edit_sell = QLineEdit(f"{sell:g}" if sell and sell > 0 else "")
        self.edit_sell.setPlaceholderText("例如 15.678")
        sell_v = QDoubleValidator(0.0, 1e9, 4, self)
        sell_v.setNotation(QDoubleValidator.StandardNotation)
        self.edit_sell.setValidator(sell_v)
        layout.addWidget(self.edit_sell, 1, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_clear = QPushButton("清除")
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        for b in (self.btn_clear, self.btn_ok, self.btn_cancel):
            b.setFixedWidth(60)
            btn_row.addWidget(b)
        layout.addLayout(btn_row, 2, 0, 1, 2)

        self._cleared = False
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_clear.clicked.connect(self._on_clear)

    def _on_clear(self):
        self._cleared = True
        self.accept()

    def get_values(self):
        """返回 (buy, sell)。清除时返回 (0.0, 0.0)。"""
        if self._cleared:
            return 0.0, 0.0
        try:
            buy = float(self.edit_buy.text().strip() or 0)
        except Exception:
            buy = 0.0
        try:
            sell = float(self.edit_sell.text().strip() or 0)
        except Exception:
            sell = 0.0
        return buy, sell


class AlertDialog(QDialog):
    """设置封单预警阈值的对话框。可添加多个阈值：正=涨停封单手数，负=跌停封单手数。"""
    def __init__(self, parent: QWidget, code: str, thresholds: list = None):
        super().__init__(parent)
        self.setWindowTitle(f"封单预警 - {code}")
        self.setModal(True)
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        tip = QLabel("正值=涨停封单（手），负值=跌停封单（手）。\n"
                     "进入涨/跌停且封单达阈值时生效；\n"
                     "封单跌破阈值或打开涨/跌停时通知并失效。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #888;")
        layout.addWidget(tip)

        self.list_thresholds = QListWidget()
        self.list_thresholds.setFixedHeight(120)
        for t in (thresholds or []):
            try:
                self._add_item(int(t))
            except Exception:
                pass
        layout.addWidget(self.list_thresholds)

        add_row = QHBoxLayout()
        self.edit_value = QLineEdit()
        self.edit_value.setPlaceholderText("手数：正=涨停，负=跌停")
        self.edit_value.setValidator(QIntValidator(-10**8, 10**8, self))
        self.btn_add_alert = QPushButton("添加")
        self.btn_add_alert.setFixedWidth(60)
        self.btn_remove_alert = QPushButton("删除")
        self.btn_remove_alert.setFixedWidth(60)
        add_row.addWidget(self.edit_value, 1)
        add_row.addWidget(self.btn_add_alert)
        add_row.addWidget(self.btn_remove_alert)
        layout.addLayout(add_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_clear_all = QPushButton("清除全部")
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        for b in (self.btn_clear_all, self.btn_ok, self.btn_cancel):
            b.setFixedWidth(70)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.btn_add_alert.clicked.connect(self._on_add)
        self.edit_value.returnPressed.connect(self._on_add)
        self.btn_remove_alert.clicked.connect(self._on_remove)
        self.btn_clear_all.clicked.connect(self.list_thresholds.clear)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _add_item(self, n: int):
        if n == 0:
            return
        for i in range(self.list_thresholds.count()):
            try:
                if int(self.list_thresholds.item(i).data(Qt.UserRole)) == n:
                    return
            except Exception:
                pass
        label = f"{n:+d} 手 ({'涨停' if n > 0 else '跌停'})"
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, n)
        self.list_thresholds.addItem(item)

    def _on_add(self):
        try:
            txt = self.edit_value.text().strip()
            if not txt:
                return
            n = int(txt)
            self._add_item(n)
            self.edit_value.clear()
        except Exception:
            pass

    def _on_remove(self):
        row = self.list_thresholds.currentRow()
        if row >= 0:
            self.list_thresholds.takeItem(row)

    def get_thresholds(self):
        result = []
        for i in range(self.list_thresholds.count()):
            try:
                n = int(self.list_thresholds.item(i).data(Qt.UserRole))
                if n != 0:
                    result.append(n)
            except Exception:
                pass
        return result
