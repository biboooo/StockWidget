# -*- coding: utf-8 -*-
"""
K线形态相似度筛选
- 内置200+行业/主题ETF（排除宽基、跨境、债券、货币）
- 三段式形态匹配：下跌段 + 筑底段 + 反弹段
- 数据质量过滤：排除回撤>60%的异常数据
- 综合得分：涨跌幅节奏 + 分段形态 + 相关性
"""
import sys
import time
import json
import requests
import pandas as pd
import numpy as np

# =========配置区========
REFERENCE_CODE = "601166"
#REFERENCE_CODE = "512480"
START_DATE = "2026-02-01"
END_DATE = "2026-08-18"
MIN_TRADE_AMOUNT = 2000  # 成交额(万)
MIN_DRAWDOWN = 0.12  # 最小回撤
MAX_DRAWDOWN = 0.60  # 最大回撤（超过60%视为数据异常）
MIN_CORR = 0.35  # 最小相关系数
MAX_PRICE_RATIO = 0.96  # 排除接近新高的
SLEEP_SEC = 0.25
DATALEN = 200
# =======================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn/"
}

# ============ 内置行业/主题ETF池（排除宽基/跨境/债券）============
INDUSTRY_ETF = [
    # --- 科技/半导体/AI ---
    "512480", "512760", "588200", "159995", "515030", "512660", "515790",
    "515000", "159611", "516160", "562500", "159766", "516150", "515220",
    "159939", "159801", "512980", "159825", "515170", "560080", "159755",
    "516510", "159605", "159687", "515980", "159560", "560600", "159742",
    "516010", "159892", "515880", "515700", "159509", "159501", "588790",
    "159781", "516530", "159678", "562800", "159819", "515070", "515050",
    "512720", "159998", "515230", "518300", "159864", "516620", "159852",
    "515340", "159749", "562510", "159888", "516950", "159890", "516350",
    # --- 医药 ---
    "512170", "512010", "159928", "512290", "159883", "516820", "159643",
    "516850", "159992", "512300", "159893", "516800", "159776", "516060",
    "159602", "516030", "159760", "516500", "159717", "516080", "159847",
    # --- 新能源/车 ---
    "515030", "515790", "516160", "159755", "515000", "516510", "159605",
    "516390", "159758", "516280", "159806", "515020", "159824", "516830",
    "159763", "516790", "159768", "516660", "159857", "515210", "159840",
    "516090", "159709", "516220", "159861", "516520", "159865", "516880",
    # --- 消费 ---
    "159928", "512690", "159996", "515100", "159862", "515650", "159825",
    "512200", "159869", "515920", "159836", "516130", "159866", "515150",
    # --- 金融 ---
    "512880", "512000", "512070", "512800", "159841", "516110", "512570",
    "159842", "516710", "159985", "512700", "516730", "159739", "516650",
    # --- 周期/资源 ---
    "512400", "159980", "516780", "159871", "516960", "159867", "518800",
    "516980", "159714", "516020", "159868", "516550", "159703", "516480",
    "518200", "159753", "516320", "159745", "516690", "159870", "516300",
    # --- 军工/国防 ---
    "512660", "512710", "159680", "516830", "159778", "516180", "159839",
    "516360", "159779", "516760", "159814", "516920", "159764", "516860",
    # --- 地产/基建 ---
    "512200", "516970", "159745", "516850", "159836", "516950", "159878",
    # --- 农业/传媒/其他 ---
    "159825", "516980", "159805", "516960", "159766", "516770", "159863",
    "516580", "159873", "516800", "159884", "516630", "159875", "516250",
]
# 去重
INDUSTRY_ETF = list(dict.fromkeys(INDUSTRY_ETF))


# ============ 数据获取 ============

