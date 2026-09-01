import keyboard
from functools import partial
import webbrowser

from PySide6.QtCore import QPropertyAnimation, QRect, Qt, QEvent, QTimer, Signal, QPoint
from PySide6.QtGui import QEnterEvent, QFont, QAction, QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QVBoxLayout, QLabel, QTableView, QHeaderView, QAbstractItemView, QFrame, QStyledItemDelegate, QStyle

from Display import SimpleTableModel, KLineDelegate, DEFAULT_UP_COLOR, DEFAULT_DOWN_COLOR, DEFAULT_TABLE_COLOR
from widget.edge_hide import EdgeHideMixin
from widget.market_data import MarketDataMixin
from widget.alerts import AlertsMixin
from widget.quote_db import init_db
MIN_FONT_SIZE = 6

class NoSelectionDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # 1. 强制剥离所有视觉状态，让它看起来永远是“最原始”的状态
        option.state &= ~QStyle.State_Selected  # 去掉选中
        option.state &= ~QStyle.State_HasFocus  # 去掉焦点虚线/高亮
        option.state &= ~QStyle.State_Active    # 去掉激活状态

        # 2. 调用父类绘制
        super().paint(painter, option, index)

class FloatLabel(EdgeHideMixin, MarketDataMixin, AlertsMixin, QWidget):
    hotkey_triggered = Signal()
    def __init__(self, cfg: dict, quotes_db: str | None = None):
        super().__init__()
        self._on_change = (lambda: None)
        self._open_settings_cb = None

        # 行情 SQLite 缓存（与 SW_config.json 同目录）
        if not quotes_db:
            import sys, os
            if getattr(sys, "frozen", False):
                _base = os.path.dirname(sys.executable)
            else:
                _base = os.path.dirname(os.path.abspath(__file__))
            quotes_db = os.path.join(_base, "SW_quotes.db")
        self._quote_db = init_db(quotes_db)

        # --- 贴边隐藏相关设置 ---
        self.is_hidden_state = False # 记录当前是否处于隐藏状态
        self.edge_margin = 10        # 距离边缘多少像素算“贴边”
        self.expose_width = 15        # 隐藏后露出的像素宽度（用来接收鼠标事件）
        self.hidden_pos = None       # 隐藏时的位置
        self.normal_pos = None       # 正常显示时的位置
        self.hide_direction = None   # 隐藏方向：'top', 'left', 'right'
        self.is_dragging = False  # 记录当前是否正在被鼠标拖拽

        # 检查贴边的定时器
        self.edge_check_timer = QTimer(self)
        self.edge_check_timer.timeout.connect(self._check_edge_and_hide)
        self.edge_check_timer.start(500) # 每 500 毫秒检查一次

        # 平滑移动动画
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(200) # 动画时长 200 毫秒

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        # 自选列表：优先 SQLite watchlist；空则从 JSON 迁移一次
        codes_cfg               = cfg.get("codes", ["sh000001"])
        checked_codes_cfg       = cfg.get("checked_codes", cfg.get("visible_codes", codes_cfg))
        self.refresh_seconds    = int(cfg.get("refresh_seconds", 2))        # 刷新间隔
        flags_cfg               = cfg.get("flags", {})                      # 指标开关（字典格式）
        self.short_code         = bool(cfg.get("short_code", False))
        self.name_length        = int(cfg.get("name_length",0))
        # b1s1_display: 'qty'|'price'|'both'。兼容旧配置键 b1s1_price (bool)
        b1s1_display_cfg = cfg.get("b1s1_display", None)
        if isinstance(b1s1_display_cfg, str) and b1s1_display_cfg in ("qty", "price", "both"):
            self.b1s1_display = b1s1_display_cfg
        else:
            # 旧配置兼容：若 b1s1_price 为 True 则默认显示价格，否则显示数量
            self.b1s1_display = "price" if bool(cfg.get("b1s1_price", False)) else "qty"
        
        # 防止买一/卖一同步时触发重复处理
        self._syncing_b1s1 = False

        self.header_visible     = bool(cfg.get("header_visible", False))    # 表头可见
        self.grid_visible       = bool(cfg.get("grid_visible", False))      # 网格可见

        font_family             = cfg.get("font_family", "Microsoft YaHei") # 字体类型
        font_size               = int(cfg.get("font_size", 10))             # 字体大小
        self.line_extra_px      = int(cfg.get("line_extra_px", 1))          # 行间距
        self.fg                 = QColor(cfg.get("fg", DEFAULT_TABLE_COLOR.name(QColor.HexRgb)))   # 表格颜色（中性/表头/网格）
        self.up_color           = QColor(cfg.get("up_color", DEFAULT_UP_COLOR.name(QColor.HexRgb)))   # 涨颜色
        self.down_color         = QColor(cfg.get("down_color", DEFAULT_DOWN_COLOR.name(QColor.HexRgb))) # 跌颜色
        self.grid_alpha_pct     = max(0, min(100, int(cfg.get("grid_alpha_pct", 31))))  # 表格线/边框不透明度(%)
        self.header_alpha_pct   = max(0, min(100, int(cfg.get("header_alpha_pct", 100))))# 表头文字不透明度(%)
        bg                      = cfg.get("bg", {"r":0,"g":0,"b":0,"a":191})# 背景色
        self.opacity_pct        = int(cfg.get("opacity_pct", 90))           # 透明度

        self.hotkey             = cfg.get("hotkey", "Ctrl+Alt+F")           # 快捷键
        self.start_on_boot      = bool(cfg.get("start_on_boot", False))

        # 锚点：'left' 或 'right'，决定窗口宽度变化时保持哪一边对齐
        anchor_cfg = cfg.get("anchor", "left")
        self.anchor = anchor_cfg if anchor_cfg in ("left", "right") else "left"

        # 双模式切换
        self.dual_mode_enabled = bool(cfg.get("dual_mode_enabled", False))  # 是否启用双模式切换
        self.leave_delay_ms = int(cfg.get("leave_delay_ms", 500))           # 鼠标离开后切换简易模式的延迟(ms)
        self._is_hovered = False  # 鼠标是否悬浮在浮窗上
        # 手动模式：当双模式自动切换关闭时生效，可选 "normal"/"simple"
        manual_mode_cfg = str(cfg.get("manual_mode", "normal")).lower()
        self.manual_mode = manual_mode_cfg if manual_mode_cfg in ("normal", "simple") else "normal"

        # 符号设置：日高/日低、涨停/跌停、涨/跌
        self.sym_high       = cfg.get("sym_high", "↑")         # 日高符号
        self.sym_low        = cfg.get("sym_low", "↓")          # 日低符号
        self.sym_limit_up   = cfg.get("sym_limit_up", "⇧")     # 涨停符号
        self.sym_limit_down = cfg.get("sym_limit_down", "⇩")   # 跌停符号
        self.sym_rise       = cfg.get("sym_rise", "+")          # 涨符号（用于涨跌值/涨跌幅/盈亏/委比）
        self.sym_fall       = cfg.get("sym_fall", "-")          # 跌符号（用于涨跌值/涨跌幅/盈亏/委比）

        # 持仓成本数据：{code: {"cost": float, "qty": int}}
        cost_cfg = cfg.get("cost_data", {}) or {}
        self.cost_data = {}
        if isinstance(cost_cfg, dict):
            for k, v in cost_cfg.items():
                try:
                    if not isinstance(v, dict):
                        continue
                    cost = float(v.get("cost", 0))
                    qty = int(v.get("qty", 0))
                    if cost > 0 and qty != 0:
                        self.cost_data[str(k).strip().lower()] = {"cost": cost, "qty": qty}
                except Exception:
                    pass

        # 买卖点：{code: {"buy": float, "sell": float}}，由 SQLite watchlist 加载
        self.trade_points = {}

        # 封单预警阈值：{code: [int, ...]}（正=涨停封单手数，负=跌停封单手数）
        alert_cfg = cfg.get("alert_data", {}) or {}
        self.alert_data = {}
        self._alert_state = {}  # 运行时生效状态，与 thresholds 索引一一对应
        self._notify_alert = None  # 通知回调 fn(title, msg)
        self._pnl_callback = None  # 总盈亏更新回调 fn(total_pnl: float, has_pnl: bool)
        self._tooltip_callback = None  # 托盘 ToolTip 文本更新回调 fn(text: str)
        if isinstance(alert_cfg, dict):
            for k, v in alert_cfg.items():
                try:
                    if not isinstance(v, list):
                        continue
                    code_key = str(k).strip().lower()
                    ts = []
                    for t in v:
                        try:
                            n = int(t)
                            if n != 0 and n not in ts:
                                ts.append(n)
                        except Exception:
                            pass
                    if ts:
                        self.alert_data[code_key] = ts
                        self._alert_state[code_key] = [False] * len(ts)
                except Exception:
                    pass

        # 涨跌异动报警配置
        price_alert_cfg = cfg.get("price_alert", {}) or {}
        self.price_alert_enabled = bool(price_alert_cfg.get("enabled", False))  # 全局开关
        # 多规则列表：[{"period": int, "threshold": float, "cooldown": int}, ...]
        rules_cfg = price_alert_cfg.get("rules", None)
        if isinstance(rules_cfg, list) and rules_cfg:
            self.price_alert_rules = []
            for r in rules_cfg:
                try:
                    self.price_alert_rules.append({
                        "period": max(1, int(r.get("period", 60))),
                        "threshold": max(0.1, float(r.get("threshold", 2.0))),
                        "cooldown": max(1, int(r.get("cooldown", 120))),
                    })
                except Exception:
                    pass
        else:
            # 兼容旧单规则配置
            self.price_alert_rules = [{
                "period": max(1, int(price_alert_cfg.get("period", 60))),
                "threshold": max(0.1, float(price_alert_cfg.get("threshold", 2.0))),
                "cooldown": max(1, int(price_alert_cfg.get("cooldown", 120))),
            }]
        # 价格历史：{code: deque([(timestamp, price), ...])}
        self._price_history = {}
        # 冷却记录：{(code, rule_index): last_fire_timestamp}
        self._price_alert_cooldowns = {}

        # 新高新低报警配置
        nhl_cfg = cfg.get("new_high_low_alert", {}) or {}
        self.new_high_low_alert_enabled = bool(nhl_cfg.get("enabled", False))
        self.new_high_alert = bool(nhl_cfg.get("new_high", True))  # 新高报警开关
        self.new_low_alert = bool(nhl_cfg.get("new_low", True))   # 新低报警开关
        self.new_high_low_cooldown = max(1, int(nhl_cfg.get("cooldown", 60)))  # 冷却秒数
        # 状态追踪：{code: {"high": last_known_high, "low": last_known_low}}
        self._nhl_last_known = {}
        # 冷却记录：{(code, "high"/"low"): last_fire_timestamp}
        self._nhl_cooldowns = {}

        # 涨跌停通知配置
        limit_alert_cfg = cfg.get("limit_alert", {}) or {}
        self.limit_alert_enabled = bool(limit_alert_cfg.get("enabled", False))  # 全局开关
        self.limit_alert_reach_up = bool(limit_alert_cfg.get("reach_up", True))  # 到达涨停通知
        self.limit_alert_reach_down = bool(limit_alert_cfg.get("reach_down", True))  # 到达跌停通知
        self.limit_alert_leave_up = bool(limit_alert_cfg.get("leave_up", True))  # 离开涨停通知
        self.limit_alert_leave_down = bool(limit_alert_cfg.get("leave_down", True))  # 离开跌停通知
        self.limit_alert_cooldown = max(1, int(limit_alert_cfg.get("cooldown", 30)))  # 冷却秒数
        # 状态追踪：{code: {"is_limit_up": bool, "is_limit_down": bool}}
        self._limit_alert_state = {}
        # 冷却记录：{(code, "reach_up"/"reach_down"/"leave_up"/"leave_down"): last_fire_timestamp}
        self._limit_alert_cooldowns = {}

        # 设置初值：自选 codes / checked_codes / 名称（SQLite 优先）
        self._load_watchlist_or_migrate(codes_cfg, checked_codes_cfg)
        # 列标题列表（提前定义，供后续旧配置解析使用）
        self.ALL_HEADERS = ["代码", "名称", "现价", "涨跌值", "涨跌幅", "盈亏", "买一", "卖一", "委比", "成交量", "成交额", "均价", "日高", "日低", "K线"]

        # 列显示标志（独立属性）
        # 解析旧 flags 配置以做回退
        old_flags = {}
        if isinstance(flags_cfg, list):
            for i, h in enumerate(self.ALL_HEADERS):
                old_flags[h] = bool(flags_cfg[i]) if i < len(flags_cfg) else False
        elif isinstance(flags_cfg, dict):
            for h in self.ALL_HEADERS:
                old_flags[h] = bool(flags_cfg.get(h, False))

        # 新：为每一列创建独立的 bool 属性（优先读取新配置，否则回退到 old_flags）
        self.code_visible = bool(cfg.get("code_visible", old_flags.get("代码", False)))
        self.name_visible = bool(cfg.get("name_visible", old_flags.get("名称", False)))
        self.price_visible = bool(cfg.get("price_visible", old_flags.get("现价", False)))
        self.change_visible = bool(cfg.get("change_visible", old_flags.get("涨跌值", False)))
        self.change_pct_visible = bool(cfg.get("change_pct_visible", old_flags.get("涨跌幅", False)))
        # 买一/卖一 使用单一开关 b1s1_visible（用户要求不要拆分控制）
        self.b1s1_visible = bool(cfg.get("b1s1_visible", (old_flags.get("买一", False) or old_flags.get("卖一", False))))
        self.commi_visible = bool(cfg.get("commi_visible", old_flags.get("委比", False)))
        self.vol_visible = bool(cfg.get("vol_visible", old_flags.get("成交量", False)))
        self.amount_visible = bool(cfg.get("amount_visible", old_flags.get("成交额", False)))
        self.avg_visible = bool(cfg.get("avg_visible", old_flags.get("均价", False)))
        self.high_visible = bool(cfg.get("high_visible", old_flags.get("日高", False)))
        self.low_visible = bool(cfg.get("low_visible", old_flags.get("日低", False)))
        self.kline_visible = bool(cfg.get("kline_visible", old_flags.get("K线", False)))
        self.pnl_visible = bool(cfg.get("pnl_visible", False))

        # 简易模式列显示标志
        simple_cfg = cfg.get("simple_flags", {})
        self.simple_code_visible = bool(simple_cfg.get("代码", False))
        self.simple_name_visible = bool(simple_cfg.get("名称", True))
        self.simple_price_visible = bool(simple_cfg.get("现价", True))
        self.simple_change_visible = bool(simple_cfg.get("涨跌值", False))
        self.simple_change_pct_visible = bool(simple_cfg.get("涨跌幅", True))
        self.simple_b1s1_visible = bool(simple_cfg.get("买一", False))
        self.simple_commi_visible = bool(simple_cfg.get("委比", False))
        self.simple_vol_visible = bool(simple_cfg.get("成交量", False))
        self.simple_amount_visible = bool(simple_cfg.get("成交额", False))
        self.simple_avg_visible = bool(simple_cfg.get("均价", False))
        self.simple_high_visible = bool(simple_cfg.get("日高", False))
        self.simple_low_visible = bool(simple_cfg.get("日低", False))
        self.simple_kline_visible = bool(simple_cfg.get("K线", False))
        self.simple_pnl_visible = bool(simple_cfg.get("盈亏", False))

        self.font = QFont(font_family, max(8, min(15, font_size)))
        self.bg = QColor(bg["r"],bg["g"],bg["b"],bg["a"])
        
        
        self.hotkey_triggered.connect(self.toggle_win)
        self._register_hotkey()

        # UI
        self.panel = QWidget(self)
        self.panel.setObjectName("panel")
        self.vbox = QVBoxLayout(self.panel)
        self.vbox.setContentsMargins(10,6,10,6)
        self.vbox.setSpacing(0)

        self.table = QTableView(self.panel)
        self.table.setFrameShape(QFrame.NoFrame)
        self.table.setShowGrid(False)
        # 1. 修改原有设置，允许接收鼠标点击
        self.table.setFocusPolicy(Qt.ClickFocus)
        # 2. 把 NoSelection 改为 SingleSelection (允许选中，否则 clicked 信号很难触发)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # 3. 还有一个隐藏设置：确保点击时选中整行，而不是零散的单元格
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setVisible(self.header_visible)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setFont(self.font)
        self.table.horizontalHeader().setFont(self.font)
        self.table.verticalHeader().setMinimumSectionSize(1)
        self.table.verticalHeader().setDefaultSectionSize(1)
        self.table.horizontalHeader().setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.table.setTextElideMode(Qt.ElideNone)
        self.table.setItemDelegate(NoSelectionDelegate())

        # 获取表格当前的调色板
        palette = self.table.palette()

        # 将“选中状态的背景色”设置为完全透明
        palette.setColor(QPalette.Highlight, QColor(0, 0, 0, 0))

        # 将“选中状态的字体颜色”设置为与普通文字颜色一致 (防止反色)
        palette.setColor(QPalette.HighlightedText, palette.color(QPalette.Text))
        
        # 应用这个新的调色板
        self.table.setPalette(palette)
        # 3. 连接信号
        self.table.clicked.connect(self._on_table_clicked)
        self.error_label = QLabel("", self.panel)
        self.error_label.setStyleSheet("color: #ff6666; padding: 2px 4px;")
        self.error_label.setVisible(False)
        self.vbox.addWidget(self.error_label)

        self.model = SimpleTableModel(headers=self.ALL_HEADERS, align_right_cols=[1,2,3,4,5])
        self.model.set_color_scheme(self.fg, self.up_color, self.down_color)
        self.table.setModel(self.model)

        self.k_delegate = KLineDelegate(self.table, base_pt=12)
        self.k_delegate.update_scheme(self.fg, self.up_color, self.down_color)
        self.k_delegate.set_point_size(self.font.pointSize())
        self.k_column_visible_index = None

        self.vbox.addWidget(self.table)

        for w in (self.panel, self.table, self.table.viewport(), self.table.horizontalHeader(), self.table.verticalHeader()):
            w.installEventFilter(self)

        # 初始化期间禁用锚点重定位，避免在宽度尚未稳定时被错误修正位置
        self._anchor_active = False

        self.apply_style()
        self.set_window_opacity_percent(self.opacity_pct)
        self._fit_to_contents()

        scr = QApplication.primaryScreen().availableGeometry()
        pos = cfg.get("pos")
        # 待初始化结束、宽度稳定后再做屏幕钛制（避免 self.width() 不准导致 x 被错误拽回）
        self._pending_pos = None
        if isinstance(pos, dict) and "x" in pos and "y" in pos:
            x, y = int(pos["x"]), int(pos["y"])
            self.move(x, y)
            self._pending_pos = (x, y)
        else:
            self.move(scr.right()-self.width()-40, scr.bottom()-self.height()-80)

        self._drag_pos = None

        self.timer = QTimer(self)
        self.timer.setInterval(max(1, self.refresh_seconds)*1000)
        self.timer.timeout.connect(self._refresh_from_function)
        self.timer.start()
        self._refresh_from_function()
        self._defer_fit()

        # 初始化完成：启用锚点重定位（后续指标变化才会按锚点调整）
        self._anchor_active = True

        # 宽度稳定后才对加载的 pos 做屏幕钛制，确保窗口可见且不被错误拽回
        QTimer.singleShot(0, self._clamp_pending_pos)

        # 定时器周期性确保窗口置顶（跨平台，使用 Qt flags）
        self._keep_top_timer = QTimer(self)
        self._keep_top_timer.setInterval(1000)  # 每 1000ms 检查一次
        self._keep_top_timer.timeout.connect(self._ensure_on_top)
        self._keep_top_timer.start()

    def _on_table_clicked(self, index):
        modifiers = QApplication.keyboardModifiers()
        col = index.column()

        if (modifiers & Qt.ControlModifier) and (col == 0):
            rows = index.row()
            code = self.checked_codes[rows]
            url = self._get_xueqiu_url(code)
            print(url)
            webbrowser.open(url)
        

    def _get_sina_url(self, code):
        # 1. A 股股票 (sh/sz) -> 标准行情页
        if code.startswith(('sh', 'sz')) and len(code) >= 6 and not (code.startswith(('sh5', 'sz15', 'sz16'))):
            return f"https://finance.sina.com.cn/realstock/company/{code}/nc.shtml"

        # 2. 基金/ETF/LOF (sh5, sz15, sz16) -> 基金详情页
        if code.startswith(('sh5', 'sz15', 'sz16')):
            pure_code = code[2:] 
            return f"https://finance.sina.com.cn/fund/quotes/{pure_code}/bc.shtml"
        
        # 3. 外汇 (fx_) -> 货币详情页
        if code.startswith('fx_'):
            fx_code = code.replace('fx_s', '').replace('fx_', '').upper()
            return f"https://finance.sina.com.cn/money/forex/hq/{fx_code}.shtml"

        # 4. 期货 (hf_ / nf_) -> 期货详情页
        if code.startswith(('hf_', 'nf_')):
            f_code = code.split('_')[1].upper()
            return f"https://finance.sina.com.cn/futures/quotes/{f_code}.shtml"

        # 5. 全球指数 (b_...) -> 使用你刚才发现的正确路径
        if code.startswith('b_'):
            # 移除 b_ 前缀并转大写，例如 b_kospi -> KOSPI, b_nky -> NKY
            idx_code = code.replace('b_', '').upper()
            return f"https://finance.sina.com.cn/stock/globalindex/quotes/{idx_code}"

        # 6. 兜底逻辑：所有未匹配品种 -> 调用官方搜索页
        search_code = code.replace('b_', '').replace('hf_', '').replace('nf_', '').replace('fx_', '')
        return f"https://search.sina.com.cn/?q={search_code}"
    
    def _get_xueqiu_url(self, code):
        """
        将各类资产代码转换为雪球 URL
        """
        # 1. A 股 / ETF / LOF (sh/sz/bj 开头)
        # 雪球规则：直接拼 SH/SZ + 代码，大写即可 (如 SH600519)
        if code.startswith(('sh', 'sz', 'bj')):
            return f"https://xueqiu.com/S/{code.upper()}"
        
        # 2. 港股 (rt_hk 开头)
        # 雪球规则：HK + 代码 (如 HK00700)
        if code.startswith('rt_hk'):
            hk_code = code.replace('rt_hk', '').upper()
            return f"https://xueqiu.com/S/{hk_code}"
        
        # 3. 美股 (gb_ 开头)
        # 雪球规则：直接用代码 (如 AAPL)
        if code.startswith('gb_'):
            us_code = code.replace('gb_', '').upper()
            return f"https://xueqiu.com/S/{us_code}"
        
        # 4. 全球指数 (b_ 开头) 新浪接口
        if code.startswith('b_'):
            # 移除 b_ 前缀并转大写，例如 b_kospi -> KOSPI, b_nky -> NKY
            idx_code = code.replace('b_', '').upper()
            return f"https://finance.sina.com.cn/stock/globalindex/quotes/{idx_code}"
        
       # 3. 外汇 (fx_) -> 新浪接口
        if code.startswith('fx_'):
            fx_code = code.replace('fx_s', '').replace('fx_', '').upper()
            return f"https://finance.sina.com.cn/money/forex/hq/{fx_code}.shtml"

        # 4. 期货 (hf_ / nf_) -> 新浪接口
        if code.startswith(('hf_', 'nf_')):
            f_code = code.split('_')[1].upper()
            return f"https://finance.sina.com.cn/futures/quotes/{f_code}.shtml"


    def _load_watchlist_or_migrate(self, codes_cfg, checked_codes_cfg):
        """从 SQLite 加载自选；若为空则从 JSON 配置迁移并落库。"""
        try:
            loaded = self._quote_db.load_watchlist()
            db_codes, db_checked, db_names = loaded[0], loaded[1], loaded[2]
            db_points = loaded[3] if len(loaded) > 3 else {}
        except Exception:
            db_codes, db_checked, db_names, db_points = [], [], {}, {}

        if db_codes:
            self.codes = list(db_codes)
            self.code_names = dict(db_names or {})
            code_set = set(self.codes)
            self.checked_codes = [c for c in (db_checked or []) if c in code_set] or list(self.codes)
            self.trade_points = {
                k: v for k, v in (db_points or {}).items() if k in code_set
            }
            return

        # JSON → SQLite 一次性迁移
        self.codes, self.code_names = self._parse_codes_cfg(codes_cfg)
        checked_list, checked_names = self._parse_codes_cfg(checked_codes_cfg)
        for k, v in checked_names.items():
            if v and k not in self.code_names:
                self.code_names[k] = v
        code_set = set(self.codes)
        self.checked_codes = [c for c in checked_list if c in code_set]
        if not self.codes:
            self.codes = ["sh000001"]
        if not self.checked_codes:
            self.checked_codes = list(self.codes)
        self.trade_points = {}
        self._persist_watchlist()

    def _persist_watchlist(self):
        """将当前 codes / checked_codes / 名称 / 买卖点写入 SQLite。"""
        try:
            self._quote_db.save_watchlist(
                self.codes,
                self.checked_codes,
                self.code_names,
                getattr(self, "trade_points", None) or {},
            )
        except Exception:
            pass

    # 与 App 连接
    def set_open_settings_callback(self, fn): 
        self._open_settings_cb = fn

    def set_on_change(self, fn): 
        self._on_change = fn or (lambda: None)

    def _notify_change(self):
        cb = getattr(self, "_on_change", None)
        if callable(cb): cb()

    @staticmethod
    def _parse_code_entry(entry):
        """解析单条自选：支持字符串或 {"code","name"}，返回 (code, name)。"""
        if isinstance(entry, dict):
            code = str(entry.get("code", "")).strip()
            name = str(entry.get("name", "") or "").strip()
            return code, name
        return str(entry).strip(), ""

    def _parse_codes_cfg(self, cfg_list):
        """解析 codes/checked_codes 配置，返回小写 codes 与名称映射。"""
        codes = []
        names = {}
        seen = set()
        if not isinstance(cfg_list, list):
            return codes, names
        for entry in cfg_list:
            code, name = self._parse_code_entry(entry)
            if not code:
                continue
            key = code.lower()
            if key not in seen:
                seen.add(key)
                codes.append(key)
            if name:
                names[key] = name
        return codes, names

    def current_config(self):
        return {
            "code_visible": bool(getattr(self, 'code_visible', False)),
            "name_visible": bool(getattr(self, 'name_visible', False)),
            "price_visible": bool(getattr(self, 'price_visible', False)),
            "change_visible": bool(getattr(self, 'change_visible', False)),
            "change_pct_visible": bool(getattr(self, 'change_pct_visible', False)),
            "b1s1_visible": bool(getattr(self, 'b1s1_visible', False)),
            "commi_visible": bool(getattr(self, 'commi_visible', False)),
            "vol_visible": bool(getattr(self, 'vol_visible', False)),
            "amount_visible": bool(getattr(self, 'amount_visible', False)),
            "avg_visible": bool(getattr(self, 'avg_visible', False)),
            "high_visible": bool(getattr(self, 'high_visible', False)),
            "low_visible": bool(getattr(self, 'low_visible', False)),
            "kline_visible": bool(getattr(self, 'kline_visible', False)),
            "pnl_visible": bool(getattr(self, 'pnl_visible', False)),
            "cost_data": dict(getattr(self, 'cost_data', {}) or {}),
            "alert_data": dict(getattr(self, 'alert_data', {}) or {}),
            "short_code": self.short_code,
            "name_length": self.name_length,
            "b1s1_price": (getattr(self, 'b1s1_display', 'qty') == 'price'),
            "b1s1_display": getattr(self, 'b1s1_display', 'qty'),
            "header_visible": self.header_visible,
            "grid_visible": self.grid_visible,
            "refresh_seconds": self.refresh_seconds,
            "fg": self.fg.name(QColor.HexRgb),
            "bg": {"r": self.bg.red(), "g": self.bg.green(), "b": self.bg.blue(), "a": self.bg.alpha()},
            "opacity_pct": int(round(self.windowOpacity()*100)),
            "font_family": self.font.family(),
            "font_size": self.font.pointSize(),
            "line_extra_px": self.line_extra_px,
            "up_color": self.up_color.name(QColor.HexRgb),
            "down_color": self.down_color.name(QColor.HexRgb),
            "grid_alpha_pct": int(self.grid_alpha_pct),
            "header_alpha_pct": int(self.header_alpha_pct),
            "pos": {"x": self.x(), "y": self.y()},
            "hotkey": self.hotkey,
            "start_on_boot": bool(self.start_on_boot),
            "anchor": self.anchor,
            "sym_high": self.sym_high,
            "sym_low": self.sym_low,
            "sym_limit_up": self.sym_limit_up,
            "sym_limit_down": self.sym_limit_down,
            "sym_rise": self.sym_rise,
            "sym_fall": self.sym_fall,
            "dual_mode_enabled": bool(self.dual_mode_enabled),
            "leave_delay_ms": int(self.leave_delay_ms),
            "manual_mode": str(self.manual_mode),
            "simple_flags": {
                "代码": bool(self.simple_code_visible),
                "名称": bool(self.simple_name_visible),
                "现价": bool(self.simple_price_visible),
                "涨跌值": bool(self.simple_change_visible),
                "涨跌幅": bool(self.simple_change_pct_visible),
                "买一": bool(self.simple_b1s1_visible),
                "委比": bool(self.simple_commi_visible),
                "成交量": bool(self.simple_vol_visible),
                "成交额": bool(self.simple_amount_visible),
                "均价": bool(self.simple_avg_visible),
                "日高": bool(self.simple_high_visible),
                "日低": bool(self.simple_low_visible),
                "K线": bool(self.simple_kline_visible),
                "盈亏": bool(self.simple_pnl_visible),
            },
            "price_alert": {
                "enabled": bool(self.price_alert_enabled),
                "rules": list(self.price_alert_rules),
            },
            "new_high_low_alert": {
                "enabled": bool(self.new_high_low_alert_enabled),
                "new_high": bool(self.new_high_alert),
                "new_low": bool(self.new_low_alert),
                "cooldown": int(self.new_high_low_cooldown),
            },
            "limit_alert": {
                "enabled": bool(self.limit_alert_enabled),
                "reach_up": bool(self.limit_alert_reach_up),
                "reach_down": bool(self.limit_alert_reach_down),
                "leave_up": bool(self.limit_alert_leave_up),
                "leave_down": bool(self.limit_alert_leave_down),
                "cooldown": int(self.limit_alert_cooldown),
            },
        }

    def header_is_visible(self, header: str) -> bool:
        """返回指定列标题对应的独立可见属性值（替代旧的 flags 字典）。"""
        try:
            if header == "代码":
                return bool(getattr(self, 'code_visible', False))
            if header == "名称":
                return bool(getattr(self, 'name_visible', False))
            if header == "现价":
                return bool(getattr(self, 'price_visible', False))
            if header == "涨跌值":
                return bool(getattr(self, 'change_visible', False))
            if header == "涨跌幅":
                return bool(getattr(self, 'change_pct_visible', False))
            if header in ("买一", "卖一"):
                return bool(getattr(self, 'b1s1_visible', False))
            if header == "委比":
                return bool(getattr(self, 'commi_visible', False))
            if header == "成交量":
                return bool(getattr(self, 'vol_visible', False))
            if header == "成交额":
                return bool(getattr(self, 'amount_visible', False))
            if header == "均价":
                return bool(getattr(self, 'avg_visible', False))
            if header == "日高":
                return bool(getattr(self, 'high_visible', False))
            if header == "日低":
                return bool(getattr(self, 'low_visible', False))
            if header == "K线":
                return bool(getattr(self, 'kline_visible', False))
            if header == "盈亏":
                return bool(getattr(self, 'pnl_visible', False))
        except Exception:
            pass
        return False

    # ----- 双模式切换：活跃指标可见性 -----
    def _active_header_is_visible(self, header: str) -> bool:
        """根据当前双模式状态、鼠标悬浮状态及手动模式返回应当显示的列可见性。
        - dual_mode_enabled=True + 悬浮: 用正常模式
        - dual_mode_enabled=True + 未悬浮: 用简易模式
        - dual_mode_enabled=False: 由 manual_mode 决定（normal=正常模式, simple=简易模式）
        """
        if self.dual_mode_enabled:
            if self._is_hovered:
                return self.header_is_visible(header)
            # 自动模式下未悬浮 -> 简易模式
        else:
            # 手动模式
            if self.manual_mode != "simple":
                return self.header_is_visible(header)
        # 简易模式
        try:
            if header == "代码":
                return bool(self.simple_code_visible)
            if header == "名称":
                return bool(self.simple_name_visible)
            if header == "现价":
                return bool(self.simple_price_visible)
            if header == "涨跌值":
                return bool(self.simple_change_visible)
            if header == "涨跌幅":
                return bool(self.simple_change_pct_visible)
            if header in ("买一", "卖一"):
                return bool(self.simple_b1s1_visible)
            if header == "委比":
                return bool(self.simple_commi_visible)
            if header == "成交量":
                return bool(self.simple_vol_visible)
            if header == "成交额":
                return bool(self.simple_amount_visible)
            if header == "均价":
                return bool(self.simple_avg_visible)
            if header == "日高":
                return bool(self.simple_high_visible)
            if header == "日低":
                return bool(self.simple_low_visible)
            if header == "K线":
                return bool(self.simple_kline_visible)
            if header == "盈亏":
                return bool(self.simple_pnl_visible)
        except Exception:
            pass
        return False

    def _on_leave_timeout(self):
        """500ms后确认鼠标确实已离开，切换到简易模式。"""
        if self.dual_mode_enabled and self._is_hovered:
            self._is_hovered = False
            self._refresh_from_function()

    # ----- 外观/尺寸 -----
    def apply_style(self):
        r,g,b,a = self.bg.red(), self.bg.green(), self.bg.blue(), self.bg.alpha()
        fg_r, fg_g, fg_b = self.fg.red(), self.fg.green(), self.fg.blue()
        g_alpha = int(round(self.grid_alpha_pct * 2.55))
        h_alpha = int(round(self.header_alpha_pct * 2.55))
        line_col = f"rgba({fg_r},{fg_g},{fg_b},{g_alpha})"
        header_col = f"rgba({fg_r},{fg_g},{fg_b},{h_alpha})"
        self.panel.setStyleSheet(f"""
            QWidget#panel {{
                background: rgba({r},{g},{b},{a});
                border-radius: 5px;
            }}
            QTableView {{
                background: transparent;
                border: {f"1px solid {line_col}" if self.grid_visible else "none"};
                border-radius: 3px;
                outline: none;
            }}
            QTableView::item {{
                border-right: {f"1px solid {line_col}" if self.grid_visible else "none"};
                border-bottom: {f"1px solid {line_col}" if self.grid_visible else "none"};
            }}
            QHeaderView {{
                background-color: transparent;
            }}
            QHeaderView::section {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {line_col};
                font-weight: 600;
                color: {header_col};
                padding: 0px 4px;
            }}
        """)
        self.table.setFont(self.font)
        self.table.horizontalHeader().setFont(self.font)
        self._defer_fit()

    def _apply_row_heights(self):
        fm = self.table.fontMetrics()
        h = fm.height() + max(0, self.line_extra_px)
        self.table.verticalHeader().setDefaultSectionSize(h)
        for r in range(self.model.rowCount()):
            self.table.setRowHeight(r, h)
        # 表头行高与数据行一致
        self.table.horizontalHeader().setFixedHeight(h)

    def _fit_to_contents(self):
        # 记录调整尺寸前的左右边界，用于按锚点重新定位
        old_left = self.x()
        old_right = self.x() + self.width()

        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.resizeColumnsToContents()
        self._apply_row_heights()

        cols = self.model.columnCount()
        rows = self.model.rowCount()
        total_w = self.table.verticalHeader().width() + 2*self.table.frameWidth()
        for c in range(cols): 
            total_w += self.table.columnWidth(c)
        hh = self.table.horizontalHeader().height() if self.table.horizontalHeader().isVisible() else 0
        total_h = hh + 2*self.table.frameWidth()
        for r in range(rows): 
            total_h += self.table.rowHeight(r)
        self.table.setFixedSize(max(1,total_w), max(1,total_h))
        self.panel.adjustSize()
        self.resize(self.panel.size())

        # 按锚点保持对齐：right 保持右边不变，left 保持左边不变（默认即不变）
        # 仅在初始化完成后生效，避免重启后位置还原被这里错误修正
        if not getattr(self, '_anchor_active', False):
            return
        anchor = getattr(self, 'anchor', 'left')
        if anchor == 'right':
            new_x = old_right - self.width()
            try:
                # 使用窗口当前所在屏幕的可用区域，避免多屏幕下被拽回主屏
                ref_point = QPoint(new_x + self.width() // 2, self.y() + self.height() // 2)
                scr = self._screen_geometry_for(ref_point)
                new_x = max(scr.left(), min(new_x, scr.right() - self.width()))
            except Exception:
                pass
            if new_x != self.x():
                self.move(new_x, self.y())

    def _defer_fit(self):
        QTimer.singleShot(0, self._fit_to_contents)

    # ----- 数据 & 投影 -----
    def _show_error(self, msg: str):
        try:
            if self.k_column_visible_index is not None:
                self.table.setItemDelegateForColumn(self.k_column_visible_index, QStyledItemDelegate(self.table))
                self.k_column_visible_index = None
        except Exception:
            pass
        try:
            text = str(msg) if msg is not None else ""
            # 若是 requests 抛出的网络错误，显示更友好的中文提示
            if isinstance(msg, Exception):
                import requests as _req
                if isinstance(msg, _req.exceptions.RequestException):
                    text = "无网络连接"
        except Exception:
            text = str(msg)

        if hasattr(self, 'error_label'):
            self.error_label.setText(text)
            self.error_label.setVisible(True)
        self._defer_fit()

    def _clear_error(self):
        # 清除顶部错误提示
        if hasattr(self, 'error_label'):
            try:
                self.error_label.setVisible(False)
                self.error_label.setText("")
            except Exception:
                pass


    def _project_columns(self, full_rows, sign_data):
        # 从 ALL_HEADERS 中按显示顺序筛选已启用的列（使用双模式感知的可见性）
        cols = [i for i, h in enumerate(self.ALL_HEADERS) if self._active_header_is_visible(h)]
        headers = [self.ALL_HEADERS[i] for i in cols]

        proj_rows, proj_meta = [], []
        for r, row in enumerate(full_rows):
            proj_rows.append([row[i] for i in cols])
            proj_meta.append(sign_data[r])

        # 右对齐：除了名称、K线、卖一外的所有列都右对齐
        right_cols = [i for i, h in enumerate(headers) if h not in ("名称", "K线", "卖一")]
        self.model.set_align_right_cols(right_cols)
        self.model.set_rows_headers(proj_rows, headers, meta=proj_meta)
        self.model.set_color_scheme(self.fg, self.up_color, self.down_color)

        if "K线" in headers:
            col = headers.index("K线")
            self.k_column_visible_index = col
            self.k_delegate.update_scheme(self.fg, self.up_color, self.down_color)
            self.k_delegate.set_point_size(self.font.pointSize())
            self.table.setItemDelegateForColumn(col, self.k_delegate)
        else:
            if self.k_column_visible_index is not None:
                self.table.setItemDelegateForColumn(self.k_column_visible_index, QStyledItemDelegate(self.table))
                self.k_column_visible_index = None

        self._fit_to_contents()

    def _refresh_from_function(self):
        err = None
        try:
            price_data, sign_data, _tp, _hp, codes, pnls = self._get_price(self.checked_codes)
            items = []
            for i, code in enumerate(codes):
                row = price_data[i]
                name = str(row[1] or "") if isinstance(row, (list, tuple)) and len(row) > 1 else ""
                items.append((code, name, row, sign_data[i], pnls[i] if i < len(pnls) else None))
            self._quote_db.upsert_quotes(items)
        except Exception as e:
            err = e

        full_rows, sign, total_pnl, has_pnl = self._quote_db.load_quotes(self.checked_codes)
        if full_rows:
            try:
                self._clear_error()
            except Exception:
                pass
            self._apply_quote_rows(full_rows, sign, total_pnl, has_pnl)
            return

        if err is not None:
            try:
                import requests as _req
                if isinstance(err, _req.exceptions.RequestException):
                    self._show_error(_req.exceptions.RequestException())
                else:
                    self._show_error(str(err))
            except Exception:
                self._show_error(str(err))

    def _apply_quote_rows(self, full_rows, sign, total_pnl, has_pnl):
        """将行情行投影到表格，并更新托盘盈亏/ToolTip。"""
        self._project_columns(full_rows, sign)
        try:
            if callable(self._pnl_callback):
                self._pnl_callback(float(total_pnl), bool(has_pnl))
        except Exception:
            pass
        try:
            if callable(self._tooltip_callback):
                cols_idx = [i for i, h in enumerate(self.ALL_HEADERS)
                            if self.header_is_visible(h) and h != "K线"]
                if cols_idx and full_rows:
                    headers_text = [self.ALL_HEADERS[i] for i in cols_idx]
                    lines = ["\t".join(headers_text)]
                    for row in full_rows:
                        cells = []
                        for i in cols_idx:
                            v = row[i] if i < len(row) else ""
                            cells.append("" if isinstance(v, dict) else str(v))
                        lines.append("\t".join(cells))
                    self._tooltip_callback("\n".join(lines))
                else:
                    self._tooltip_callback("")
        except Exception:
            pass

    # ----- 应用设置 -----
    def set_codes(self, codes_list, *, notify=True, refresh=True):
        """更新自选代码。notify/refresh 可关，便于与 set_checked_codes 合并为一次写盘/拉行情。"""
        seen = set()
        new = []
        for c in codes_list:
            code, name = self._parse_code_entry(c)
            s = code.lower() if code else ""
            if s and s not in seen:
                seen.add(s)
                new.append(s)
                if name:
                    if not hasattr(self, "code_names") or self.code_names is None:
                        self.code_names = {}
                    self.code_names[s] = name
        if not new:
            new = ["sh000001"]
        if new == list(getattr(self, "codes", []) or []):
            return False
        self.codes = new
        # 清理已删除代码的名称缓存
        if getattr(self, "code_names", None):
            keep = set(new)
            self.code_names = {k: v for k, v in self.code_names.items() if k in keep or k.lower() in keep}
        # 勾选列表跟随自选裁剪
        keep = set(new)
        self.checked_codes = [c for c in (getattr(self, "checked_codes", []) or []) if c in keep]
        if not self.checked_codes:
            self.checked_codes = list(new)
        # 清理已删除股票的成本数据
        if self.cost_data:
            keep = set(new)
            self.cost_data = {k: v for k, v in self.cost_data.items() if k in keep}
        # 清理已删除股票的买卖点
        if getattr(self, "trade_points", None):
            keep = set(new)
            self.trade_points = {k: v for k, v in self.trade_points.items() if k in keep}
        # 清理已删除股票的封单预警数据
        if self.alert_data:
            keep = set(new)
            self.alert_data = {k: v for k, v in self.alert_data.items() if k in keep}
            self._alert_state = {k: v for k, v in self._alert_state.items() if k in keep}
        self._persist_watchlist()
        if notify:
            self._notify_change()
        if refresh:
            self._refresh_from_function()
        return True

    def set_checked_codes(self, codes_list, *, notify=True, refresh=True):
        """更新勾选代码。notify/refresh 可关，便于与 set_codes 合并为一次写盘/拉行情。"""
        seen = set()
        new = []
        for c in codes_list:
            code, name = self._parse_code_entry(c)
            s = code.lower() if code else ""
            if s and s not in seen:
                seen.add(s)
                new.append(s)
                if name:
                    if not hasattr(self, "code_names") or self.code_names is None:
                        self.code_names = {}
                    self.code_names[s] = name
        if not new:
            new = ["sh000001"]
        if new == list(getattr(self, "checked_codes", []) or []):
            return False
        self.checked_codes = new
        self._persist_watchlist()
        if notify:
            self._notify_change()
        if refresh:
            self._refresh_from_function()
        return True

    def set_code_names(self, name_map: dict):
        """更新代码→名称映射并写回 SQLite。"""
        if not hasattr(self, "code_names") or self.code_names is None:
            self.code_names = {}
        if not isinstance(name_map, dict):
            return
        for k, v in name_map.items():
            code = str(k).strip().lower()
            name = str(v or "").strip()
            if code and name:
                self.code_names[code] = name
        # 去掉已不在自选中的名称
        keep = set(getattr(self, "codes", []) or [])
        self.code_names = {k: v for k, v in self.code_names.items() if k in keep}
        self._persist_watchlist()
        self._notify_change()

    def get_code_name(self, code: str) -> str:
        name_map = getattr(self, "code_names", {}) or {}
        c = str(code or "").strip()
        return name_map.get(c) or name_map.get(c.lower()) or ""

    def set_flag(self, idx, checked: bool):
        """设置指标显示标志。idx 可以是整数索引（向后兼容）或列标题字符串"""
        # 兼容老版本：若传整数索引，转为列标题
        if isinstance(idx, int):
            if 0 <= idx < len(self.ALL_HEADERS):
                header = self.ALL_HEADERS[idx]
            else:
                return
        else:
            header = str(idx)
            if header not in self.ALL_HEADERS:
                return
        
        checked = bool(checked)
        prev = None
        try:
            if header == "代码":
                prev = bool(getattr(self, 'code_visible', False)); self.code_visible = checked
            elif header == "名称":
                prev = bool(getattr(self, 'name_visible', False)); self.name_visible = checked
            elif header == "现价":
                prev = bool(getattr(self, 'price_visible', False)); self.price_visible = checked
            elif header == "涨跌值":
                prev = bool(getattr(self, 'change_visible', False)); self.change_visible = checked
            elif header == "涨跌幅":
                prev = bool(getattr(self, 'change_pct_visible', False)); self.change_pct_visible = checked
            elif header in ("买一", "卖一"):
                prev = bool(getattr(self, 'b1s1_visible', False)); self.b1s1_visible = checked
            elif header == "委比":
                prev = bool(getattr(self, 'commi_visible', False)); self.commi_visible = checked
            elif header == "成交量":
                prev = bool(getattr(self, 'vol_visible', False)); self.vol_visible = checked
            elif header == "成交额":
                prev = bool(getattr(self, 'amount_visible', False)); self.amount_visible = checked
            elif header == "均价":
                prev = bool(getattr(self, 'avg_visible', False)); self.avg_visible = checked
            elif header == "日高":
                prev = bool(getattr(self, 'high_visible', False)); self.high_visible = checked
            elif header == "日低":
                prev = bool(getattr(self, 'low_visible', False)); self.low_visible = checked
            elif header == "K线":
                prev = bool(getattr(self, 'kline_visible', False)); self.kline_visible = checked
            elif header == "盈亏":
                prev = bool(getattr(self, 'pnl_visible', False)); self.pnl_visible = checked
        except Exception:
            prev = None

        if prev is None or prev == checked:
            # 如果状态没有变化仍然返回（避免额外刷新）
            if prev == checked:
                return
        self._notify_change()
        self._refresh_from_function()

    def set_code_type(self, pure_num: bool):
        self.short_code = bool(pure_num)
        self._notify_change()
        self._refresh_from_function()

    def set_name_length(self, name_len: int):
        if name_len >=0:
            self.name_length = name_len
            self._notify_change()
            self._refresh_from_function()

    def set_b1s1_display(self, mode: str):
        """mode: 'qty' | 'price' | 'both'"""
        if mode not in ("qty", "price", "both"):
            return
        self.b1s1_display = mode
        self._notify_change()
        self._refresh_from_function()

    def set_header_visible(self, vis: bool):
        self.header_visible = bool(vis)
        self.table.horizontalHeader().setVisible(self.header_visible)
        self._notify_change()
        self._defer_fit()

    def set_symbols(self, sym_high: str, sym_low: str, sym_limit_up: str, sym_limit_down: str,
                    sym_rise: str = None, sym_fall: str = None):
        """设置日高/日低/涨停/跌停/涨/跌符号"""
        self.sym_high = sym_high or "↑"
        self.sym_low = sym_low or "↓"
        self.sym_limit_up = sym_limit_up or "⇧"
        self.sym_limit_down = sym_limit_down or "⇩"
        if sym_rise is not None:
            self.sym_rise = sym_rise
        if sym_fall is not None:
            self.sym_fall = sym_fall
        self._notify_change()
        self._refresh_from_function()

    def _fmt_signed(self, value: float, decimals: int) -> str:
        """使用涨/跌符号格式化带符号数值。
        正值前缀 sym_rise，负值前缀 sym_fall，零值显示 sym_rise+0。"""
        if value > 0:
            return f"{self.sym_rise}{value:.{decimals}f}"
        elif value < 0:
            return f"{self.sym_fall}{abs(value):.{decimals}f}"
        else:
            return f"{self.sym_rise}{0:.{decimals}f}"

    @staticmethod
    def _fmt_lots(lots: int) -> str:
        """格式化手数：>=1亿显示X.X亿，>=1万显示X.X万，否则原数字。"""
        abs_lots = abs(lots)
        if abs_lots >= 100000000:
            return f"{lots/1e8:.1f}亿"
        elif abs_lots >= 10000:
            return f"{lots/1e4:.1f}万"
        else:
            return f"{lots}"

    def set_cost(self, code: str, cost: float, qty: int):
        """设置指定股票的持仓成本与数量。cost<=0 或 qty==0 时清除。"""
        try:
            key = str(code).strip().lower()
            if not key:
                return
            try:
                cost_f = float(cost)
            except Exception:
                cost_f = 0.0
            try:
                qty_i = int(qty)
            except Exception:
                qty_i = 0
            if cost_f > 0 and qty_i != 0:
                self.cost_data[key] = {"cost": cost_f, "qty": qty_i}
                # 首次设置成本时自动启用盈亏列显示
                if not getattr(self, 'pnl_visible', False):
                    self.pnl_visible = True
            else:
                self.cost_data.pop(key, None)
            self._notify_change()
            self._refresh_from_function()
        except Exception:
            pass

    def get_cost(self, code: str):
        """返回指定股票的成本数据 dict 或 None。"""
        try:
            return self.cost_data.get(str(code).strip().lower())
        except Exception:
            return None

    def set_trade_points(self, code: str, buy: float, sell: float):
        """设置指定股票的买入点/卖出点。两者均 <=0 时清除。"""
        try:
            key = str(code).strip().lower()
            if not key:
                return
            try:
                buy_f = float(buy)
            except Exception:
                buy_f = 0.0
            try:
                sell_f = float(sell)
            except Exception:
                sell_f = 0.0
            if not hasattr(self, "trade_points") or self.trade_points is None:
                self.trade_points = {}
            if buy_f > 0 or sell_f > 0:
                self.trade_points[key] = {
                    "buy": buy_f if buy_f > 0 else 0.0,
                    "sell": sell_f if sell_f > 0 else 0.0,
                }
            else:
                self.trade_points.pop(key, None)
            self._persist_watchlist()
        except Exception:
            pass

    def get_trade_points(self, code: str):
        """返回指定股票的买卖点 dict 或 None。"""
        try:
            return (getattr(self, "trade_points", None) or {}).get(
                str(code).strip().lower()
            )
        except Exception:
            return None

    def set_notifier_callback(self, fn):
        """设置预警通知回调 fn(title, msg)。"""
        self._notify_alert = fn

    def set_pnl_callback(self, fn):
        """设置总盈亏更新回调 fn(total_pnl: float, has_pnl: bool)。"""
        self._pnl_callback = fn

    def set_tooltip_callback(self, fn):
        """设置托盘 ToolTip 指标文本更新回调 fn(text: str)。"""
        self._tooltip_callback = fn

    def set_alert(self, code: str, thresholds: list):
        """设置指定股票的封单预警阈值列表（手数，正=涨停，负=跌停）。"""
        try:
            key = str(code).strip().lower()
            if not key:
                return
            cleaned = []
            for t in thresholds or []:
                try:
                    n = int(t)
                    if n != 0 and n not in cleaned:
                        cleaned.append(n)
                except Exception:
                    pass
            if cleaned:
                self.alert_data[key] = cleaned
                self._alert_state[key] = [False] * len(cleaned)
            else:
                self.alert_data.pop(key, None)
                self._alert_state.pop(key, None)
            self._notify_change()
        except Exception:
            pass

    def get_alert(self, code: str):
        """返回指定股票的预警阈值列表。"""
        try:
            return list(self.alert_data.get(str(code).strip().lower(), []))
        except Exception:
            return []


    def set_grid_visible(self, vis: bool):
        self.grid_visible = bool(vis)
        self.apply_style()
        self._notify_change()

    def set_refresh_interval(self, seconds: int):
        if seconds in {1,2,3,5,10,15,30,60}:
            self.refresh_seconds = seconds
            self.timer.setInterval(seconds*1000)
            self._notify_change()

    def set_fg_color(self, c: QColor):
        if isinstance(c, QColor) and c.isValid():
            self.fg = QColor(c)
            self.model.set_color_scheme(self.fg, self.up_color, self.down_color)
            self.k_delegate.update_scheme(self.fg, self.up_color, self.down_color)
            self.apply_style()
            self._notify_change()
            self._defer_fit()

    def set_up_color(self, c: QColor):
        if isinstance(c, QColor) and c.isValid():
            self.up_color = QColor(c)
            self.model.set_color_scheme(self.fg, self.up_color, self.down_color)
            self.k_delegate.update_scheme(self.fg, self.up_color, self.down_color)
            self.apply_style()
            self._notify_change()
            self._defer_fit()

    def set_down_color(self, c: QColor):
        if isinstance(c, QColor) and c.isValid():
            self.down_color = QColor(c)
            self.model.set_color_scheme(self.fg, self.up_color, self.down_color)
            self.k_delegate.update_scheme(self.fg, self.up_color, self.down_color)
            self.apply_style()
            self._notify_change()
            self._defer_fit()

    def reset_default_colors(self):
        """恢复涨/跌/表格颜色为默认值。"""
        self.up_color = QColor(DEFAULT_UP_COLOR)
        self.down_color = QColor(DEFAULT_DOWN_COLOR)
        self.fg = QColor(DEFAULT_TABLE_COLOR)
        self.model.set_color_scheme(self.fg, self.up_color, self.down_color)
        self.k_delegate.update_scheme(self.fg, self.up_color, self.down_color)
        self.apply_style()
        self._notify_change()
        self._defer_fit()

    def set_bg_rgb_keep_alpha(self, c: QColor):
        if isinstance(c, QColor) and c.isValid():
            c2 = QColor(c)
            c2.setAlpha(self.bg.alpha())
            self.bg = c2
            self.apply_style()
            self._notify_change()

    def set_bg_alpha_percent(self, percent_0_100: int):
        p = max(0, min(100, int(percent_0_100)))
        self.bg.setAlpha(int(round(p*2.55)))
        self.apply_style()
        self._notify_change()

    def set_window_opacity_percent(self, percent_20_100: int):
        p = max(20, min(100, int(percent_20_100)))
        self.setWindowOpacity(p/100.0)
        self._defer_fit()
        self._notify_change()

    def set_grid_alpha_percent(self, percent_0_100: int):
        """表格线/表头底边线的不透明度（0-100%）。"""
        self.grid_alpha_pct = max(0, min(100, int(percent_0_100)))
        self.apply_style()
        self._notify_change()

    def set_header_alpha_percent(self, percent_0_100: int):
        """表头文字的不透明度（0-100%）。"""
        self.header_alpha_pct = max(0, min(100, int(percent_0_100)))
        self.apply_style()
        self._notify_change()

    def set_font_size(self, pt: int):
        pt = max(MIN_FONT_SIZE, min(15, int(pt)))
        self.font.setPointSize(pt)
        self.k_delegate.set_point_size(pt)
        self.apply_style()
        self._notify_change()
        self.table.viewport().update()
        self._defer_fit()

    def set_font_family(self, family: str):
        if family and family != self.font.family():
            self.font.setFamily(family)
            self.apply_style()
            self._notify_change()

    def set_line_extra(self, px: int):
        self.line_extra_px = max(0, int(px))
        self.apply_style()
        self._defer_fit()
        self._notify_change()

    def set_start_on_boot(self, enabled: bool):
        self.start_on_boot = bool(enabled)
        self._notify_change()

    def set_anchor(self, anchor: str):
        """设置窗口锚点：'left' 保持左边对齐，'right' 保持右边对齐。
        切换时以当前窗口位置作为新锚点的基准，不立即移动窗口。"""
        if anchor not in ("left", "right"):
            return
        if anchor == self.anchor:
            return
        self.anchor = anchor
        self._notify_change()

    def set_dual_mode_enabled(self, enabled: bool):
        """启用或禁用双模式切换。"""
        self.dual_mode_enabled = bool(enabled)
        self._notify_change()
        self._refresh_from_function()

    def set_manual_mode(self, mode: str):
        """设置手动显示模式（仅当双模式自动切换关闭时生效）。
        mode: "normal" 或 "simple"。
        """
        mode = str(mode).lower()
        if mode not in ("normal", "simple"):
            return
        if mode == self.manual_mode:
            return
        self.manual_mode = mode
        self._notify_change()
        # 仅在自动切换关闭时立即刷新视图
        if not self.dual_mode_enabled:
            self._refresh_from_function()

    def set_leave_delay_ms(self, ms: int):
        """设置鼠标离开后切换简易模式的延迟时间(ms)。"""
        self.leave_delay_ms = max(0, int(ms))
        self._notify_change()

    def set_simple_flag(self, header: str, checked: bool):
        """设置简易模式下指定列的可见性。"""
        checked = bool(checked)
        if header == "代码":
            self.simple_code_visible = checked
        elif header == "名称":
            self.simple_name_visible = checked
        elif header == "现价":
            self.simple_price_visible = checked
        elif header == "涨跌值":
            self.simple_change_visible = checked
        elif header == "涨跌幅":
            self.simple_change_pct_visible = checked
        elif header in ("买一", "卖一"):
            self.simple_b1s1_visible = checked
        elif header == "委比":
            self.simple_commi_visible = checked
        elif header == "成交量":
            self.simple_vol_visible = checked
        elif header == "成交额":
            self.simple_amount_visible = checked
        elif header == "均价":
            self.simple_avg_visible = checked
        elif header == "日高":
            self.simple_high_visible = checked
        elif header == "日低":
            self.simple_low_visible = checked
        elif header == "K线":
            self.simple_kline_visible = checked
        elif header == "盈亏":
            self.simple_pnl_visible = checked
        else:
            return
        self._notify_change()
        self._refresh_from_function()

    def simple_header_is_visible(self, header: str) -> bool:
        """返回简易模式下指定列的可见性。"""
        try:
            if header == "代码":
                return bool(self.simple_code_visible)
            if header == "名称":
                return bool(self.simple_name_visible)
            if header == "现价":
                return bool(self.simple_price_visible)
            if header == "涨跌值":
                return bool(self.simple_change_visible)
            if header == "涨跌幅":
                return bool(self.simple_change_pct_visible)
            if header in ("买一", "卖一"):
                return bool(self.simple_b1s1_visible)
            if header == "委比":
                return bool(self.simple_commi_visible)
            if header == "成交量":
                return bool(self.simple_vol_visible)
            if header == "成交额":
                return bool(self.simple_amount_visible)
            if header == "均价":
                return bool(self.simple_avg_visible)
            if header == "日高":
                return bool(self.simple_high_visible)
            if header == "日低":
                return bool(self.simple_low_visible)
            if header == "K线":
                return bool(self.simple_kline_visible)
            if header == "盈亏":
                return bool(self.simple_pnl_visible)
        except Exception:
            pass
        return False

    # ----- 涨跌异动报警设置 -----
    def set_price_alert_enabled(self, enabled: bool):
        """启用/禁用涨跌异动报警。"""
        self.price_alert_enabled = bool(enabled)
        if not enabled:
            # 禁用时清空历史数据
            self._price_history.clear()
            self._price_alert_cooldowns.clear()
        self._notify_change()

    def set_price_alert_rules(self, rules: list):
        """设置涨跌异动报警规则列表。"""
        self.price_alert_rules = []
        for r in (rules or []):
            try:
                self.price_alert_rules.append({
                    "period": max(1, int(r.get("period", 60))),
                    "threshold": max(0.1, float(r.get("threshold", 2.0))),
                    "cooldown": max(1, int(r.get("cooldown", 120))),
                })
            except Exception:
                pass
        # 规则变化时清空历史和冷却状态
        self._price_history.clear()
        self._price_alert_cooldowns.clear()
        self._notify_change()

    def add_price_alert_rule(self, period: int, threshold: float, cooldown: int):
        """添加一条涨跌异动报警规则。"""
        self.price_alert_rules.append({
            "period": max(1, int(period)),
            "threshold": max(0.1, float(threshold)),
            "cooldown": max(1, int(cooldown)),
        })
        self._price_history.clear()
        self._price_alert_cooldowns.clear()
        self._notify_change()

    def remove_price_alert_rule(self, index: int):
        """删除指定索引的报警规则。"""
        if 0 <= index < len(self.price_alert_rules):
            self.price_alert_rules.pop(index)
            self._price_history.clear()
            self._price_alert_cooldowns.clear()
            self._notify_change()

    # ----- 新高新低报警设置 -----
    def set_new_high_low_alert_enabled(self, enabled: bool):
        """启用/禁用新高新低报警。"""
        self.new_high_low_alert_enabled = bool(enabled)
        if not enabled:
            self._nhl_last_known.clear()
            self._nhl_cooldowns.clear()
        self._notify_change()

    def set_new_high_alert(self, enabled: bool):
        """启用/禁用新高报警。"""
        self.new_high_alert = bool(enabled)
        self._notify_change()

    def set_new_low_alert(self, enabled: bool):
        """启用/禁用新低报警。"""
        self.new_low_alert = bool(enabled)
        self._notify_change()

    def set_new_high_low_cooldown(self, seconds: int):
        """设置新高新低报警冷却时间（秒）。"""
        self.new_high_low_cooldown = max(1, int(seconds))
        self._nhl_cooldowns.clear()
        self._notify_change()

    # ----- 涨跌停通知设置 -----
    def set_limit_alert_enabled(self, enabled: bool):
        """启用/禁用涨跌停通知。"""
        self.limit_alert_enabled = bool(enabled)
        if not enabled:
            self._limit_alert_state.clear()
            self._limit_alert_cooldowns.clear()
        self._notify_change()

    def set_limit_alert_reach_up(self, enabled: bool):
        """启用/禁用到达涨停通知。"""
        self.limit_alert_reach_up = bool(enabled)
        self._notify_change()

    def set_limit_alert_reach_down(self, enabled: bool):
        """启用/禁用到达跌停通知。"""
        self.limit_alert_reach_down = bool(enabled)
        self._notify_change()

    def set_limit_alert_leave_up(self, enabled: bool):
        """启用/禁用离开涨停通知。"""
        self.limit_alert_leave_up = bool(enabled)
        self._notify_change()

    def set_limit_alert_leave_down(self, enabled: bool):
        """启用/禁用离开跌停通知。"""
        self.limit_alert_leave_down = bool(enabled)
        self._notify_change()

    def set_limit_alert_cooldown(self, seconds: int):
        """设置涨跌停通知冷却时间（秒）。"""
        self.limit_alert_cooldown = max(1, int(seconds))
        self._limit_alert_cooldowns.clear()
        self._notify_change()

    # ----- 交互 -----
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        sub_cols = QMenu("显示指标", menu)
        for name in self.ALL_HEADERS:
            if name == "卖一":
                continue
            if name == "买一":
                act = QAction("买一/卖一", sub_cols, checkable=True)
                act.setChecked(self.header_is_visible("买一"))
                act.toggled.connect(partial(self.set_flag, "买一"))
                sub_cols.addAction(act)
                continue
            act = QAction(name, sub_cols, checkable=True)
            act.setChecked(self.header_is_visible(name))
            act.toggled.connect(partial(self.set_flag, name))
            sub_cols.addAction(act)
        menu.addMenu(sub_cols)

        act_header = QAction("显示表头", menu, checkable=True)
        act_header.setChecked(self.header_visible)
        act_header.toggled.connect(self.set_header_visible)
        menu.addAction(act_header)

        act_grid = QAction("显示网格",menu, checkable=True)
        act_grid.setChecked(self.grid_visible)
        act_grid.toggled.connect(self.set_grid_visible)
        menu.addAction(act_grid)

        act_dual = QAction("双模式切换", menu, checkable=True)
        act_dual.setChecked(self.dual_mode_enabled)
        act_dual.toggled.connect(self.set_dual_mode_enabled)
        menu.addAction(act_dual)

        # 手动模式选择：仅当双模式自动切换关闭时可用
        sub_mode = QMenu("当前显示模式", menu)
        sub_mode.setEnabled(not self.dual_mode_enabled)
        act_mode_normal = QAction("正常模式", sub_mode, checkable=True)
        act_mode_normal.setChecked(self.manual_mode == "normal")
        act_mode_normal.triggered.connect(lambda: self.set_manual_mode("normal"))
        sub_mode.addAction(act_mode_normal)
        act_mode_simple = QAction("简易模式", sub_mode, checkable=True)
        act_mode_simple.setChecked(self.manual_mode == "simple")
        act_mode_simple.triggered.connect(lambda: self.set_manual_mode("simple"))
        sub_mode.addAction(act_mode_simple)
        menu.addMenu(sub_mode)

        menu.addSeparator()
        act_open_settings = QAction("设置…", menu)
        act_open_settings.triggered.connect(self._open_settings_cb)
        menu.addAction(act_open_settings)

        menu.addSeparator()
        menu.addAction(QAction("隐藏浮窗", menu, triggered=self.hide))
        menu.exec(event.globalPos())

    def _pause_refresh(self):
        """拖动开始时暂停数据刷新，避免网络请求+重绘导致卡顿"""
        if self.timer and self.timer.isActive():
            self.timer.stop()

    def _resume_refresh(self):
        """拖动结束后恢复数据刷新"""
        if self.timer and not self.timer.isActive():
            self.timer.start()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._pause_refresh()
            self.setFocus(Qt.MouseFocusReason)
            self.is_dragging = True

    def mouseMoveEvent(self, e):
        if getattr(self, "_drag_pos", None) and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = None
            self.is_dragging = False
            self._resume_refresh()
            self._notify_change()
            self._check_edge_and_hide()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = None
            self.is_dragging = False
            self.hide()
            # 【核心安全锁】：隐藏后，立刻把贴边检查定时器停掉，防止它在后台报错
            if hasattr(self, 'edge_check_timer'):
                self.edge_check_timer.stop()

    def eventFilter(self, obj, ev):
        # 1. 双击逻辑保持不变 (这是最优先级的)
        if ev.type() == QEvent.MouseButtonDblClick and ev.button() == Qt.LeftButton:
            self._drag_pos = None
            self.is_dragging = False
            self.hide()
            return True

        # 2. 按下事件：只记录坐标，不拦截 (永远返回 False)
        if ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton:
            # 记录按下时的初始位置
            self._drag_start_pos = ev.globalPosition().toPoint()
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            
            self._pause_refresh()
            self.setFocus(Qt.MouseFocusReason)
            # 【关键】：返回 False，确保表格能收到点击事件，从而触发你的 Ctrl+点击
            return False

        # 3. 移动事件：这是区分“点击”和“拖动”的关键
        if ev.type() == QEvent.MouseMove and (ev.buttons() & Qt.LeftButton) and hasattr(self, "_drag_start_pos") and self._drag_start_pos:
            # 计算移动距离
            move_dist = (ev.globalPosition().toPoint() - self._drag_start_pos).manhattanLength()
            
            # 如果移动距离超过 5 像素，才认为是“拖动”，开始移动窗口
            if move_dist > 5:
                self.is_dragging = True
                self.move(ev.globalPosition().toPoint() - self._drag_pos)
                return True # 拖动时，拦截事件防止表格内容选中
            
            # 如果移动距离很小，返回 False，允许表格处理“拖动选择”
            return False

        # 4. 释放事件
        if ev.type() == QEvent.MouseButtonRelease and ev.button() == Qt.LeftButton:
            self._drag_start_pos = None
            self._drag_pos = None
            self.is_dragging = False
            self._resume_refresh()
            self._notify_change()
            self._check_edge_and_hide()
            return False # 释放时也放行，避免影响表格逻辑

        return QWidget.eventFilter(self, obj, ev)

    def closeEvent(self, event): 
        event.ignore()
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        if self.timer and not self.timer.isActive(): 
            self.timer.start()
        if self._keep_top_timer and not self._keep_top_timer.isActive():
            self._keep_top_timer.start()
        self._defer_fit()

    def hideEvent(self, event):
        super().hideEvent(event)
        # 隐藏后仍需继续刷新以保证托盘 ToolTip / 总盈亏灯泡及时更新，不停数据刷新定时器
        if self._keep_top_timer and self._keep_top_timer.isActive():
            self._keep_top_timer.stop()

    def _ensure_on_top(self):
        """跨平台置顶：利用 Qt.WindowStaysOnTopHint 保持窗口始终在最前。"""
        if not self.isVisible():
            return
        try:
            popup = QApplication.activePopupWidget()
            if popup is not None and popup is not self and not self.isAncestorOf(popup):
                return
        except Exception:
            pass
        # 通过 raise_() 确保置顶；flags 中已包含 WindowStaysOnTopHint
        self.raise_()

    def _register_hotkey(self):
        try:
            keyboard.remove_all_hotkeys()
        except Exception:
            pass
        keyboard.add_hotkey(self.hotkey.lower(), lambda: self.hotkey_triggered.emit())

    def update_hotkey(self, new_hotkey: str):
        self.hotkey = new_hotkey.strip()
        self._register_hotkey()

    def toggle_win(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()