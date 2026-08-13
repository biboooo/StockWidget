# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING

import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QDialog, QHBoxLayout, QTabWidget, QWidget, QSizePolicy

from settings.dialogs import CostDialog, AlertDialog
from settings.tab_codes import CodesTabMixin
from settings.tab_display import DisplayTabMixin
from settings.tab_appearance import AppearanceTabMixin
from settings.tab_general import GeneralTabMixin
from settings.tab_alerts import AlertsTabMixin

if TYPE_CHECKING:
    from WidgetPanel import FloatLabel


class SettingsDialog(
    CodesTabMixin,
    DisplayTabMixin,
    AppearanceTabMixin,
    GeneralTabMixin,
    AlertsTabMixin,
    QDialog,
):
    def __init__(self, win: "FloatLabel", parent: QWidget, app=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.win = win
        self.app = app
        self.setModal(False)

        main = QHBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(8)
        self.tabs = QTabWidget()
        main.addWidget(self.tabs)

        self.tab_sizes = {
            0: QSize(560, 320),
            1: QSize(480, 750),
            2: QSize(480, 460),
            3: QSize(480, 280),
            4: QSize(480, 720),
        }

        self.tabs.addTab(self._build_tab_codes(), "自选列表")
        self.tabs.addTab(self._build_tab_display(), "显示数据")
        self.tabs.addTab(self._build_tab_appearance(), "外观")
        self.tabs.addTab(self._build_tab_general(), "常规")
        self.tabs.addTab(self._build_tab_alerts(), "报警")
        self.tabs.addTab(self._build_tab_help(), "使用说明")

        self._connect_signals()
        self._apply_tab_size(0)

    def _connect_signals(self):
        # 连接：代码列表
        self.list_codes.itemChanged.connect(self._on_codes_changed)
        self.btn_add.clicked.connect(self._add_code)
        self.btn_del.clicked.connect(self._del_code)
        self.btn_up.clicked.connect(self._move_up)
        self.btn_dn.clicked.connect(self._move_down)
        self.btn_cost.clicked.connect(self._open_cost_dialog_for_current)
        self.btn_alert.clicked.connect(self._open_alert_dialog_for_current)
        self.list_codes.itemSelectionChanged.connect(self._on_list_selection_changed)
        self.list_codes.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_codes.customContextMenuRequested.connect(self._on_list_context_menu)
        self._refresh_all_names()
        # 连接：其它设置
        self.cmb_interval.currentIndexChanged.connect(self._on_interval_changed)
        self.cmb_namelength.currentIndexChanged.connect(self._on_name_length_changed)
        self.btn_up_color.clicked.connect(self.pick_up_color)
        self.btn_down_color.clicked.connect(self.pick_down_color)
        self.btn_fg.clicked.connect(self.pick_fg)
        self.btn_bg.clicked.connect(self.pick_bg)
        self.btn_reset_colors.clicked.connect(self._on_reset_colors)
        self.slider_bg_alpha.valueChanged.connect(self.apply_bg_alpha)
        self.slider_win_opacity.valueChanged.connect(self.apply_win_opacity)
        self.slider_grid_alpha.valueChanged.connect(self.apply_grid_alpha)
        self.slider_header_alpha.valueChanged.connect(self.apply_header_alpha)
        self.cmb_family.currentTextChanged.connect(self._on_family_changed)
        self.slider_font.valueChanged.connect(self.apply_font_size)
        self.slider_line.valueChanged.connect(self._on_line_changed)
        self.edit_hotkey.editingFinished.connect(self._on_hotkey_changed)
        self.chk_start_on_boot.toggled.connect(self._on_start_on_boot_toggled)
        self.chk_table_header.toggled.connect(self._on_header_toggled)
        self.chk_table_grid.toggled.connect(self._on_grid_toggled)
        try:
            cur_choice = None
            if hasattr(self, 'app') and self.app is not None:
                cur_choice = getattr(self.app, '_app_icon_choice', None)
            if cur_choice is None:
                cur_choice = 'default'
            idx = self.cmb_icon.findData(cur_choice)
            if idx < 0:
                if isinstance(cur_choice, str) and os.path.exists(cur_choice):
                    self.cmb_icon.addItem('自定义', userData=cur_choice)
                    idx = self.cmb_icon.count()-1
            self.cmb_icon.setCurrentIndex(idx if idx >= 0 else 0)
        except Exception:
            pass
        self.cmb_icon.currentIndexChanged.connect(self._on_icon_changed)
        self.btn_pick_icon.clicked.connect(self._pick_custom_icon)
        self.tabs.currentChanged.connect(self._apply_tab_size)
        self.cmb_b1s1_display.currentIndexChanged.connect(self._on_b1s1_display_changed)
        self.cb_short_code.stateChanged.connect(self._on_short_code_toggled)
        self.edit_sym_high.textChanged.connect(self._on_symbols_changed)
        self.edit_sym_low.textChanged.connect(self._on_symbols_changed)
        self.edit_sym_limit_up.textChanged.connect(self._on_symbols_changed)
        self.edit_sym_limit_down.textChanged.connect(self._on_symbols_changed)
        self.edit_sym_rise.textChanged.connect(self._on_symbols_changed)
        self.edit_sym_fall.textChanged.connect(self._on_symbols_changed)
        self.chk_dual_mode.toggled.connect(self._on_dual_mode_toggled)
        self.cmb_leave_delay.currentIndexChanged.connect(self._on_leave_delay_changed)
        self.rb_anchor_left.toggled.connect(self._on_anchor_changed)
        self.rb_anchor_right.toggled.connect(self._on_anchor_changed)
        self.chk_price_alert.toggled.connect(self._on_price_alert_toggled)
        self.btn_pa_add.clicked.connect(self._on_pa_add_rule)
        self.btn_pa_del.clicked.connect(self._on_pa_del_rule)
        self.chk_nhl_alert.toggled.connect(self._on_nhl_alert_toggled)
        self.chk_new_high.toggled.connect(self._on_new_high_toggled)
        self.chk_new_low.toggled.connect(self._on_new_low_toggled)
        self.cmb_nhl_cooldown.currentIndexChanged.connect(self._on_nhl_cooldown_changed)
        self.chk_limit_alert.toggled.connect(self._on_limit_alert_toggled)
        self.chk_reach_limit_up.toggled.connect(self._on_reach_limit_up_toggled)
        self.chk_reach_limit_down.toggled.connect(self._on_reach_limit_down_toggled)
        self.chk_leave_limit_up.toggled.connect(self._on_leave_limit_up_toggled)
        self.chk_leave_limit_down.toggled.connect(self._on_leave_limit_down_toggled)
        self.cmb_limit_alert_cooldown.currentIndexChanged.connect(self._on_limit_alert_cooldown_changed)

    def _apply_tab_size(self, index: int):
        target_size = self.tab_sizes.get(index, QSize(480, 400))
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        for i in range(self.tabs.count()):
            page = self.tabs.widget(i)
            if i == index:
                page.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            else:
                page.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.tabs.updateGeometry()
        self.setFixedSize(target_size)


# re-exports for compatibility
__all__ = ["SettingsDialog", "CostDialog", "AlertDialog"]
