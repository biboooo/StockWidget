# -*- coding: utf-8 -*-
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem, QMenu,
    QSizePolicy, QMessageBox,
)

from settings.dialogs import AddCodeDialog, CostDialog, AlertDialog, BuySellDialog


class CodesTabMixin:
    """设置对话框「自选列表」页的混入类。"""

    def _build_tab_codes(self):
        """构建自选列表页：代码表 + 添加/删除/上下移/成本/预警按钮。"""
        # ---- 第一页 ----
        tab_0 = QWidget()
        code_settings = QVBoxLayout(tab_0)

        # 1.自选列表
        g_codes = QGroupBox("自选列表")
        # 【修改点1】：确保外层布局允许控件填充
        g_codes.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        g_codes.setContentsMargins(3,25,3,6)
        lay_codes = QHBoxLayout(g_codes)
        lay_codes.setSpacing(6)
        # 1.1 代码列表（代码 + 名称 + 买入点 + 卖出点）
        self.list_codes = QTableWidget(0, 4)
        self.list_codes.setHorizontalHeaderLabels(["代码", "名称", "买入点", "卖出点"])
        self.list_codes.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.list_codes.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.list_codes.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.list_codes.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.list_codes.verticalHeader().setVisible(False)
        self.list_codes.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_codes.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_codes.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed)
        self.list_codes.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        for c in self.win.codes:
            self._append_code_row(
                c,
                checked=(c in getattr(self.win, 'checked_codes', [])),
            )
        # 1.2 操作按钮
        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)
        self.btn_add = QPushButton("添加")
        self.btn_add.setFixedWidth(60)
        self.btn_del = QPushButton("删除")
        self.btn_del.setFixedWidth(60)
        self.btn_up  = QPushButton("上移")
        self.btn_up.setFixedWidth(60)
        self.btn_dn  = QPushButton("下移")
        self.btn_dn.setFixedWidth(60)
        self.btn_cost = QPushButton("设置成本")
        self.btn_cost.setFixedWidth(60)
        self.btn_cost.setEnabled(False)
        self.btn_edit_points = QPushButton("编辑")
        self.btn_edit_points.setFixedWidth(60)
        self.btn_edit_points.setEnabled(False)
        self.btn_alert = QPushButton("封单预警")
        self.btn_alert.setFixedWidth(60)
        self.btn_alert.setEnabled(False)
        for b in (self.btn_add, self.btn_del, self.btn_up, self.btn_dn,
                  self.btn_cost, self.btn_edit_points, self.btn_alert):
            btn_col.addWidget(b)
        btn_col.addStretch(1)

        lay_codes.addWidget(self.list_codes)
        lay_codes.addLayout(btn_col)
        code_settings.addWidget(g_codes, 1)

        return tab_0

    _re_full = re.compile(r'^(sh|sz|bj)\d+$')
    _re_6 = re.compile(r'^\d{6}$')
    # 匹配期货代码的正则 (nf_ 或 hf_ 开头，后面跟字母和数字)
    _re_futures = re.compile(r'^(nf|hf)_[a-zA-Z0-9]+$', re.IGNORECASE)

    def _normalize_code_or_none(self, s: str):
        """将用户输入规范为行情代码；无法识别时返回 None。"""
        original_s = (s or "").strip()
        if not original_s: 
            return None

        lower_s = original_s.lower()

        # ==========================================
        # 绝招一：【绝对绿灯直通车】——真正的“一劳永逸”！
        # 如果你未来想看阿根廷指数，但代码里没写，
        # 你只要在软件输入框里直接敲 `b_MERV`，它就会直接放行发给新浪，无需任何代码修改！
        # ==========================================
        if lower_s.startswith(('nf_', 'hf_', 'b_', 'gb_', 'fx_', 'rt_hk', 'hk')):
            if lower_s.startswith(('fx_', 'rt_hk', 'hk')):
                return lower_s.replace('fx_s_', 'fx_s') # 兼容外汇旧错码
                
            parts = original_s.split('_', 1)
            if len(parts) == 2:
                prefix = parts[0].lower()
                code = parts[1]
                if prefix in ['nf', 'hf', 'b']:
                    return f"{prefix}_{code.upper()}"
                elif prefix == 'gb':
                    return f"{prefix}_{code.lower()}"
            return original_s

        # ==========================================
        # 绝招二：【品类大词典】——告别无数个 elif
        # ==========================================
        test_s = original_s.upper()

        # 1. 港股 (5位纯数字，如 01810)
        if re.match(r'^\d{5}$', test_s):
            return f"rt_hk{test_s}"

        # 2. 全球指数大词典 (涵盖全球核心股市)
        test_s = original_s.upper()

        # 1. 港股 (5位纯数字，如 01810)
        if re.match(r'^\d{5}$', test_s):
            return f"rt_hk{test_s}"

        # 2. 全球其他指数大词典 (【修改】：移出了美股三大指数)
        INDEX_DICT = {
            # 亚洲
            "NKY", "N225", "N255", "KS11", "KOSPI", "TWII", 
            # 美洲 (巴西)
            "IBOV",
            # 欧洲
            "UKX", "CAC", "DAX", "MICEX", "RTS", 
            # 东南亚/印度/澳洲
            "SENSEX", "NIFTY", "STI", "KLSE", "SETI", "AS51", "NZ50" 
        }
        if test_s in INDEX_DICT:
            if test_s in ["N225", "N255"]: test_s = "NKY"
            elif test_s == "KOSPI": test_s = "KS11"
            return f"b_{test_s}"

        # 3. 【新增】：美股三大指数特供通道 (走 gb_ 美股接口)
        if test_s in {"DJI", "IXIC", "INX", "SPX"}:
            if test_s == "SPX": test_s = "INX" # 标普500 新浪只认 INX
            return f"gb_{test_s.lower()}"

        # 4. 外盘期货/现货
        if test_s in {"XAU", "XAG", "OIL", "CL", "GC", "SI"}:
            return f"hf_{test_s}"

        # 5. 外汇对
        if test_s in {"USDJPY", "EURUSD", "GBPUSD", "USDCNY", "USDCNH", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"}:
            return f"fx_s{test_s.lower()}"

        # 6. 国内期货 (智能正则：1~3个字母 + 数字，且排除A股前缀)
        if re.match(r'^[A-Z]{1,3}\d{1,4}$', test_s) and not test_s.startswith(('SH', 'SZ', 'BJ')):
            return f"nf_{original_s.upper()}"

        # 7. 纯字母默认当做美股处理 (如 AAPL)
        if test_s.isalpha():
            return f"gb_{original_s.lower()}"

        # ==========================================
        # 兜底：原作者的 A 股 / ETF 识别逻辑
        # ==========================================
        s = lower_s
        s = re.sub(r'[^a-z0-9]', '', s)  
        if not s: return None
        if getattr(self, '_re_full', None) and self._re_full.match(s): return s
        if getattr(self, '_re_6', None) and self._re_6.match(s):
            if s[0] == '6' or s[0:2] == '90' or s[0] == '5':
                return 'sh' + s
            elif s[0] == '0' or s[0] == '3' or s[0] == '2' or s[0] == '1':
                return 'sz' + s
            elif s[0] == '8' or s[0] == '4' or s[0:2] == '92':
                return 'bj' + s
                
        return None

    def _append_code_row(self, code: str, checked: bool = False, name: str = None):
        """向自选表追加一行：代码(可勾选/可编辑) + 名称/买卖点(只读)。"""
        row = self.list_codes.rowCount()
        self.list_codes.insertRow(row)

        code_it = QTableWidgetItem(code)
        code_it.setFlags(
            Qt.ItemIsUserCheckable | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled
        )
        code_it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        code_it.setData(Qt.UserRole, code)

        if name is None:
            name = ""
            if hasattr(self.win, "get_code_name"):
                name = self.win.get_code_name(code) or ""
        name_it = QTableWidgetItem(name or "")
        name_it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        buy_txt, sell_txt = "", ""
        if hasattr(self.win, "get_trade_points"):
            pt = self.win.get_trade_points(code) or {}
            buy = float(pt.get("buy", 0) or 0)
            sell = float(pt.get("sell", 0) or 0)
            if buy > 0:
                buy_txt = f"{buy:g}"
            if sell > 0:
                sell_txt = f"{sell:g}"
        buy_it = QTableWidgetItem(buy_txt)
        buy_it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        sell_it = QTableWidgetItem(sell_txt)
        sell_it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        self.list_codes.blockSignals(True)
        self.list_codes.setItem(row, 0, code_it)
        self.list_codes.setItem(row, 1, name_it)
        self.list_codes.setItem(row, 2, buy_it)
        self.list_codes.setItem(row, 3, sell_it)
        self.list_codes.blockSignals(False)
        return code_it

    def _save_code_name(self, code: str, name: str):
        """把名称写入主窗口缓存（配置在后续 _notify_change 时一并保存）。"""
        if not code or not name:
            return
        if not hasattr(self.win, "code_names") or self.win.code_names is None:
            self.win.code_names = {}
        self.win.code_names[code] = name
        self.win.code_names[code.lower()] = name

    def _sync_row_name_from_config(self, row: int):
        """按配置刷新指定行的名称列。"""
        code_it = self.list_codes.item(row, 0)
        if code_it is None:
            return
        code = code_it.data(Qt.UserRole) or self._normalize_code_or_none(code_it.text()) or code_it.text().strip()
        name = ""
        if code and hasattr(self.win, "get_code_name"):
            name = self.win.get_code_name(code) or ""
        name_it = self.list_codes.item(row, 1)
        if name_it is None:
            name_it = QTableWidgetItem("")
            name_it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.list_codes.setItem(row, 1, name_it)
        self.list_codes.blockSignals(True)
        name_it.setText(name)
        self.list_codes.blockSignals(False)

    def _sync_row_points_from_config(self, row: int):
        """按配置刷新指定行的买入点/卖出点列。"""
        code_it = self.list_codes.item(row, 0)
        if code_it is None:
            return
        code = code_it.data(Qt.UserRole) or self._normalize_code_or_none(code_it.text()) or code_it.text().strip()
        buy_txt, sell_txt = "", ""
        if code and hasattr(self.win, "get_trade_points"):
            pt = self.win.get_trade_points(code) or {}
            buy = float(pt.get("buy", 0) or 0)
            sell = float(pt.get("sell", 0) or 0)
            if buy > 0:
                buy_txt = f"{buy:g}"
            if sell > 0:
                sell_txt = f"{sell:g}"
        for col, text in ((2, buy_txt), (3, sell_txt)):
            it = self.list_codes.item(row, col)
            if it is None:
                it = QTableWidgetItem("")
                it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.list_codes.setItem(row, col, it)
            self.list_codes.blockSignals(True)
            it.setText(text)
            self.list_codes.blockSignals(False)

    def _collect_codes_from_list(self):
        """遍历自选表，规范化代码并去重；无效行回退或删除，返回有效代码列表。"""
        codes = []
        seen = set()
        i = 0
        while i < self.list_codes.rowCount():
            it = self.list_codes.item(i, 0)
            if it is None:
                self.list_codes.removeRow(i)
                continue
            txt = it.text()
            norm = self._normalize_code_or_none(txt)
            if norm:
                if norm not in seen:
                    seen.add(norm)
                    codes.append(norm)
                # 写回规范化文本
                if it.text() != norm:
                    self.list_codes.blockSignals(True)
                    it.setText(norm)
                    it.setData(Qt.UserRole, norm)
                    self.list_codes.blockSignals(False)
                else:
                    it.setData(Qt.UserRole, norm)
                i += 1
            else:
                # 回退到上次有效值
                prev = it.data(Qt.UserRole)
                if prev:
                    self.list_codes.blockSignals(True)
                    it.setText(prev)
                    self.list_codes.blockSignals(False)
                    i += 1
                else:
                    self.list_codes.removeRow(i)
        return codes

    def _on_codes_changed(self, _item):
        """自选表变更：回写 codes/checked_codes；代码列变更时同步名称。"""
        # 名称/买卖点列只读，不回写配置
        if _item is not None and self.list_codes.column(_item) in (1, 2, 3):
            return

        codes = self._collect_codes_from_list()
        checked_codes = []
        for i in range(self.list_codes.rowCount()):
            it = self.list_codes.item(i, 0)
            if it is None or it.checkState() != Qt.Checked:
                continue
            txt = (it.text() or "").strip()
            if txt:
                checked_codes.append(txt.split()[0])
        # 合并写盘/拉行情，避免 set_codes + set_checked_codes 各刷新一次
        codes_changed = self.win.set_codes(codes, notify=False, refresh=False)
        checked_changed = self.win.set_checked_codes(checked_codes, notify=False, refresh=False)
        if codes_changed or checked_changed:
            self.win._notify_change()
            self.win._refresh_from_function()

        if _item is not None and self.list_codes.column(_item) == 0:
            self._sync_row_name_from_config(self.list_codes.row(_item))
            self._sync_row_points_from_config(self.list_codes.row(_item))

    def _add_code(self):
        """弹窗搜索/输入代码，确认后追加到自选列表并保存名称。"""
        dlg = AddCodeDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        raw, name = dlg.get_result()
        if not raw:
            return
        code = self._normalize_code_or_none(raw) or (
            raw.lower() if raw.lower().startswith(("sh", "sz", "bj", "gb_", "rt_hk", "nf_", "hf_", "b_", "fx_")) else None
        )
        if not code:
            QMessageBox.warning(self, "添加自选", "无法识别该代码，请检查输入或从搜索结果中选择。")
            return
        # 已存在则选中该行；有名称则更新并写配置
        for i in range(self.list_codes.rowCount()):
            it = self.list_codes.item(i, 0)
            if it is None:
                continue
            existing = it.data(Qt.UserRole) or self._normalize_code_or_none(it.text()) or ""
            if existing == code:
                if name:
                    self._save_code_name(code, name)
                    name_it = self.list_codes.item(i, 1)
                    if name_it is None:
                        name_it = QTableWidgetItem("")
                        name_it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                        self.list_codes.setItem(i, 1, name_it)
                    self.list_codes.blockSignals(True)
                    name_it.setText(name)
                    self.list_codes.blockSignals(False)
                    self.win._notify_change()
                self.list_codes.setCurrentCell(i, 0)
                return
        if name:
            self._save_code_name(code, name)
        it = self._append_code_row(code, checked=False, name=name or None)
        self.list_codes.setCurrentItem(it)
        self._on_codes_changed(it)

    def _del_code(self):
        """删除当前选中行并回写配置。"""
        row = self.list_codes.currentRow()
        if row >= 0:
            self.list_codes.removeRow(row)
            self._on_codes_changed(None)

    def _swap_table_rows(self, r1: int, r2: int):
        """交换自选表两行的全部单元格。"""
        cols = self.list_codes.columnCount()
        for col in range(cols):
            a = self.list_codes.takeItem(r1, col)
            b = self.list_codes.takeItem(r2, col)
            self.list_codes.setItem(r1, col, b)
            self.list_codes.setItem(r2, col, a)

    def _move_up(self):
        """将当前行上移一行。"""
        row = self.list_codes.currentRow()
        if row > 0:
            self.list_codes.blockSignals(True)
            self._swap_table_rows(row, row - 1)
            self.list_codes.blockSignals(False)
            self.list_codes.setCurrentCell(row - 1, 0)
            self._on_codes_changed(None)

    def _move_down(self):
        """将当前行下移一行。"""
        row = self.list_codes.currentRow()
        if 0 <= row < self.list_codes.rowCount() - 1:
            self.list_codes.blockSignals(True)
            self._swap_table_rows(row, row + 1)
            self.list_codes.blockSignals(False)
            self.list_codes.setCurrentCell(row + 1, 0)
            self._on_codes_changed(None)

    def _on_list_selection_changed(self):
        """有选中行时才启用「设置成本」「编辑」「封单预警」。"""
        has = self.list_codes.currentRow() >= 0
        self.btn_cost.setEnabled(has)
        self.btn_edit_points.setEnabled(has)
        self.btn_alert.setEnabled(has)

    def _on_list_context_menu(self, pos):
        """右键菜单：设置成本 / 编辑买卖点 / 封单预警。"""
        item = self.list_codes.itemAt(pos)
        if item is None:
            return
        row = self.list_codes.row(item)
        code_item = self.list_codes.item(row, 0)
        if code_item is None:
            return
        self.list_codes.setCurrentItem(code_item)
        menu = QMenu(self.list_codes)
        act = QAction("设置成本…", menu)
        act.triggered.connect(lambda: self._open_cost_dialog_for_item(code_item))
        menu.addAction(act)
        act_points = QAction("编辑买卖点…", menu)
        act_points.triggered.connect(lambda: self._open_points_dialog_for_item(code_item))
        menu.addAction(act_points)
        act_alert = QAction("封单预警…", menu)
        act_alert.triggered.connect(lambda: self._open_alert_dialog_for_item(code_item))
        menu.addAction(act_alert)
        menu.exec(self.list_codes.viewport().mapToGlobal(pos))

    def _open_cost_dialog_for_current(self):
        """为当前选中代码打开成本设置对话框。"""
        row = self.list_codes.currentRow()
        item = self.list_codes.item(row, 0) if row >= 0 else None
        if item is not None:
            self._open_cost_dialog_for_item(item)

    def _open_cost_dialog_for_item(self, item: QTableWidgetItem):
        """打开指定代码的成本设置对话框并写回。"""
        raw = item.text().strip()
        code = self._normalize_code_or_none(raw) or raw.lower()
        if not code:
            return
        existing = {}
        try:
            existing = self.win.get_cost(code) or {}
        except Exception:
            existing = {}
        dlg = CostDialog(self, code,
                         float(existing.get("cost", 0.0) or 0.0),
                         int(existing.get("qty", 0) or 0))
        if dlg.exec() == QDialog.Accepted:
            cost, qty = dlg.get_values()
            try:
                self.win.set_cost(code, cost, qty)
            except Exception:
                pass

    def _open_points_dialog_for_current(self):
        """为当前选中代码打开买卖点编辑对话框。"""
        row = self.list_codes.currentRow()
        item = self.list_codes.item(row, 0) if row >= 0 else None
        if item is not None:
            self._open_points_dialog_for_item(item)

    def _open_points_dialog_for_item(self, item: QTableWidgetItem):
        """打开指定代码的买卖点对话框并写回。"""
        raw = item.text().strip()
        code = self._normalize_code_or_none(raw) or raw.lower()
        if not code:
            return
        existing = {}
        try:
            existing = self.win.get_trade_points(code) or {}
        except Exception:
            existing = {}
        dlg = BuySellDialog(
            self,
            code,
            float(existing.get("buy", 0.0) or 0.0),
            float(existing.get("sell", 0.0) or 0.0),
        )
        if dlg.exec() == QDialog.Accepted:
            buy, sell = dlg.get_values()
            try:
                self.win.set_trade_points(code, buy, sell)
            except Exception:
                pass
            row = self.list_codes.row(item)
            if row >= 0:
                self._sync_row_points_from_config(row)

    def _open_alert_dialog_for_current(self):
        """为当前选中代码打开封单预警对话框。"""
        row = self.list_codes.currentRow()
        item = self.list_codes.item(row, 0) if row >= 0 else None
        if item is not None:
            self._open_alert_dialog_for_item(item)

    def _open_alert_dialog_for_item(self, item: QTableWidgetItem):
        """打开指定代码的封单预警对话框并写回。"""
        raw = item.text().strip()
        code = self._normalize_code_or_none(raw) or raw.lower()
        if not code:
            return
        existing = []
        try:
            existing = self.win.get_alert(code) or []
        except Exception:
            existing = []
        dlg = AlertDialog(self, code, existing)
        if dlg.exec() == QDialog.Accepted:
            try:
                self.win.set_alert(code, dlg.get_thresholds())
            except Exception:
                pass
