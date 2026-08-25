# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QPushButton,
    QSlider, QCheckBox, QComboBox, QColorDialog,
)

MIN_FONT_SIZE = 6

class AppearanceTabMixin:
    def _build_tab_appearance(self):
        """外观页。"""
        # ---- 第三页 ----
        tab_2 = QWidget()
        appearance_settings = QVBoxLayout(tab_2)

        # 表格外观
        g_table = QGroupBox("表格外观")
        g_table.setContentsMargins(3,12,3,6)
        gl_table = QGridLayout(g_table)
        gl_table.setHorizontalSpacing(6)
        gl_table.setVerticalSpacing(6)
        # 复选框
        self.chk_table_header = QCheckBox("显示表头")
        self.chk_table_header.setChecked(self.win.header_visible)
        self.chk_table_grid = QCheckBox("显示网格")
        self.chk_table_grid.setChecked(self.win.grid_visible)

        gl_table.addWidget(self.chk_table_header,0,0)
        gl_table.addWidget(self.chk_table_grid,0,1)
        appearance_settings.addWidget(g_table)

        # 3.颜色/透明度
        g_color = QGroupBox("颜色与透明度")
        g_color.setContentsMargins(3,12,3,6)
        gl_color = QGridLayout(g_color)
        gl_color.setHorizontalSpacing(6)
        gl_color.setVerticalSpacing(6)
        # 3.1 颜色按钮：涨/跌/表格/背景
        self.btn_up_color = QPushButton("涨颜色…")
        self.btn_up_color.setFixedWidth(90)
        self.btn_down_color = QPushButton("跌颜色…")
        self.btn_down_color.setFixedWidth(90)
        self.btn_fg = QPushButton("表格颜色…")
        self.btn_fg.setFixedWidth(90)
        self.btn_bg = QPushButton("背景颜色…")
        self.btn_bg.setFixedWidth(90)
        # 3.2 恢复默认按钮
        self.btn_reset_colors = QPushButton("恢复默认")
        self.btn_reset_colors.setFixedWidth(90)
        # 3.3 滑块：表格不透明度（表格线/表头底边线）
        self.slider_grid_alpha = QSlider(Qt.Horizontal)
        self.slider_grid_alpha.setRange(0, 100)
        self.slider_grid_alpha.setMinimumWidth(150)
        self.slider_grid_alpha.setValue(int(getattr(self.win, 'grid_alpha_pct', 31)))
        self.lbl_grid_alpha = QLabel(f"{self.slider_grid_alpha.value()}%")
        # 3.4 滑块：表头不透明度（表头文字）
        self.slider_header_alpha = QSlider(Qt.Horizontal)
        self.slider_header_alpha.setRange(0, 100)
        self.slider_header_alpha.setMinimumWidth(150)
        self.slider_header_alpha.setValue(int(getattr(self.win, 'header_alpha_pct', 100)))
        self.lbl_header_alpha = QLabel(f"{self.slider_header_alpha.value()}%")
        # 3.5 滑块：背景不透明度
        self.slider_bg_alpha = QSlider(Qt.Horizontal)
        self.slider_bg_alpha.setRange(1, 100)
        self.slider_bg_alpha.setMinimumWidth(150)
        self.slider_bg_alpha.setValue(int(round(self.win.bg.alpha()/2.55)))
        self.lbl_bg_alpha = QLabel(f"{self.slider_bg_alpha.value()}%")
        # 3.6 滑块：整体不透明度
        self.slider_win_opacity = QSlider(Qt.Horizontal)
        self.slider_win_opacity.setRange(20, 100)
        self.slider_win_opacity.setMinimumWidth(150)
        self.slider_win_opacity.setValue(int(round(self.win.windowOpacity()*100)))
        self.lbl_win_opacity = QLabel(f"{self.slider_win_opacity.value()}%")

        gl_color.addWidget(self.btn_up_color,0,0,1,2)
        gl_color.addWidget(self.btn_down_color,0,2,1,2)
        gl_color.addWidget(self.btn_fg,0,4,1,2)
        gl_color.addWidget(self.btn_bg,1,0,1,2)
        gl_color.addWidget(self.btn_reset_colors,1,4,1,2)
        gl_color.addWidget(QLabel("表格不透明度："),2,0,1,2)
        gl_color.addWidget(self.slider_grid_alpha,2,2,1,3)
        gl_color.addWidget(self.lbl_grid_alpha,2,5,1,1)
        gl_color.addWidget(QLabel("表头不透明度："),3,0,1,2)
        gl_color.addWidget(self.slider_header_alpha,3,2,1,3)
        gl_color.addWidget(self.lbl_header_alpha,3,5,1,1)
        gl_color.addWidget(QLabel("背景不透明度："),4,0,1,2)
        gl_color.addWidget(self.slider_bg_alpha,4,2,1,3)
        gl_color.addWidget(self.lbl_bg_alpha,4,5,1,1)
        gl_color.addWidget(QLabel("整体不透明度："),5,0,1,2)
        gl_color.addWidget(self.slider_win_opacity,5,2,1,3)
        gl_color.addWidget(self.lbl_win_opacity,5,5,1,1)
        appearance_settings.addWidget(g_color)

        # 4.字体/行距
        g_font = QGroupBox("字体与行距")
        g_font.setContentsMargins(3,12,3,6)
        gl_font = QGridLayout(g_font)
        gl_font.setHorizontalSpacing(6)
        gl_font.setVerticalSpacing(6)
        # 4.1 选项：字体
        self.cmb_family = QComboBox()
        self.cmb_family.setFixedWidth(200)
        for fam in sorted(QFontDatabase.families()):
            self.cmb_family.addItem(fam)
        fi = self.cmb_family.findText(self.win.font.family())
        self.cmb_family.setCurrentIndex(fi if fi >= 0 else 0)
        # 4.2 滑块：字号
        self.slider_font = QSlider(Qt.Horizontal)
        self.slider_font.setRange(MIN_FONT_SIZE, 15)
        self.slider_font.setMinimumWidth(150)
        self.slider_font.setValue(self.win.font.pointSize())
        self.lbl_font = QLabel(f"{self.slider_font.value()} pt")
        # 4.3 滑块：行间距
        self.slider_line = QSlider(Qt.Horizontal)
        self.slider_line.setRange(0, 20)
        self.slider_line.setMinimumWidth(150)
        self.slider_line.setValue(getattr(self.win,"line_extra_px",4))
        self.lbl_line = QLabel(f"+{self.slider_line.value()} px")

        gl_font.addWidget(QLabel("字体："),0,0,1,2)
        gl_font.addWidget(self.cmb_family,0,2,1,4)
        gl_font.addWidget(QLabel("字号："),1,0,1,2)
        gl_font.addWidget(self.slider_font,1,2,1,3)
        gl_font.addWidget(self.lbl_font,1,5,1,1)
        gl_font.addWidget(QLabel("行距："),2,0,1,2)
        gl_font.addWidget(self.slider_line,2,2,1,3)
        gl_font.addWidget(self.lbl_line,2,5,1,1)
        appearance_settings.addWidget(g_font)

        return tab_2
    def _on_reset_colors(self):
        try:
            self.win.reset_default_colors()
        except Exception:
            pass

    def _on_grid_toggled(self, checked: bool):
        self.win.set_grid_visible(bool(checked))

    def _on_header_toggled(self, checked: bool):
        self.win.set_header_visible(bool(checked))
    def pick_fg(self):
        c = QColorDialog.getColor(self.win.fg, self, "选择表格颜色")
        if c.isValid(): self.win.set_fg_color(c)
    def pick_up_color(self):
        c = QColorDialog.getColor(self.win.up_color, self, "选择涨颜色")
        if c.isValid(): self.win.set_up_color(c)
    def pick_down_color(self):
        c = QColorDialog.getColor(self.win.down_color, self, "选择跌颜色")
        if c.isValid(): self.win.set_down_color(c)
    def pick_bg(self):
        base = QColor(self.win.bg)
        base.setAlpha(255)
        c = QColorDialog.getColor(base, self, "选择背景颜色")
        if c.isValid(): self.win.set_bg_rgb_keep_alpha(c)
    def apply_bg_alpha(self, v): 
        self.lbl_bg_alpha.setText(f"{v}%")
        self.win.set_bg_alpha_percent(v)
    def apply_win_opacity(self, v): 
        self.lbl_win_opacity.setText(f"{v}%")
        self.win.set_window_opacity_percent(v)
    def apply_grid_alpha(self, v):
        self.lbl_grid_alpha.setText(f"{v}%")
        self.win.set_grid_alpha_percent(v)
    def apply_header_alpha(self, v):
        self.lbl_header_alpha.setText(f"{v}%")
        self.win.set_header_alpha_percent(v)
    def _on_family_changed(self, fam: str): 
        self.win.set_font_family(fam)
    def apply_font_size(self, v):
        self.lbl_font.setText(f"{v} pt")
        self.win.set_font_size(v)  # 同步 K 线缩放
    def _on_line_changed(self, v: int): 
        self.lbl_line.setText(f"+{v} px")
        self.win.set_line_extra(v)
