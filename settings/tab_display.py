# -*- coding: utf-8 -*-
from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QComboBox,
    QCheckBox, QLineEdit,
)

class DisplayTabMixin:
    def _build_tab_display(self):
        """显示数据页。"""
        # ---- 第二页 ----
        tab_1 = QWidget()
        data_settings = QVBoxLayout(tab_1)

        # 2.刷新间隔
        g_interval = QGroupBox("刷新间隔")
        g_interval.setContentsMargins(3,12,3,6)
        self.cmb_interval = QComboBox()
        self.cmb_interval.setFixedWidth(136)
        for s in [1,2,3,5,10,15,30,60]:
            self.cmb_interval.addItem(f"{s} 秒", userData=s)
        idx = self.cmb_interval.findData(self.win.refresh_seconds)
        self.cmb_interval.setCurrentIndex(idx if idx >= 0 else 1)
        v = QVBoxLayout(g_interval)
        v.setContentsMargins(6,6,6,6)
        v.addWidget(self.cmb_interval)
        data_settings.addWidget(g_interval)

        # 3.显示选项
        # 3.0 双模式切换开关
        g_dual_mode = QGroupBox("双模式切换")
        g_dual_mode.setContentsMargins(3,12,3,6)
        gl_dual_mode = QGridLayout(g_dual_mode)
        gl_dual_mode.setHorizontalSpacing(6)
        gl_dual_mode.setVerticalSpacing(6)
        self.chk_dual_mode = QCheckBox("启用模式切换（悬浮显示正常模式，离开显示简易模式）")
        self.chk_dual_mode.setChecked(bool(self.win.dual_mode_enabled))
        gl_dual_mode.addWidget(self.chk_dual_mode, 0, 0, 1, 3)
        # 延迟设置
        gl_dual_mode.addWidget(QLabel("切换延迟："), 1, 0)
        self.cmb_leave_delay = QComboBox()
        self.cmb_leave_delay.setFixedWidth(100)
        for ms, label in [(0, "无延迟"), (200, "0.2 秒"), (500, "0.5 秒"), (1000, "1 秒"), (2000, "2 秒"), (3000, "3 秒")]:
            self.cmb_leave_delay.addItem(label, userData=ms)
        idx_delay = self.cmb_leave_delay.findData(self.win.leave_delay_ms)
        if idx_delay < 0:
            idx_delay = self.cmb_leave_delay.findData(500)
        self.cmb_leave_delay.setCurrentIndex(idx_delay if idx_delay >= 0 else 2)
        self.cmb_leave_delay.setEnabled(bool(self.win.dual_mode_enabled))
        gl_dual_mode.addWidget(self.cmb_leave_delay, 1, 1)
        data_settings.addWidget(g_dual_mode)

        # 3.1复选框组 - 正常模式
        g_flags = QGroupBox("正常模式指标")
        g_flags.setContentsMargins(3,12,3,6)
        gl_flags = QGridLayout(g_flags)
        gl_flags.setHorizontalSpacing(8)
        gl_flags.setVerticalSpacing(6)
        self.cbs: list[QCheckBox] = []
        cb_texts = self.win.ALL_HEADERS

        g_flag_name = QGroupBox("名称")
        gl_flag_name = QGridLayout(g_flag_name)
        gl_flag_name.setHorizontalSpacing(6)
        gl_flag_name.setVerticalSpacing(6)
        # 代码、名称
        for i, h in enumerate(cb_texts[0:2]):
            cb = QCheckBox(h)
            cb.setChecked(self.win.header_is_visible(h))
            cb.stateChanged.connect(partial(self._on_cb_changed, h))
            self.cbs.append(cb)
            gl_flag_name.addWidget(cb, i, 0)
        self.cb_short_code = QCheckBox("仅显示数字")
        self.cb_short_code.setChecked(bool(self.win.short_code))
        self.cb_short_code.setEnabled(self.win.header_is_visible("代码"))
        gl_flag_name.addWidget(self.cb_short_code, 0, 1)
        self.cmb_namelength = QComboBox()
        self.cmb_namelength.setFixedWidth(80)
        for l in [0, 1, 2, 3, 4]:
            self.cmb_namelength.addItem(f"{l}个字" if l>0 else "完整", userData=l)
        idx_name = self.cmb_namelength.findData(self.win.name_length)
        self.cmb_namelength.setCurrentIndex(idx_name if idx_name>=0 else 1)
        self.cmb_namelength.setEnabled(self.win.header_is_visible("名称"))
        gl_flag_name.addWidget(self.cmb_namelength, 1, 1)
        gl_flags.addWidget(g_flag_name, 0, 0)

        g_flag_price = QGroupBox("价格")
        gl_flag_price = QGridLayout(g_flag_price)
        gl_flag_price.setHorizontalSpacing(6)
        gl_flag_price.setVerticalSpacing(6)
        # 现价、涨跌值、涨跌幅、盈亏 — 2×2 网格布局
        for i, h in enumerate(cb_texts[2:6]):
            cb = QCheckBox(h)
            cb.setChecked(self.win.header_is_visible(h))
            cb.stateChanged.connect(partial(self._on_cb_changed, h))
            self.cbs.append(cb)
            gl_flag_price.addWidget(cb, i // 2, i % 2)
        gl_flags.addWidget(g_flag_price, 1, 0)

        g_flag_order = QGroupBox("盘口")
        gl_flag_order = QGridLayout(g_flag_order)
        gl_flag_order.setHorizontalSpacing(6)
        gl_flag_order.setVerticalSpacing(6)
        # 买一/卖一
        self.cb_b1s1 = QCheckBox("买一/卖一")
        self.cb_b1s1.setChecked(self.win.b1s1_visible)
        self.cb_b1s1.stateChanged.connect(self._on_b1s1_toggled)
        self.cbs.append(self.cb_b1s1)
        gl_flag_order.addWidget(self.cb_b1s1, 0, 0)
        
        # 委比
        cb_commi = QCheckBox("委比")
        cb_commi.setChecked(self.win.header_is_visible("委比"))
        cb_commi.stateChanged.connect(partial(self._on_cb_changed, "委比"))
        self.cbs.append(cb_commi)
        gl_flag_order.addWidget(cb_commi, 1, 0)
        
        # 买一/卖一显示模式：数量 / 价格 / 数量和价格
        self.cmb_b1s1_display = QComboBox()
        self.cmb_b1s1_display.setFixedWidth(150)
        self.cmb_b1s1_display.addItem("数量", userData="qty")
        self.cmb_b1s1_display.addItem("价格", userData="price")
        self.cmb_b1s1_display.addItem("数量和价格", userData="both")
        cur_mode = getattr(self.win, 'b1s1_display', 'qty')
        idx_mode = self.cmb_b1s1_display.findData(cur_mode)
        self.cmb_b1s1_display.setCurrentIndex(idx_mode if idx_mode>=0 else 0)
        self.cmb_b1s1_display.setEnabled(self.win.b1s1_visible)
        gl_flag_order.addWidget(self.cmb_b1s1_display, 0, 1)
        gl_flags.addWidget(g_flag_order, 0, 1)

        g_flag_deal = QGroupBox("成交")
        gl_flag_deal = QGridLayout(g_flag_deal)
        
        # 1. 稍微放宽四周的边距 (左, 上, 右, 下)，给 GroupBox 的标题留出空间
        gl_flag_deal.setContentsMargins(10, 15, 10, 10) 
        gl_flag_deal.setHorizontalSpacing(10)
        gl_flag_deal.setVerticalSpacing(8)
        
        for i, idx in enumerate(range(9,14)):
            cb = QCheckBox(cb_texts[idx])
            
            # 【核心修复 1】：强制给 CheckBox 设置一个最小高度，防止文字被上下裁切
            cb.setMinimumHeight(22) 
            
            cb.setChecked(self.win.header_is_visible(cb_texts[idx]))
            cb.stateChanged.connect(partial(self._on_cb_changed, cb_texts[idx]))
            self.cbs.append(cb)
            
            # 【核心修复 2】：使用 Qt.AlignTop，让复选框在自己的网格里靠上对齐，不要被强行拉伸
            gl_flag_deal.addWidget(cb, i // 2, i % 2, alignment=Qt.AlignTop)
            
        # 【核心修复 3】：在网格的最下面（第 3 行，因为上面是 0, 1, 2 行）加一个垂直弹簧。
        # 这样当外层窗口缩放时，这个弹簧会吸收多余的形变，复选框就不会被挤压了。
        gl_flag_deal.setRowStretch(3, 1)

        gl_flags.addWidget(g_flag_deal, 1, 1)

        g_flag_other = QGroupBox("其他")
        gl_flag_other = QGridLayout(g_flag_other)
        gl_flag_other.setHorizontalSpacing(6)
        gl_flag_other.setVerticalSpacing(6)
        for i in range(14,15):
            cb = QCheckBox(cb_texts[i])
            cb.setChecked(self.win.header_is_visible(cb_texts[i]))
            cb.stateChanged.connect(partial(self._on_cb_changed, cb_texts[i]))
            self.cbs.append(cb)
            gl_flag_other.addWidget(cb, i-14, 0)
        gl_flags.addWidget(g_flag_other, 2, 0)

        data_settings.addWidget(g_flags)

        # 3.2 简易模式指标复选框组
        g_simple_flags = QGroupBox("简易模式指标")
        g_simple_flags.setContentsMargins(3,12,3,6)
        gl_simple = QGridLayout(g_simple_flags)
        gl_simple.setHorizontalSpacing(6)
        gl_simple.setVerticalSpacing(6)
        self.simple_cbs: list[QCheckBox] = []
        simple_headers = ["代码", "名称", "现价", "涨跌值", "涨跌幅", "盈亏", "买一/卖一", "委比", "成交量", "成交额", "均价", "日高", "日低", "K线"]
        simple_header_keys = ["代码", "名称", "现价", "涨跌值", "涨跌幅", "盈亏", "买一", "委比", "成交量", "成交额", "均价", "日高", "日低", "K线"]
        for i, (label, key) in enumerate(zip(simple_headers, simple_header_keys)):
            cb = QCheckBox(label)
            cb.setChecked(self.win.simple_header_is_visible(key))
            cb.stateChanged.connect(partial(self._on_simple_cb_changed, key))
            self.simple_cbs.append(cb)
            gl_simple.addWidget(cb, i // 4, i % 4)
        # 简易模式指标组仅在双模式启用时可编辑
        g_simple_flags.setEnabled(bool(self.win.dual_mode_enabled))
        self._g_simple_flags = g_simple_flags
        data_settings.addWidget(g_simple_flags)

        # 符号设置
        g_symbols = QGroupBox("标记符号")
        g_symbols.setContentsMargins(3,12,3,6)
        gl_sym = QGridLayout(g_symbols)
        gl_sym.setHorizontalSpacing(6)
        gl_sym.setVerticalSpacing(6)
        gl_sym.addWidget(QLabel("日高:"), 0, 0)
        self.edit_sym_high = QLineEdit(self.win.sym_high)
        self.edit_sym_high.setFixedWidth(40)
        self.edit_sym_high.setMaxLength(2)
        gl_sym.addWidget(self.edit_sym_high, 0, 1)
        gl_sym.addWidget(QLabel("日低:"), 0, 2)
        self.edit_sym_low = QLineEdit(self.win.sym_low)
        self.edit_sym_low.setFixedWidth(40)
        self.edit_sym_low.setMaxLength(2)
        gl_sym.addWidget(self.edit_sym_low, 0, 3)
        gl_sym.addWidget(QLabel("涨停:"), 1, 0)
        self.edit_sym_limit_up = QLineEdit(self.win.sym_limit_up)
        self.edit_sym_limit_up.setFixedWidth(40)
        self.edit_sym_limit_up.setMaxLength(2)
        gl_sym.addWidget(self.edit_sym_limit_up, 1, 1)
        gl_sym.addWidget(QLabel("跌停:"), 1, 2)
        self.edit_sym_limit_down = QLineEdit(self.win.sym_limit_down)
        self.edit_sym_limit_down.setFixedWidth(40)
        self.edit_sym_limit_down.setMaxLength(2)
        gl_sym.addWidget(self.edit_sym_limit_down, 1, 3)
        gl_sym.addWidget(QLabel("涨:"), 2, 0)
        self.edit_sym_rise = QLineEdit(self.win.sym_rise)
        self.edit_sym_rise.setFixedWidth(40)
        self.edit_sym_rise.setMaxLength(2)
        gl_sym.addWidget(self.edit_sym_rise, 2, 1)
        gl_sym.addWidget(QLabel("跌:"), 2, 2)
        self.edit_sym_fall = QLineEdit(self.win.sym_fall)
        self.edit_sym_fall.setFixedWidth(40)
        self.edit_sym_fall.setMaxLength(2)
        gl_sym.addWidget(self.edit_sym_fall, 2, 3)
        data_settings.addWidget(g_symbols)
        data_settings.addStretch(1)

        return tab_1
    def _on_interval_changed(self, idx):
        seconds = self.cmb_interval.currentData()
        if isinstance(seconds,int): 
            self.win.set_refresh_interval(seconds)

    def _on_cb_changed(self, header: str, state: bool):
        self.win.set_flag(header, state)
        if header == "代码":
            self.cb_short_code.setEnabled(state)
        elif header == "名称":
            self.cmb_namelength.setEnabled(state)
    
    def _on_short_code_toggled(self, checked: bool):
        self.win.set_code_type(checked)

    def _on_name_length_changed(self, length: int):
        self.win.set_name_length(length)

    def _on_b1s1_display_changed(self, idx: int):
        try:
            val = self.cmb_b1s1_display.itemData(idx)
            if not val:
                return
            self.win.set_b1s1_display(val)
        except Exception:
            pass

    def _on_b1s1_toggled(self, state: bool):
        self.win.set_flag("买一", state)
        self.cmb_b1s1_display.setEnabled(state)

    def _on_symbols_changed(self):
        self.win.set_symbols(
            self.edit_sym_high.text(),
            self.edit_sym_low.text(),
            self.edit_sym_limit_up.text(),
            self.edit_sym_limit_down.text(),
            sym_rise=self.edit_sym_rise.text(),
            sym_fall=self.edit_sym_fall.text(),
        )

    def _on_dual_mode_toggled(self, checked: bool):
        self.win.set_dual_mode_enabled(bool(checked))
        self._g_simple_flags.setEnabled(bool(checked))
        self.cmb_leave_delay.setEnabled(bool(checked))

    def _on_leave_delay_changed(self, idx: int):
        ms = self.cmb_leave_delay.currentData()
        if isinstance(ms, int):
            self.win.set_leave_delay_ms(ms)
    def _on_simple_cb_changed(self, header: str, state: bool):
        self.win.set_simple_flag(header, state)
