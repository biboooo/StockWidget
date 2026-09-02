import akshare as ak
import pandas as pd


def get_price_quantile(stock_code, start_date="20250902", end_date="20261231"):
    """
    获取指定股票的历史数据并计算当前价格的历史分位数
    :param stock_code: 股票代码，如 "600000"
    :param start_date: 历史数据开始日期
    :param end_date: 历史数据结束日期
    :return: 当前价格, 历史分位数
    """
    try:
        # 第一步：通过 AKShare 获取历史日线数据 (默认使用前复权)
        # 注意：如果 AKShare 版本较新，接口名可能是 stock_zh_a_hist
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=start_date, end_date=end_date,
                                adjust="qfq")

        if df.empty:
            return None, None

        # 第二步：提取收盘价并计算分位
        current_price = df['收盘'].iloc[-1]
        # 计算当前价格小于历史价格的比例，即为历史分位
        percentile_rank = (df['收盘'] < current_price).sum() / len(df)

        return current_price, percentile_rank

    except Exception as e:
        print(f"获取数据或计算出错: {e}")
        return None, None


# 测试：获取“中国海油”的历史价格分位
# 兴业：601166 招商：600036
if __name__ == "__main__":
    code = "600036"
    price, quantile = get_price_quantile(code)

    if price is not None:
        print(f"股票代码: {code}")
        print(f"当前收盘价: {price}")
        print(f"历史价格分位: {quantile:.2%}")
    else:
        print("未能获取到有效数据，请检查股票代码或网络连接。")