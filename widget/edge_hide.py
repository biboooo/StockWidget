# -*- coding: utf-8 -*-
from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget


class EdgeHideMixin:
    def _check_edge_and_hide(self):
        try:
            screen = self.screen().availableGeometry()
        except Exception:
            screen = QApplication.primaryScreen().availableGeometry()
            
        curr_rect = self.geometry()
        
        # 1. 拦截条件
        if getattr(self, 'is_hidden_state', False):
            return
        if getattr(self, 'is_dragging', False) or not self.isVisible() or self.underMouse():
            return
            
        self.hide_direction = None
        
        # 2. 判断贴向哪边，并【强制计算】完美贴边坐标
        if curr_rect.top() <= screen.top() + self.edge_margin:
            self.hide_direction = 'top'
            # 弹出时：顶端紧贴屏幕顶端
            self.normal_pos = QPoint(curr_rect.left(), screen.top())
            self.hidden_pos = QPoint(curr_rect.left(), screen.top() - curr_rect.height() + self.expose_width)
            
        elif curr_rect.left() <= screen.left() + self.edge_margin:
            self.hide_direction = 'left'
            # 弹出时：左端紧贴屏幕左端
            self.normal_pos = QPoint(screen.left(), curr_rect.top())
            self.hidden_pos = QPoint(screen.left() - curr_rect.width() + self.expose_width, curr_rect.top())
            
        elif curr_rect.right() >= screen.right() - self.edge_margin:
            self.hide_direction = 'right'
            # 弹出时：右端紧贴屏幕右端（计算公式：屏幕右边缘 X坐标 - 窗口自身宽度）
            self.normal_pos = QPoint(screen.right() - curr_rect.width() + 1, curr_rect.top())
            self.hidden_pos = QPoint(screen.right() - self.expose_width, curr_rect.top())

        # 3. 执行隐藏动画
        if self.hide_direction:
            self.is_hidden_state = True
            self.anim.stop() 
            # 注意这里：用当前的实际位置作为起点，向隐藏位置移动
            self.anim.setStartValue(self.pos())
            self.anim.setEndValue(self.hidden_pos)
            self.anim.start()

    def enterEvent(self, event):
        """鼠标进入窗口：统一处理【贴边弹出】和【双模式切换】"""
        super().enterEvent(event)
        
        # ===============================
        # 1. 贴边弹出逻辑
        # ===============================
        if hasattr(self, 'edge_check_timer'):
            self.edge_check_timer.stop() # 停止检查贴边，防止乱跳
            
        if getattr(self, 'is_hidden_state', False) and getattr(self, 'normal_pos', None):
            self.anim.stop()
            # 注意：因为动画是 b"pos"，这里必须传当前坐标 (self.pos()) 和目标坐标
            self.anim.setStartValue(self.pos())
            self.anim.setEndValue(self.normal_pos)
            self.anim.start()
            self.is_hidden_state = False

        # ===============================
        # 2. 双模式切换逻辑
        # ===============================
        if getattr(self, 'dual_mode_enabled', False):
            # 取消待执行的延迟切换
            if hasattr(self, '_leave_timer') and self._leave_timer.isActive():
                self._leave_timer.stop()
            if not getattr(self, '_is_hovered', False):
                self._is_hovered = True
                self._refresh_from_function()

    def leaveEvent(self, event):
        """鼠标离开窗口：统一处理【贴边隐藏】和【双模式切换】"""
        super().leaveEvent(event)

        # ===============================
        # 1. 贴边隐藏逻辑
        # ===============================
        if hasattr(self, 'edge_check_timer'):
            self.edge_check_timer.start(500) 
            # 稍微延迟一下检查，给双模式一点反应时间
            QTimer.singleShot(100, self._check_edge_and_hide)

        # ===============================
        # 2. 双模式切换逻辑（与贴边隐藏解耦，避免异常打断 leaveEvent）
        # ===============================
        try:
            if getattr(self, 'dual_mode_enabled', False):
                delay = getattr(self, 'leave_delay_ms', 500)
                on_leave = getattr(self, '_on_leave_timeout', None)
                if not callable(on_leave):
                    return
                if delay > 0:
                    if not hasattr(self, '_leave_timer'):
                        self._leave_timer = QTimer(self)
                        self._leave_timer.setSingleShot(True)
                        self._leave_timer.timeout.connect(on_leave)
                    self._leave_timer.start(delay)
                else:
                    on_leave()
        except Exception:
            pass

    def _screen_geometry_for(self, point: QPoint):
        """返回指定点所在屏幕的可用几何；若不在任何屏幕内，返回主屏可用几何。
        用于多显示器场景下正确保存/还原位置。"""
        try:
            s = QGuiApplication.screenAt(point)
            if s is not None:
                return s.availableGeometry()
        except Exception:
            pass
        return QApplication.primaryScreen().availableGeometry()

    def _clamp_pending_pos(self):
        """初始化完成后对加载的位置做屏幕钛制。此时 self.width()/height() 已稳定。"""
        pending = getattr(self, '_pending_pos', None)
        if not pending:
            return
        self._pending_pos = None
        x, y = pending
        try:
            scr = self._screen_geometry_for(QPoint(x, y))
            new_x = max(scr.left(), min(x, scr.right() - self.width()))
            new_y = max(scr.top(), min(y, scr.bottom() - self.height()))
            if (new_x, new_y) != (self.x(), self.y()):
                self.move(new_x, new_y)
        except Exception:
            pass
