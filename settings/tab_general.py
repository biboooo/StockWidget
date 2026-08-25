# -*- coding: utf-8 -*-
import os

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QCheckBox, QComboBox, QPushButton, QKeySequenceEdit, QFileDialog,
    QRadioButton, QButtonGroup,
)

class GeneralTabMixin:
    def _build_tab_general(self):
        """常规页。"""
        # ---- 第四页 ----
        tab_3 = QWidget()
        other_settings = QVBoxLayout(tab_3)

        # 4.热键
        g_hotkey = QGroupBox("快捷键")
        g_hotkey.setContentsMargins(3,12,3,6)
        gl_hotkey = QGridLayout(g_hotkey)
        gl_hotkey.setHorizontalSpacing(6)
        gl_hotkey.setVerticalSpacing(6)
        gl_hotkey.addWidget(QLabel("隐藏/显示浮窗："),0,0,1,1)
        self.edit_hotkey = QKeySequenceEdit()
        self.edit_hotkey.setKeySequence(QKeySequence(self.win.hotkey))
        gl_hotkey.addWidget(self.edit_hotkey,0,1)
        # 开机启动复选框
        self.chk_start_on_boot = QCheckBox("开机启动")
        self.chk_start_on_boot.setChecked(bool(self.win.start_on_boot))
        other_settings.addWidget(self.chk_start_on_boot)
        other_settings.addWidget(g_hotkey)

        # 窗口锚点
        from PySide6.QtWidgets import QRadioButton, QButtonGroup
        g_anchor = QGroupBox("窗口锚点")
        g_anchor.setContentsMargins(3,12,3,6)
        gl_anchor = QHBoxLayout(g_anchor)
        self.rb_anchor_left = QRadioButton("左对齐")
        self.rb_anchor_right = QRadioButton("右对齐")
        cur_anchor = getattr(self.win, 'anchor', 'left')
        if cur_anchor == 'right':
            self.rb_anchor_right.setChecked(True)
        else:
            self.rb_anchor_left.setChecked(True)
        self._anchor_group = QButtonGroup(self)
        self._anchor_group.addButton(self.rb_anchor_left)
        self._anchor_group.addButton(self.rb_anchor_right)
        gl_anchor.addWidget(QLabel("指标变化时保持："))
        gl_anchor.addWidget(self.rb_anchor_left)
        gl_anchor.addWidget(self.rb_anchor_right)
        gl_anchor.addStretch(1)
        other_settings.addWidget(g_anchor)

        # 程序图标选择
        g_icon = QGroupBox("程序图标")
        g_icon.setContentsMargins(3,12,3,6)
        gl_icon = QHBoxLayout(g_icon)
        self.cmb_icon = QComboBox()
        icon_items = [
            ("默认", 'default'),
            ("系统：计算机", 'std:computer'),
            ("系统：网络", 'std:network'),
            ("系统：文件夹", 'std:folder'),
            ("系统：文件", 'std:file'),
            ("系统：回收站", 'std:trash'),
        ]
        for label, val in icon_items:
            self.cmb_icon.addItem(label, userData=val)
        self.btn_pick_icon = QPushButton("自定义图标…")
        self.btn_pick_icon.setFixedWidth(120)
        gl_icon.addWidget(self.cmb_icon)
        gl_icon.addWidget(self.btn_pick_icon)
        other_settings.addWidget(g_icon)
        other_settings.addStretch(1)

        return tab_3
    def _on_start_on_boot_toggled(self, checked: bool):
        try:
            self.win.set_start_on_boot(bool(checked))
            if hasattr(self, 'app') and self.app is not None:
                try:
                    self.app.set_start_on_boot(bool(checked))
                except Exception:
                    pass
        except Exception:
            pass
    def _on_anchor_changed(self, _checked: bool):
        try:
            anchor = 'right' if self.rb_anchor_right.isChecked() else 'left'
            self.win.set_anchor(anchor)
        except Exception:
            pass
    def _on_hotkey_changed(self):
        new_hotkey = self.edit_hotkey.keySequence().toString()
        try:
            self.win.update_hotkey(new_hotkey)
        except Exception:
            pass

    def _on_icon_changed(self, idx: int):
        try:
            val = self.cmb_icon.itemData(idx)
            if not val:
                return
            if hasattr(self, 'app') and self.app is not None:
                try:
                    self.app.set_app_icon(val)
                    # persist immediately
                    try:
                        self.app.save_now()
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

    def _pick_custom_icon(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "选择图标文件", os.path.expanduser('~'), "图标文件 (*.ico);;All Files (*)")
            if path:
                # append or find existing custom entry
                idx = self.cmb_icon.findData(path)
                if idx < 0:
                    self.cmb_icon.addItem('自定义', userData=path)
                    idx = self.cmb_icon.count()-1
                self.cmb_icon.setCurrentIndex(idx)
                # trigger change handler will call app.set_app_icon
        except Exception:
            pass
