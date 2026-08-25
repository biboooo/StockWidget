# -*- coding: utf-8 -*-
import requests


class MarketDataMixin:
    def smart_format_code(self, raw_code):
        """
        智能识别股票/期货/指数代码并补全前缀
        """
        raw_code = str(raw_code).strip()
        
        # 1. 如果用户已经自带了前缀（比如已经输入了 hf_XAU, sh600519），直接放行
        if "_" in raw_code or raw_code.startswith(("sh", "sz", "bj")):
            return raw_code
            
        # 2. 纯数字：国内 A股 / ETF / 转债 自动识别
        if raw_code.isdigit() and len(raw_code) == 6:
            if raw_code.startswith(("6", "5")):
                return f"sh{raw_code}"  # 沪市股票(6)或ETF(5)
            elif raw_code.startswith(("0", "3", "1")):
                return f"sz{raw_code}"  # 深市股票(0,3)或ETF(1)
            elif raw_code.startswith(("4", "8")):
                return f"bj{raw_code}"  # 北交所
                
        # 3. 常见外盘现货 / 期货 (转化为 hf_ 大写)
        hf_list = ["XAU", "XAG", "OIL", "CL", "GC", "SI"]
        if raw_code.upper() in hf_list:
            return f"hf_{raw_code.upper()}"
            
        # 4. 常见全球指数 (转化为 b_ 大写)
        b_list = ["NKY", "DJI", "IXIC", "SPX", "HSI"]
        if raw_code.upper() in b_list:
            return f"b_{raw_code.upper()}"
            
        # 5. 如果是纯英文字母（且不在上面列表里），默认当成美股 (转化为 gb_ 小写)
        if raw_code.isalpha():
            return f"gb_{raw_code.lower()}"
            
        # 兜底返回原样
        return raw_code

    # ----- 数据来源：新浪财经 -----
    def _get_price(self, codes:list):
        formatted_codes = []
        for c in codes:
            c_str = self.smart_format_code(c)
            if not c_str: 
                continue
                
            # 兼容处理：遇到 nf_ (国内期货), hf_ (外盘), b_ (全球指数)，保证前缀小写，后缀大写
            if c_str.lower().startswith(('nf_', 'hf_', 'b_')):
                # 用 '_' 分割更安全，不用管前缀是 2 位还是 3 位
                parts = c_str.split('_', 1)
                if len(parts) == 2:
                    formatted_codes.append(f"{parts[0].lower()}_{parts[1].upper()}")
                else:
                    formatted_codes.append(c_str)
            else:
                # 对于 A股 (sh/sz/bj) 或 美股 (gb_)，保持全小写即可
                formatted_codes.append(c_str.lower())
                
        label = ",".join(formatted_codes)
        # ==========================================

        if not label:
            raise Exception("暂无数据，请添加自选")

        price_data = []
        sign_data = []
        total_pnl = 0.0
        has_pnl = False
        url = 'https://hq.sinajs.cn/list=' + label
        headers = {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=3)
        r.encoding = 'gbk'
        
        for line in r.text.split('\n'):
            if not line or '"' not in line:
                continue
            
            prefix_part = line.split('="')[0]
            parts = line.split('="')[1].split(',')
            
            # 判断是否为内盘期货 (nf_) 或 外盘期货 (hf_)
            is_nf_futures = "str_nf_" in prefix_part
            is_hf_futures = "str_hf_" in prefix_part
            is_b_futures = 'str_b_' in prefix_part
            is_fx_futures = 'str_fx_' in prefix_part
            is_gb_stock = "str_gb_" in prefix_part
            is_hk_stock = "str_rt_hk" in prefix_part or "str_hk" in prefix_part
            # 【新增】：统一的一个期货标志位，方便后续使用
            is_any_futures = is_nf_futures or is_hf_futures
            
            if is_hf_futures:

                #print(f"👉 成功进入外盘期货(hf_)解析分支！")
                #print(f"👉 原始文本行: {line}")
                #print(f"👉 拆分后的数组 (长度 {len(parts)}): {parts}")
                #print("="*50 + "\n")

                if len(parts) < 14: 
                    continue
                code          = prefix_part.split('str_hf_')[-1]
                # 第 14 个元素（索引13）的名称清洗一下
                name = parts[13].replace('"', '').replace(';', '')
                opening_price = float(parts[8] or 0)
                high_price    = float(parts[4] or 0)
                low_price     = float(parts[5] or 0)
                prev_close    = float(parts[7] or 0)
                current_price = float(parts[0] or 0)
                first_pur     = float(parts[2] or 0)
                first_sell    = float(parts[3] or 0)
                
                # 安全获取成交量：只有长度大于 14，才去取 parts[14]
                if len(parts) > 14:
                    vol_str = parts[14].replace('"', '').replace(';', '')
                    deals_vol = float(vol_str or 0)
                else:
                    deals_vol = 0.0  # 长度只有14的现货黄金，乖乖走这里

                deals_amt     = current_price * deals_vol 
                committee     = 0.0
                pur_vol       = int(parts[10] or 0) * 100 
                sel_vol       = int(parts[11] or 0) * 100
                purchaser     = [pur_vol] + [0]*9 
                pur_price     = [first_pur] + [0]*9
                seller        = [sel_vol] + [0]*9
                sel_price     = [first_sell] + [0]*9
                etf           = False

            elif is_nf_futures:

                if len(parts) < 14:
                    continue
                
                code          = prefix_part.split('str_nf_')[-1]
                name          = parts[0]
                opening_price = float(parts[2] or 0)
                high_price    = float(parts[3] or 0)
                low_price     = float(parts[4] or 0)
                
                # 【修复1】：昨收（昨结算）实际上在索引 10 的位置
                prev_close    = float(parts[10] or 0) 
                
                first_pur     = float(parts[6] or 0)
                first_sell    = float(parts[7] or 0)
                current_price = float(parts[8] or 0)
                deals_vol     = float(parts[14] or 0)
                
                # 【修复2】：为了让下面的通用代码能算出正确的均价(avg = amt/vol)，
                # 我们用 现价*成交量 倒推伪装一个“成交额”给它
                deals_amt = current_price * deals_vol 
                committee = 0.0
                
                # 期货本身就是手数，为了抵消下方 A 股的除以 100 逻辑，这里乘 100
                pur_vol = int(parts[11] or 0) * 100 
                sel_vol = int(parts[12] or 0) * 100
                purchaser = [pur_vol] + [0]*9 
                pur_price = [first_pur] + [0]*9
                seller    = [sel_vol] + [0]*9
                sel_price = [first_sell] + [0]*9
                etf = False

            elif is_b_futures:
                # ====== 新浪全球指数解析分支 (如 b_NKY) ======
                # 指数返回的数据非常短，通常只有名称、点数、涨跌额、涨跌幅等几个核心数据
                if len(parts) < 4:
                    continue
                    
                code          = prefix_part.split('str_b_')[-1]
                name          = parts[0].replace('"', '').replace(';', '')
                current_price = float(parts[1] or 0)
                
                # 新浪全球指数通常 parts[2] 是涨跌额，parts[3] 是涨跌幅百分比
                change_amount = float(parts[2] or 0)
                
                # 指数接口通常不给昨收，我们需要通过公式【昨收 = 现价 - 涨跌额】自己推算出来
                prev_close    = current_price - change_amount
                
                # ====== 下面这些是指数没有的数据，统一填 0 防止你的浮窗报错 ======
                opening_price = 0.0
                high_price    = 0.0
                low_price     = 0.0
                first_pur     = 0.0
                first_sell    = 0.0
                deals_vol     = 0.0
                deals_amt     = 0.0
                committee     = 0.0
                pur_vol       = 0 
                sel_vol       = 0
                purchaser     = [0]*10 
                pur_price     = [0]*10
                seller        = [0]*10
                sel_price     = [0]*10
                etf           = False

            elif is_fx_futures:
                if len(parts) < 10:
                    continue
                    
                code          = prefix_part.split('str_fx_s')[-1].upper()
                name          = parts[9].replace('"', '').replace(';', '')  # 名称在第 9 位
                current_price = float(parts[8] or 0)  # 现价在第 8 位
                prev_close    = float(parts[3] or 0)  # 昨收在第 3 位
                opening_price = float(parts[5] or 0)
                high_price    = float(parts[6] or 0)
                low_price     = float(parts[7] or 0)
                first_pur     = float(parts[1] or 0)  # 银行买入价
                first_sell    = float(parts[2] or 0)  # 银行卖出价
                

                # ------ 下面是没有的数据，统一填 0 防崩溃 ------
                deals_vol     = 0.0
                deals_amt     = 0.0
                committee     = 0.0
                pur_vol       = 0 
                sel_vol       = 0
                purchaser     = [0]*10 
                pur_price     = [0]*10
                seller        = [0]*10
                sel_price     = [0]*10
                etf           = False

            elif is_hk_stock:
                # ====== 新浪港股解析分支 (如 rt_hk01810) ======
                if len(parts) < 13:
                    continue
                
                # 提取纯数字代码
                if 'str_rt_hk' in prefix_part:
                    code = prefix_part.split('str_rt_hk')[-1]
                else:
                    code = prefix_part.split('str_hk')[-1]
                    
                name          = parts[1].replace('"', '').replace(';', '') # 港股中文名在第 1 位 (第0位是英文简称)
                opening_price = float(parts[2] or 0)  # 开盘价
                prev_close    = float(parts[3] or 0)  # 昨收价
                high_price    = float(parts[4] or 0)  # 最高价
                low_price     = float(parts[5] or 0)  # 最低价
                current_price = float(parts[6] or 0)  # 现价在第 6 位
                
                # 港股的买一和卖一
                first_pur     = float(parts[9] or 0)
                first_sell    = float(parts[10] or 0)
                
                # 港股成交量与成交额
                deals_vol     = float(parts[11] or 0) 
                deals_amt     = float(parts[12] or 0) 
                
                # ------ 补齐其他没有的数据，防崩溃 ------
                committee     = 0.0
                pur_vol       = 0 
                sel_vol       = 0
                purchaser     = [0]*10 
                pur_price     = [first_pur] + [0]*9
                seller        = [0]*10
                sel_price     = [first_sell] + [0]*9
                etf           = False

            elif is_gb_stock:
                # ====== 新浪美股解析分支 (如 gb_aapl) ======
                if len(parts) < 20:
                    continue
                    
                code          = prefix_part.split('str_gb_')[-1].upper() # 转成大写 AAPL 显示
                name          = parts[0].replace('"', '').replace(';', '')
                current_price = float(parts[1] or 0)  # 美股现价在第 1 位
                change_amount = float(parts[2] or 0)  # 美股涨跌额在第 2 位
                
                # 美股接口有时昨收字段会漂移，最安全的方式是用公式反推昨收价：
                prev_close    = current_price - change_amount
                
                opening_price = float(parts[5] or 0)  # 开盘
                high_price    = float(parts[6] or 0)  # 最高
                low_price     = float(parts[7] or 0)  # 最低
                deals_vol     = float(parts[10] or 0) # 成交量
                
                # ------ 美股接口不提供买卖盘口数据，统一补 0 防崩溃 ------
                first_pur     = 0.0
                first_sell    = 0.0
                deals_amt     = current_price * deals_vol  # 估算一个大概的成交额
                committee     = 0.0
                pur_vol       = 0 
                sel_vol       = 0
                purchaser     = [0]*10 
                pur_price     = [0]*10
                seller        = [0]*10
                sel_price     = [0]*10
                etf           = False

            else:
                if len(parts) < 30:
                    continue
                heads = prefix_part.split('_')
                code          = heads[2]
                name          = parts[0]
                opening_price = float(parts[1] or 0)   # 开盘
                prev_close    = float(parts[2] or 0)   # 昨收
                current_price = float(parts[3] or 0)   # 现价
                high_price    = float(parts[4] or 0)   # 当日最高
                low_price     = float(parts[5] or 0)   # 当日最低
                first_pur     = float(parts[6] or 0)   # 买一
                first_sell    = float(parts[7] or 0)   # 卖一
                deals_vol     = float(parts[8] or 0)   # 成交量
                deals_amt     = float(parts[9] or 0)   # 成交额
                purchaser     = [int(x or 0) for x in parts[10:19:2]]  
                pur_price     = [float(x or 0) for x in parts[11:20:2]]  
                seller        = [int(x or 0) for x in parts[20:29:2]]  
                sel_price     = [float(x or 0) for x in parts[21:30:2]]  
                etf = code[2] in ('1','5') if len(code)>2 else False

            # 构建买一/卖一数据及其颜色信息，并添加位置箭头
            b1_label = ""
            s1_label = ""
            b1_color_sign = 0  # 买一颜色：1红 0中性 -1绿
            s1_color_sign = 0  # 卖一颜色：1红 0中性 -1绿

            # 决定小数精度用于比较是否相等（避免浮点微小误差）
            dec = 3 if etf else 2
            def almost_eq(a, b):
                try:
                    return round(float(a), dec) == round(float(b), dec)
                except Exception:
                    return False

            # 标记：买一箭头位于右侧 '<'，卖一箭头位于左侧 '>'
            buy_marker = " "
            sell_marker = " "
            if first_pur > 0 and almost_eq(current_price, first_pur):
                buy_marker = "<"
            if first_sell > 0 and almost_eq(current_price, first_sell):
                sell_marker = ">"

            if first_pur == first_sell > 0:
                # 集合竞价：配对量 / 未配对量
                # 此处不显示成交方向箭头（竞价阶段无 <> 指示），且配对量和未配对量使用统一颜色规则
                current_price = first_sell  # 9:15 ~ 9:25; 14:57 ~ 15:00 竞价
                paired = seller[0]
                # unpaired_sign: >0 表示买方优势，<0 表示卖方优势
                unpaired_sign = -seller[1] if seller[1] > 0 else purchaser[1]
                # 显示数量（手）或价格或数量和价格（手数(价格)）
                paired_cnt = int(paired/100)
                unpaired_cnt = int(unpaired_sign/100)
                paired_fmt = self._fmt_lots(paired_cnt)
                unpaired_fmt = f"+{self._fmt_lots(unpaired_cnt)}" if unpaired_cnt >= 0 else f"-{self._fmt_lots(abs(unpaired_cnt))}"
                b_price = f"{first_pur:.3f}" if etf else f"{first_pur:.2f}"
                s_price = f"{first_sell:.3f}" if etf else f"{first_sell:.2f}"
                mode = getattr(self, 'b1s1_display', 'qty')
                if mode == 'price':
                    b1_label = f"{b_price}"
                    s1_label = f"{s_price}"
                elif mode == 'both':
                    b1_label = f"{paired_fmt}({b_price})"
                    s1_label = f"{unpaired_fmt}({s_price})"
                else:
                    b1_label = f"{paired_fmt}"
                    s1_label = f"{unpaired_fmt}"
                # 竞价颜色：根据未配对量的方向
                if unpaired_sign > 0:
                    b1_color_sign = 1
                    s1_color_sign = 1
                elif unpaired_sign < 0:
                    b1_color_sign = -1
                    s1_color_sign = -1
                else:
                    b1_color_sign = 0
                    s1_color_sign = 0
            else:
                # 连续竞价：买一数量/卖一数量
                if first_pur > 0:
                    cnt = self._fmt_lots(int(purchaser[0]/100))
                    b_price = f"{first_pur:.3f}" if etf else f"{first_pur:.2f}"
                    mode = getattr(self, 'b1s1_display', 'qty')
                    if mode == 'price':
                        b1_label = f"{b_price}{buy_marker}"
                    elif mode == 'both':
                        b1_label = f"{cnt}({b_price}){buy_marker}"
                    else:
                        b1_label = f"{cnt}{buy_marker}"
                else:
                    b1_label = f"-{buy_marker}"

                if first_sell > 0:
                    cnt = self._fmt_lots(int(seller[0]/100))
                    s_price = f"{first_sell:.3f}" if etf else f"{first_sell:.2f}"
                    mode = getattr(self, 'b1s1_display', 'qty')
                    if mode == 'price':
                        s1_label = f"{sell_marker}{s_price}"
                    elif mode == 'both':
                        s1_label = f"{sell_marker}{cnt}({s_price})"
                    else:
                        s1_label = f"{sell_marker}{cnt}"
                else:
                    s1_label = f"{sell_marker}-"

                # 连续竞价时：买一固定红色，卖一固定绿色
                b1_color_sign = 1
                s1_color_sign = -1
            
            if current_price == 0:
                current_price = prev_close # 9:00 ~ 9:15 无数据
            if opening_price == 0: 
                opening_price = current_price
                high_price = current_price
                low_price = current_price

            change = current_price - prev_close if prev_close else 0.0
            change_pct = (current_price / prev_close - 1) * 100 if prev_close else 0.0
            avg = (deals_amt / deals_vol) if deals_vol > 0 else prev_close # 均价
            p_sum, s_sum = sum(purchaser), sum(seller)
            committee = (100 * (p_sum - s_sum) / (p_sum + s_sum)) if (p_sum + s_sum) > 0 else 0.0 # 委比

            # 触及涨跌停或日高/低显示箭头（涨跌停优先）
            # 涨跌停价计算：创业板/科创板±20%，ST±5%，其余±10%
            limit_up = None
            limit_down = None
            if not etf and prev_close > 0:
                if "ST" in name or "st" in name:
                    limit_pct = 0.05
                elif code[2:5] in ('300','301','688'):
                    limit_pct = 0.20
                else:
                    limit_pct = 0.10
                limit_up = round(prev_close * (1 + limit_pct), dec)
                limit_down = round(prev_close * (1 - limit_pct), dec)

            arrow = " "
            if high_price > low_price:
                if limit_up is not None:
                    cur_rounded = round(current_price, dec)
                    if cur_rounded == limit_up:
                        arrow = self.sym_limit_up
                    elif cur_rounded == limit_down:
                        arrow = self.sym_limit_down
                    elif current_price == high_price:
                        arrow = self.sym_high
                    elif current_price == low_price:
                        arrow = self.sym_low
                else:
                    if current_price == high_price: arrow = self.sym_high
                    elif current_price == low_price: arrow = self.sym_low

            # 封单预警检测
            try:
                self._check_seal_alerts(code, name, current_price,
                                        first_pur, first_sell,
                                        purchaser[0], seller[0],
                                        limit_up, limit_down, dec)
            except Exception:
                pass

            # 涨跌异动报警检测
            try:
                self._check_price_alert(code, name, current_price, prev_close)
            except Exception:
                pass

            # 新高新低报警检测
            try:
                self._check_new_high_low_alert(code, name, current_price, high_price, low_price)
            except Exception:
                pass

            # 涨跌停通知检测
            try:
                self._check_limit_alert(code, name, current_price, limit_up, limit_down, dec)
            except Exception:
                pass

            k_payload = {"k": (opening_price, current_price, high_price, low_price, prev_close)}

            # 计算盈亏：(现价 - 成本) * 持仓数量
            cd = self.cost_data.get(code)
            if cd:
                pnl_val = (current_price - cd["cost"]) * cd["qty"]
                pnl_label = self._fmt_signed(pnl_val, 3 if etf else 2)
                pnl_sign = (pnl_val > 0) - (pnl_val < 0)
                total_pnl += pnl_val
                has_pnl = True
            else:
                pnl_label = ""
                pnl_sign = 0

            # 委比格式化
            commi_label = self._fmt_signed(committee, 2) + "%"
            
            # 智能提取代码短名
            display_code = code[2:] if not is_any_futures and getattr(self, 'short_code', False) else code

            if not etf:
                chg_fmt = self._fmt_signed(change, 2)
                pct_fmt = self._fmt_signed(change_pct, 2) + "%"
                
                current_price_str = f"{arrow}{current_price:.2f}"
                
                price_data.append([
                    display_code,
                    name if getattr(self, 'name_length', 0) == 0 else name[:self.name_length],
                    current_price_str,
                    chg_fmt,
                    pct_fmt,
                    pnl_label,
                    b1_label,
                    s1_label,
                    commi_label,
                    f"{deals_vol}" if deals_vol<1e4 else (f"{deals_vol/1e4:.2f}万" if deals_vol<1e8 else f"{deals_vol/1e8:.2f}亿"),
                    f"{deals_amt/1e4:.2f}万" if deals_amt<1e8 else (f"{deals_amt/1e8:.2f}亿" if deals_amt<1e12 else f"{deals_amt/1e12:.2f}万亿"),
                    f"{avg:.2f}",
                    f"{high_price:.2f}",
                    f"{low_price:.2f}",
                    k_payload
                ])
            else:
                # ETF 的价格保留 3 位小数
                chg_fmt = self._fmt_signed(change, 3)
                pct_fmt = self._fmt_signed(change_pct, 2) + "%"
                
                current_price_str = f"{arrow}{current_price:.3f}"
                
                price_data.append([
                    display_code,
                    name if getattr(self, 'name_length', 0) == 0 else name[:self.name_length],
                    current_price_str,
                    chg_fmt,
                    pct_fmt,
                    pnl_label,
                    b1_label,
                    s1_label,
                    commi_label,
                    f"{deals_vol}" if deals_vol<1e4 else (f"{deals_vol/1e4:.2f}万" if deals_vol<1e8 else f"{deals_vol/1e8:.2f}亿"),
                    f"{deals_amt/1e4:.2f}万" if deals_amt<1e8 else (f"{deals_amt/1e8:.2f}亿" if deals_amt<1e12 else f"{deals_amt/1e12:.2f}万亿"),
                    f"{avg:.3f}",
                    f"{high_price:.3f}",
                    f"{low_price:.3f}",
                    k_payload
                ])

            # 构建信号灯数据保持不变
            sign_data.append({
                "delta": (change > 0) - (change < 0), 
                "commi": (committee > 0) - (committee < 0),
                "avg": (avg > prev_close) - (avg < prev_close),
                "b1": b1_color_sign,
                "s1": s1_color_sign,
                "pnl": pnl_sign,
                "high": (high_price > prev_close) - (high_price < prev_close) if prev_close else 0,
                "low": (low_price > prev_close) - (low_price < prev_close) if prev_close else 0,
            })
        
        return price_data, sign_data, total_pnl, has_pnl
