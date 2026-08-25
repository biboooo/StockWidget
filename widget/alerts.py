# -*- coding: utf-8 -*-
import time
from collections import deque


class AlertsMixin:
    def _fire_alert(self, title: str, msg: str):
        cb = getattr(self, '_notify_alert', None)
        if callable(cb):
            try:
                cb(title, msg)
            except Exception:
                pass

    def _check_seal_alerts(self, code, name, current_price, b1_price, s1_price,
                           b1_qty, s1_qty, limit_up, limit_down, dec):
        """封单预警状态机检测。进入涨/跌停且封单达阈值进入生效状态；
        封单跌破阈值或打开涨/跌停时触发通知并进入失效状态。"""
        key = (code or "").strip().lower()
        thresholds = self.alert_data.get(key)
        if not thresholds:
            return
        state = self._alert_state.get(key)
        if not state or len(state) != len(thresholds):
            state = [False] * len(thresholds)
            self._alert_state[key] = state

        is_limit_up = (limit_up is not None and
                       round(current_price, dec) == limit_up and
                       b1_price > 0 and round(b1_price, dec) == limit_up)
        is_limit_down = (limit_down is not None and
                         round(current_price, dec) == limit_down and
                         s1_price > 0 and round(s1_price, dec) == limit_down)

        seal_up_lots = int(b1_qty / 100) if is_limit_up else 0
        seal_down_lots = int(s1_qty / 100) if is_limit_down else 0

        for i, t in enumerate(thresholds):
            if t > 0:
                # 涨停预警
                if not state[i]:
                    if is_limit_up and seal_up_lots >= t:
                        state[i] = True
                else:
                    if not is_limit_up or seal_up_lots < t:
                        state[i] = False
                        if not is_limit_up:
                            title = f"{name} 打开涨停"
                            msg = f"{code} 预警阈值 {t}手：已脱离涨停"
                        else:
                            title = f"{name} 涨停封单跌破 {t}手"
                            msg = f"{code} 当前封单 {seal_up_lots}手 < {t}手"
                        self._fire_alert(title, msg)
            elif t < 0:
                # 跌停预警：阈值以绝对值比较
                req = -t
                if not state[i]:
                    if is_limit_down and seal_down_lots >= req:
                        state[i] = True
                else:
                    if not is_limit_down or seal_down_lots < req:
                        state[i] = False
                        if not is_limit_down:
                            title = f"{name} 打开跌停"
                            msg = f"{code} 预警阈值 {t}手：已脱离跌停"
                        else:
                            title = f"{name} 跌停封单跌破 {req}手"
                            msg = f"{code} 当前封单 {seal_down_lots}手 < {req}手"
                        self._fire_alert(title, msg)

    def _check_price_alert(self, code, name, current_price, prev_close):
        """涨跌异动报警：对每条规则独立检测，在配置的周期内若价格波动超过阈值则发出通知。"""
        if not self.price_alert_enabled:
            return
        if current_price <= 0 or prev_close <= 0:
            return
        if not self.price_alert_rules:
            return

        key = (code or "").strip().lower()
        now = time.time()

        # 记录价格历史（统一维护，保留最大周期所需数据）
        if key not in self._price_history:
            self._price_history[key] = deque()

        history = self._price_history[key]
        history.append((now, current_price))

        # 清除超出所有规则最大周期的老数据
        max_period = max(r["period"] for r in self.price_alert_rules)
        cutoff = now - max_period
        while history and history[0][0] < cutoff:
            history.popleft()

        # 对每条规则独立检测
        for rule_idx, rule in enumerate(self.price_alert_rules):
            period = rule["period"]
            threshold = rule["threshold"]
            cooldown = rule["cooldown"]

            # 找到该规则周期内最早的价格
            rule_cutoff = now - period
            base_price = None
            for ts, price in history:
                if ts >= rule_cutoff:
                    base_price = price
                    break

            if base_price is None or base_price <= 0:
                continue

            # 需要至少有两个数据点
            if base_price == current_price:
                continue

            # 计算周期内涨跌幅
            change_pct = abs((current_price - base_price) / base_price) * 100

            if change_pct >= threshold:
                # 检查冷却
                cd_key = (key, rule_idx)
                last_fired = self._price_alert_cooldowns.get(cd_key, 0)
                if now - last_fired < cooldown:
                    continue

                # 触发报警
                self._price_alert_cooldowns[cd_key] = now
                direction = "涨" if current_price > base_price else "跌"
                actual_pct = (current_price - base_price) / base_price * 100
                title = f"{name} 涨跌异动"
                msg = (f"{code} {period}秒内"
                       f"{direction}{abs(actual_pct):.2f}%"
                       f"（{base_price:.2f}→{current_price:.2f}）")
                self._fire_alert(title, msg)

    def _check_new_high_low_alert(self, code, name, current_price, high_price, low_price):
        """新高新低报警：当日最高价创新高或最低价创新低时发出通知。"""
        if not self.new_high_low_alert_enabled:
            return
        if current_price <= 0 or high_price <= 0 or low_price <= 0:
            return
        if high_price <= low_price:
            return  # 无效数据（还未交易）

        key = (code or "").strip().lower()
        now = time.time()

        prev = self._nhl_last_known.get(key)
        if prev is None:
            # 首次记录，不触发报警
            self._nhl_last_known[key] = {"high": high_price, "low": low_price}
            return

        prev_high = prev["high"]
        prev_low = prev["low"]

        # 检测新高
        if self.new_high_alert and high_price > prev_high:
            cd_key = (key, "high")
            last_fired = self._nhl_cooldowns.get(cd_key, 0)
            if now - last_fired >= self.new_high_low_cooldown:
                self._nhl_cooldowns[cd_key] = now
                title = f"{name} 创新高"
                msg = f"{code} 当日新高 {high_price:.2f}（前高 {prev_high:.2f}）"
                self._fire_alert(title, msg)

        # 检测新低
        if self.new_low_alert and low_price < prev_low:
            cd_key = (key, "low")
            last_fired = self._nhl_cooldowns.get(cd_key, 0)
            if now - last_fired >= self.new_high_low_cooldown:
                self._nhl_cooldowns[cd_key] = now
                title = f"{name} 创新低"
                msg = f"{code} 当日新低 {low_price:.2f}（前低 {prev_low:.2f}）"
                self._fire_alert(title, msg)

        # 更新记录
        self._nhl_last_known[key] = {"high": high_price, "low": low_price}

    def _check_limit_alert(self, code, name, current_price, limit_up, limit_down, dec):
        """涨跌停通知：到达涨跌停或离开涨跌停时发出通知。"""
        if not self.limit_alert_enabled:
            return
        if current_price <= 0:
            return
        if limit_up is None and limit_down is None:
            return

        key = (code or "").strip().lower()
        now = time.time()
        cur_rounded = round(current_price, dec)

        # 当前涨跌停状态
        is_limit_up = (limit_up is not None and cur_rounded == limit_up)
        is_limit_down = (limit_down is not None and cur_rounded == limit_down)

        prev = self._limit_alert_state.get(key)
        if prev is None:
            # 首次记录，不触发报警
            self._limit_alert_state[key] = {"is_limit_up": is_limit_up, "is_limit_down": is_limit_down}
            return

        prev_up = prev["is_limit_up"]
        prev_down = prev["is_limit_down"]

        # 检测到达涨停
        if self.limit_alert_reach_up and is_limit_up and not prev_up:
            cd_key = (key, "reach_up")
            last_fired = self._limit_alert_cooldowns.get(cd_key, 0)
            if now - last_fired >= self.limit_alert_cooldown:
                self._limit_alert_cooldowns[cd_key] = now
                title = f"{name} 到达涨停"
                msg = f"{code} 当前价 {current_price:.{dec}f} 触及涨停价 {limit_up:.{dec}f}"
                self._fire_alert(title, msg)

        # 检测到达跌停
        if self.limit_alert_reach_down and is_limit_down and not prev_down:
            cd_key = (key, "reach_down")
            last_fired = self._limit_alert_cooldowns.get(cd_key, 0)
            if now - last_fired >= self.limit_alert_cooldown:
                self._limit_alert_cooldowns[cd_key] = now
                title = f"{name} 到达跌停"
                msg = f"{code} 当前价 {current_price:.{dec}f} 触及跌停价 {limit_down:.{dec}f}"
                self._fire_alert(title, msg)

        # 检测离开涨停
        if self.limit_alert_leave_up and not is_limit_up and prev_up:
            cd_key = (key, "leave_up")
            last_fired = self._limit_alert_cooldowns.get(cd_key, 0)
            if now - last_fired >= self.limit_alert_cooldown:
                self._limit_alert_cooldowns[cd_key] = now
                title = f"{name} 离开涨停"
                msg = f"{code} 当前价 {current_price:.{dec}f} 已离开涨停价 {limit_up:.{dec}f}"
                self._fire_alert(title, msg)

        # 检测离开跌停
        if self.limit_alert_leave_down and not is_limit_down and prev_down:
            cd_key = (key, "leave_down")
            last_fired = self._limit_alert_cooldowns.get(cd_key, 0)
            if now - last_fired >= self.limit_alert_cooldown:
                self._limit_alert_cooldowns[cd_key] = now
                title = f"{name} 离开跌停"
                msg = f"{code} 当前价 {current_price:.{dec}f} 已离开跌停价 {limit_down:.{dec}f}"
                self._fire_alert(title, msg)

        # 更新状态
        self._limit_alert_state[key] = {"is_limit_up": is_limit_up, "is_limit_down": is_limit_down}
