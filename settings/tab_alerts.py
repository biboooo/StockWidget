# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QCheckBox, QComboBox, QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QScrollArea,
)

class AlertsTabMixin:
    def _build_tab_alerts(self):
        """报警页。"""
        # ---- 第五页：报警 ----
        tab_4 = QWidget()
        alert_settings = QVBoxLayout(tab_4)

        # 涨跌异动报警
        g_price_alert = QGroupBox("涨跌异动报警")
        g_price_alert.setContentsMargins(3, 12, 3, 6)
        gl_pa = QVBoxLayout(g_price_alert)
        gl_pa.setSpacing(8)

        # 启用开关
        self.chk_price_alert = QCheckBox("启用涨跌异动报警")
        self.chk_price_alert.setChecked(bool(self.win.price_alert_enabled))
        gl_pa.addWidget(self.chk_price_alert)

        # 规则列表
        self.list_pa_rules = QListWidget()
        self.list_pa_rules.setFixedHeight(100)
        for rule in self.win.price_alert_rules:
            self._add_pa_rule_item(rule)
        gl_pa.addWidget(self.list_pa_rules)

        # 添加规则区域
        add_row = QGridLayout()
        add_row.setHorizontalSpacing(6)
        add_row.setVerticalSpacing(4)
        add_row.addWidget(QLabel("周期:"), 0, 0)
        self.cmb_pa_period = QComboBox()
        self.cmb_pa_period.setFixedWidth(90)
        for sec in [1, 3, 5, 10, 20, 30, 60, 120, 180, 300, 600]:
            if sec < 60:
                self.cmb_pa_period.addItem(f"{sec}秒", userData=sec)
            else:
                self.cmb_pa_period.addItem(f"{sec//60}分钟", userData=sec)
        self.cmb_pa_period.setCurrentIndex(5)  # 默认30秒
        add_row.addWidget(self.cmb_pa_period, 0, 1)

        add_row.addWidget(QLabel("阈值:"), 0, 2)
        self.edit_pa_threshold = QLineEdit("2.0")
        self.edit_pa_threshold.setFixedWidth(60)
        self.edit_pa_threshold.setPlaceholderText("%")
        th_validator = QDoubleValidator(0.1, 50.0, 2, self)
        th_validator.setNotation(QDoubleValidator.StandardNotation)
        self.edit_pa_threshold.setValidator(th_validator)
        add_row.addWidget(self.edit_pa_threshold, 0, 3)
        add_row.addWidget(QLabel("%"), 0, 4)

        add_row.addWidget(QLabel("冷却:"), 1, 0)
        self.cmb_pa_cooldown = QComboBox()
        self.cmb_pa_cooldown.setFixedWidth(90)
        for sec in [1, 3, 5, 10, 15, 30, 60, 120, 180, 300, 600]:
            if sec < 60:
                self.cmb_pa_cooldown.addItem(f"{sec}秒", userData=sec)
            else:
                self.cmb_pa_cooldown.addItem(f"{sec//60}分钟", userData=sec)
        self.cmb_pa_cooldown.setCurrentIndex(5)  # 默认30秒
        add_row.addWidget(self.cmb_pa_cooldown, 1, 1)

        self.btn_pa_add = QPushButton("添加规则")
        self.btn_pa_add.setFixedWidth(70)
        add_row.addWidget(self.btn_pa_add, 1, 2, 1, 2)
        self.btn_pa_del = QPushButton("删除")
        self.btn_pa_del.setFixedWidth(50)
        add_row.addWidget(self.btn_pa_del, 1, 4)
        gl_pa.addLayout(add_row)

        # 说明
        tip_pa = QLabel("在监测周期内，若股票价格波动超过阈值，\n"
                        "将发出系统通知。冷却时间内同一股票不重复报警。")
        tip_pa.setWordWrap(True)
        tip_pa.setStyleSheet("color: #888;")
        gl_pa.addWidget(tip_pa)

        alert_settings.addWidget(g_price_alert)

        # 新高新低报警
        g_nhl_alert = QGroupBox("新高新低报警")
        g_nhl_alert.setContentsMargins(3, 12, 3, 6)
        gl_nhl = QVBoxLayout(g_nhl_alert)
        gl_nhl.setSpacing(8)

        # 启用开关
        self.chk_nhl_alert = QCheckBox("启用新高新低报警")
        self.chk_nhl_alert.setChecked(bool(self.win.new_high_low_alert_enabled))
        gl_nhl.addWidget(self.chk_nhl_alert)

        # 新高/新低分别开关
        nhl_chk_row = QHBoxLayout()
        self.chk_new_high = QCheckBox("新高报警")
        self.chk_new_high.setChecked(bool(self.win.new_high_alert))
        nhl_chk_row.addWidget(self.chk_new_high)
        self.chk_new_low = QCheckBox("新低报警")
        self.chk_new_low.setChecked(bool(self.win.new_low_alert))
        nhl_chk_row.addWidget(self.chk_new_low)
        nhl_chk_row.addStretch(1)
        gl_nhl.addLayout(nhl_chk_row)

        # 冷却时间
        nhl_cd_row = QHBoxLayout()
        nhl_cd_row.addWidget(QLabel("冷却时间:"))
        self.cmb_nhl_cooldown = QComboBox()
        self.cmb_nhl_cooldown.setFixedWidth(90)
        nhl_cd_options = [5, 10, 15, 30, 60, 120, 180, 300, 600]
        for sec in nhl_cd_options:
            if sec < 60:
                self.cmb_nhl_cooldown.addItem(f"{sec}秒", userData=sec)
            else:
                self.cmb_nhl_cooldown.addItem(f"{sec//60}分钟", userData=sec)
        # 设置当前值
        cur_cd = self.win.new_high_low_cooldown
        for i in range(self.cmb_nhl_cooldown.count()):
            if self.cmb_nhl_cooldown.itemData(i) == cur_cd:
                self.cmb_nhl_cooldown.setCurrentIndex(i)
                break
        nhl_cd_row.addWidget(self.cmb_nhl_cooldown)
        nhl_cd_row.addStretch(1)
        gl_nhl.addLayout(nhl_cd_row)

        # 说明
        tip_nhl = QLabel("当股票价格创当日新高或新低时发出系统通知。\n"
                         "冷却时间内同一股票不重复报警。")
        tip_nhl.setWordWrap(True)
        tip_nhl.setStyleSheet("color: #888;")
        gl_nhl.addWidget(tip_nhl)

        alert_settings.addWidget(g_nhl_alert)

        # 涨跌停通知
        g_limit_alert = QGroupBox("涨跌停通知")
        g_limit_alert.setContentsMargins(3, 12, 3, 6)
        gl_la = QVBoxLayout(g_limit_alert)
        gl_la.setSpacing(8)

        # 启用开关
        self.chk_limit_alert = QCheckBox("启用涨跌停通知")
        self.chk_limit_alert.setChecked(bool(self.win.limit_alert_enabled))
        gl_la.addWidget(self.chk_limit_alert)

        # 到达/离开分别开关
        la_chk_row1 = QHBoxLayout()
        self.chk_reach_limit_up = QCheckBox("到达涨停")
        self.chk_reach_limit_up.setChecked(bool(self.win.limit_alert_reach_up))
        la_chk_row1.addWidget(self.chk_reach_limit_up)
        self.chk_reach_limit_down = QCheckBox("到达跌停")
        self.chk_reach_limit_down.setChecked(bool(self.win.limit_alert_reach_down))
        la_chk_row1.addWidget(self.chk_reach_limit_down)
        la_chk_row1.addStretch(1)
        gl_la.addLayout(la_chk_row1)

        la_chk_row2 = QHBoxLayout()
        self.chk_leave_limit_up = QCheckBox("离开涨停")
        self.chk_leave_limit_up.setChecked(bool(self.win.limit_alert_leave_up))
        la_chk_row2.addWidget(self.chk_leave_limit_up)
        self.chk_leave_limit_down = QCheckBox("离开跌停")
        self.chk_leave_limit_down.setChecked(bool(self.win.limit_alert_leave_down))
        la_chk_row2.addWidget(self.chk_leave_limit_down)
        la_chk_row2.addStretch(1)
        gl_la.addLayout(la_chk_row2)

        # 冷却时间
        la_cd_row = QHBoxLayout()
        la_cd_row.addWidget(QLabel("冷却时间:"))
        self.cmb_limit_alert_cooldown = QComboBox()
        self.cmb_limit_alert_cooldown.setFixedWidth(90)
        la_cd_options = [5, 10, 15, 30, 60, 120, 180, 300, 600]
        for sec in la_cd_options:
            if sec < 60:
                self.cmb_limit_alert_cooldown.addItem(f"{sec}秒", userData=sec)
            else:
                self.cmb_limit_alert_cooldown.addItem(f"{sec//60}分钟", userData=sec)
        # 设置当前值
        cur_la_cd = self.win.limit_alert_cooldown
        for i in range(self.cmb_limit_alert_cooldown.count()):
            if self.cmb_limit_alert_cooldown.itemData(i) == cur_la_cd:
                self.cmb_limit_alert_cooldown.setCurrentIndex(i)
                break
        la_cd_row.addWidget(self.cmb_limit_alert_cooldown)
        la_cd_row.addStretch(1)
        gl_la.addLayout(la_cd_row)

        # 说明
        tip_la = QLabel("当股票价格到达涨跌停或离开涨跌停时发出系统通知。\n"
                        "冷却时间内同一股票不重复报警。")
        tip_la.setWordWrap(True)
        tip_la.setStyleSheet("color: #888;")
        gl_la.addWidget(tip_la)

        alert_settings.addWidget(g_limit_alert)
        alert_settings.addStretch(1)

        return tab_4
    def _build_tab_help(self):
        """使用说明页。"""
        #第五页：使用说明
        tab_help = QWidget()
        lay_help = QVBoxLayout(tab_help)
        lay_help.setContentsMargins(5, 5, 5, 5)
        
        # 1. 创建滚动区域，防止4K或笔记本小屏幕下文字显示不全
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        # 2. 用富文本和美观的 HTML 表格来排版说明书
        help_html = """
        <div style="line-height: 1.6; font-size: 13px; color: #333333; padding: 10px;">
            <h3 style="color: #2B579A; margin-top: 0; border-bottom: 2px solid #2B579A; padding-bottom: 5px;">
                💡 智能输入指南
            </h3>
            <p>在自选列表中添加代码时，<b>无需手动敲击任何奇葩的前缀后缀</b>，直接输入品种简称，系统将自动智能化识别：</p>
            
            <table border="0" cellpadding="8" cellspacing="0" style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                <tr style="background-color: #E9ECEF; font-weight: bold;">
                    <td style="width: 25%; border-bottom: 1px solid #DEE2E6;">品种类型</td>
                    <td style="border-bottom: 1px solid #DEE2E6;">直接输入示例与说明</td>
                </tr>
                <tr>
                    <td style="border-bottom: 1px solid #F1F3F5;"><b>A股 / 美股</b></td>
                    <td style="border-bottom: 1px solid #F1F3F5;">输入纯数字或纯字母（如 <code>600519</code> 茅台、<code>AAPL</code> 苹果）</td>
                </tr>
                <tr style="background-color: #F8F9FA;">
                    <td style="border-bottom: 1px solid #F1F3F5;"><b>港股行情</b></td>
                    <td style="border-bottom: 1px solid #F1F3F5;">输入 5 位纯数字（如 <code>00700</code> 腾讯、<code>01810</code> 小米集团）</td>
                </tr>
                <tr>
                    <td style="border-bottom: 1px solid #F1F3F5;"><b>全球指数</b></td>
                    <td style="border-bottom: 1px solid #F1F3F5;">输入大写简称（如 <code>DJI</code> 道指、<code>NKY</code> 日经、<code>KS11</code> 韩国指数）</td>
                </tr>
                <tr style="background-color: #F8F9FA;">
                    <td style="border-bottom: 1px solid #F1F3F5;"><b>国内期货</b></td>
                    <td style="border-bottom: 1px solid #F1F3F5;">输入品种字母+数字（如 <code>RB0</code> 螺纹钢、<code>AU0</code> 沪金）</td>
                </tr>
                <tr>
                    <td style="border-bottom: 1px solid #F1F3F5;"><b>外盘期货</b></td>
                    <td style="border-bottom: 1px solid #F1F3F5;">输入国际通用代号（如 <code>XAU</code> 伦敦金、<code>CL</code> 美原油、<code>OIL</code> 原油）</td>
                </tr>
                <tr style="background-color: #F8F9FA;">
                    <td style="border-bottom: 1px solid #F1F3F5;"><b>即期外汇</b></td>
                    <td style="border-bottom: 1px solid #F1F3F5;">输入 6 位外汇货币对（如 <code>USDJPY</code> 美元日元、<code>EURUSD</code> 汇率）</td>
                </tr>
            </table>
            
            <div style="margin-top: 20px; padding: 10px; background-color: #FFF3CD; border-left: 4px solid #FFC107; border-radius: 4px;">
                <b>🛠️ 超级极冷门品种：</b><br/>
                如果未来上线了全新的冷门国家品种（代码词典未收录），可在输入框中直接键入新浪官方底层的<b>完整前缀代码</b>（例如输入 <code>b_XU100</code> 强行查土耳其指数），系统将开启绿色通道直接放行请求！
            </div>
        </div>
        """
        
        lbl_help = QLabel(help_html)
        lbl_help.setWordWrap(True)  # 激活自动换行
        lbl_help.setTextFormat(Qt.RichText)
        
        # 3. 将标签放入滚动区域，再将滚动区域放入新 Tab
        scroll_area.setWidget(lbl_help)
        lay_help.addWidget(scroll_area)
        
        # 4. 把这个说明页挂载到 Tab 栏
        return tab_help
    # —— 涨跌异动报警槽 --
    def _on_price_alert_toggled(self, checked: bool):
        self.win.set_price_alert_enabled(bool(checked))

    def _add_pa_rule_item(self, rule: dict):
        """向规则列表添加一项。"""
        period = rule.get("period", 60)
        threshold = rule.get("threshold", 2.0)
        cooldown = rule.get("cooldown", 120)
        if period < 60:
            p_str = f"{period}秒"
        else:
            p_str = f"{period//60}分钟"
        if cooldown < 60:
            c_str = f"{cooldown}秒"
        else:
            c_str = f"{cooldown//60}分钟"
        label = f"周期 {p_str} | 阈值 {threshold:g}% | 冷却 {c_str}"
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, rule)
        self.list_pa_rules.addItem(item)

    def _on_pa_add_rule(self):
        """Read UI values and add a new rule."""
        try:
            period = self.cmb_pa_period.currentData()
            threshold_txt = self.edit_pa_threshold.text().strip()
            threshold = float(threshold_txt) if threshold_txt else 2.0
            cooldown = self.cmb_pa_cooldown.currentData()
            if not isinstance(period, int) or not isinstance(cooldown, int):
                return
            rule = {"period": period, "threshold": threshold, "cooldown": cooldown}
            self._add_pa_rule_item(rule)
            self.win.add_price_alert_rule(period, threshold, cooldown)
        except Exception:
            pass

    def _on_pa_del_rule(self):
        """Delete selected rule."""
        row = self.list_pa_rules.currentRow()
        if row >= 0:
            self.list_pa_rules.takeItem(row)
            self.win.remove_price_alert_rule(row)

    # —— 新高新低报警槽 --
    def _on_nhl_alert_toggled(self, checked: bool):
        self.win.set_new_high_low_alert_enabled(bool(checked))

    def _on_new_high_toggled(self, checked: bool):
        self.win.set_new_high_alert(bool(checked))

    def _on_new_low_toggled(self, checked: bool):
        self.win.set_new_low_alert(bool(checked))

    def _on_nhl_cooldown_changed(self, index: int):
        sec = self.cmb_nhl_cooldown.currentData()
        if isinstance(sec, int):
            self.win.set_new_high_low_cooldown(sec)

    # —— 涨跌停通知槽 --
    def _on_limit_alert_toggled(self, checked: bool):
        self.win.set_limit_alert_enabled(bool(checked))

    def _on_reach_limit_up_toggled(self, checked: bool):
        self.win.set_limit_alert_reach_up(bool(checked))

    def _on_reach_limit_down_toggled(self, checked: bool):
        self.win.set_limit_alert_reach_down(bool(checked))

    def _on_leave_limit_up_toggled(self, checked: bool):
        self.win.set_limit_alert_leave_up(bool(checked))

    def _on_leave_limit_down_toggled(self, checked: bool):
        self.win.set_limit_alert_leave_down(bool(checked))

    def _on_limit_alert_cooldown_changed(self, index: int):
        sec = self.cmb_limit_alert_cooldown.currentData()
        if isinstance(sec, int):
            self.win.set_limit_alert_cooldown(sec)