def get_etf_kline(code: str):
    if code.startswith(("5", "6", "9")):
        symbol = "sh" + code
    else:
        symbol = "sz" + code
    url = (
        "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={DATALEN}"
    )
    time.sleep(SLEEP_SEC)
    resp = requests.get(url, headers=HEADERS, timeout=12)
    data = json.loads(resp.text)
    if not data:
        return None
    df = pd.DataFrame(data)
    df["day"] = pd.to_datetime(df["day"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values("day").reset_index(drop=True)
    mask = (df["day"] >= START_DATE) & (df["day"] <= END_DATE)
    df = df.loc[mask].reset_index(drop=True)
    if len(df) < 50:
        return None
    df["amount"] = (df["close"] * df["volume"]) / 10000
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    df["pct"] = df["close"].pct_change()
    return df


# ============ 三段式形态特征 ============

def extract_segments(df):
    """
    把K线分成三段，提取形态特征：
    - 下跌段（前40%）：涨跌幅均值、最大跌幅
    - 筑底段（中30%）：波动率、振幅
    - 反弹段（后30%）：涨跌幅均值、反弹力度
    """
    n = len(df)
    seg1_end = int(n * 0.4)
    seg2_end = int(n * 0.7)

    seg1 = df.iloc[:seg1_end]  # 下跌段
    seg2 = df.iloc[seg1_end:seg2_end]  # 筑底段
    seg3 = df.iloc[seg2_end:]  # 反弹段

    features = {
        # 下跌段
        "seg1_return": (seg1["close"].iloc[-1] / seg1["close"].iloc[0] - 1),
        "seg1_max_drop": (seg1["close"].min() / seg1["close"].iloc[0] - 1),
        "seg1_vol": seg1["pct"].std(),
        # 筑底段
        "seg2_amplitude": (seg2["close"].max() - seg2["close"].min()) / seg2["close"].mean(),
        "seg2_vol": seg2["pct"].std(),
        "seg2_return": (seg2["close"].iloc[-1] / seg2["close"].iloc[0] - 1),
        # 反弹段
        "seg3_return": (seg3["close"].iloc[-1] / seg3["close"].iloc[0] - 1),
        "seg3_vol": seg3["pct"].std(),
        "seg3_strength": (seg3["close"].iloc[-1] - seg3["close"].min()) / seg3["close"].min(),
    }
    return features


def segment_distance(ref_feat, tgt_feat):
    """计算两段形态特征的欧氏距离"""
    keys = list(ref_feat.keys())
    ref_vals = np.array([ref_feat[k] for k in keys])
    tgt_vals = np.array([tgt_feat[k] for k in keys])
    # 标准化每个特征维度
    return np.sqrt(np.sum(np.square(ref_vals - tgt_vals)))


# ============ 相似度 ============

def zscore(ser):
    s = ser.dropna()
    if s.std() == 0:
        return s * 0
    return (s - s.mean()) / s.std()


def minmax(ser):
    s = ser.dropna()
    return (s - s.min()) / (s.max() - s.min())


def calc_similarity(ref_df, target_df):
    min_len = min(len(ref_df), len(target_df))
    r = ref_df.tail(min_len).reset_index(drop=True)
    t = target_df.tail(min_len).reset_index(drop=True)

    # 维度1：涨跌幅节奏（Z-score欧氏距离）
    r_pct = zscore(r["pct"]).fillna(0).values
    t_pct = zscore(t["pct"]).fillna(0).values
    pct_dist = np.sqrt(np.sum(np.square(r_pct - t_pct)))

    # 维度2：收盘价轮廓
    r_close = minmax(r["close"]).values
    t_close = minmax(t["close"]).values
    close_dist = np.sqrt(np.sum(np.square(r_close - t_close)))

    # 维度3：皮尔逊相关系数
    corr = np.corrcoef(r["close"].values, t["close"].values)[0, 1]
    corr = 0 if np.isnan(corr) else corr

    # 维度4：三段式形态特征
    ref_feat = extract_segments(r)
    tgt_feat = extract_segments(t)
    seg_dist = segment_distance(ref_feat, tgt_feat)

    # 综合得分（各维度归一化权重）
    score = (
            pct_dist * 0.30 +
            close_dist * 0.20 +
            (1 - corr) * 10 * 0.20 +
            seg_dist * 0.30
    )
    return round(score, 4), round(corr, 4), round(pct_dist, 2), round(close_dist, 2), round(seg_dist, 3)


# ============ 主流程 ============

def main():
    print(f"【1】加载参考标的 {REFERENCE_CODE}")
    ref_df = get_etf_kline(REFERENCE_CODE)
    if ref_df is None:
        print("参考K线获取失败！")
        return
    print(f"参考K线 {len(ref_df)} 行：{ref_df['day'].iloc[0].date()} ~ {ref_df['day'].iloc[-1].date()}")
    ref_feat = extract_segments(ref_df)
    print(
        f"参考形态：下跌段收益{ref_feat['seg1_return'] * 100:.1f}% 筑底振幅{ref_feat['seg2_amplitude'] * 100:.1f}% 反弹段收益{ref_feat['seg3_return'] * 100:.1f}%")

    print(f"\n【2】使用内置行业/主题ETF池，共 {len(INDUSTRY_ETF)} 只（已排除宽基/跨境/债券）")
    code_list = INDUSTRY_ETF

    out = []
    total = len(code_list)
    skip = {"drawdown_low": 0, "drawdown_high": 0, "corr": 0, "high": 0, "ma": 0, "amount": 0, "data": 0}
    for idx, code in enumerate(code_list):
        if idx % 50 == 0:
            print(f"进度 {idx}/{total}  命中 {len(out)}")
        try:
            df = get_etf_kline(code)
            if df is None:
                skip["data"] += 1
                continue
            if df["amount"].iloc[-1] < MIN_TRADE_AMOUNT:
                skip["amount"] += 1
                continue

            high, low = df["close"].max(), df["close"].min()
            drawdown = (high - low) / high
            if drawdown < MIN_DRAWDOWN:
                skip["drawdown_low"] += 1
                continue
            if drawdown > MAX_DRAWDOWN:
                skip["drawdown_high"] += 1
                continue

            ma20_now = df["ma20"].iloc[-1]
            ma20_5ago = df["ma20"].iloc[-5]
            if ma20_now <= ma20_5ago or df["close"].iloc[-1] < ma20_now:
                skip["ma"] += 1
                continue

            price_ratio = df["close"].iloc[-1] / high
            if price_ratio > MAX_PRICE_RATIO:
                skip["high"] += 1
                continue

            min_len = min(len(ref_df), len(df))
            corr = np.corrcoef(
                ref_df.tail(min_len)["close"].values,
                df.tail(min_len)["close"].values
            )[0, 1]
            if np.isnan(corr) or corr < MIN_CORR:
                skip["corr"] += 1
                continue

            score, corr_val, pct_d, close_d, seg_d = calc_similarity(ref_df, df)
            feat = extract_segments(df)
            out.append({
                "code": code,
                "score": score,
                "corr": corr_val,
                "seg_dist": seg_d,
                "pct_dist": pct_d,
                "close_dist": close_d,
                "drawdown_pct": round(drawdown * 100, 1),
                "price_ratio": round(price_ratio, 3),
                "seg1_ret": round(feat["seg1_return"] * 100, 1),
                "seg3_ret": round(feat["seg3_return"] * 100, 1),
                "amount_wan": round(df["amount"].iloc[-1], 0)
            })
        except Exception:
            skip["data"] += 1
            continue

    res_df = pd.DataFrame(out)
    if res_df.empty:
        print("无满足条件标的！")
        print(f"过滤统计：{skip}")
        print("建议：MIN_CORR降到0.25，MAX_PRICE_RATIO升到0.98")
        return

    res_df = res_df.sort_values("score", ascending=True).reset_index(drop=True)
    print(f"\n扫描完成：命中 {len(res_df)} 只")
    print(
        f"过滤统计：成交额不足{skip['amount']} 回撤过小{skip['drawdown_low']} 回撤异常{skip['drawdown_high']} 均线{skip['ma']} 新高{skip['high']} 相关系数{skip['corr']} 数据{skip['data']}")
    print("\n========== 形态相似ETF排名（score越小越相似）==========")
    print(res_df.head(25).to_string(index=False))
    res_df.to_csv("similar_etf_result.csv", encoding="utf-8", index=False)
    print("\n结果已保存：similar_etf_result.csv")


if __name__ == "__main__":
    main()