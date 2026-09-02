from datetime import datetime
from dateutil.relativedelta import relativedelta


class DateRangeUtils:
    """日期范围工具类（仅返回日期字符串）"""

    def __init__(self, base_date: datetime = None):
        """
        初始化日期工具类
        :param base_date: 基准日期，默认为当前时间
        """
        self.now = base_date or datetime.now()

    def _format_date(self, dt: datetime) -> str:
        """内部格式化方法"""
        return dt.strftime('%Y-%m-%d')

    def _format_datetime(self, dt: datetime) -> str:
        """内部格式化方法"""
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def get_today(self) -> tuple[str, str]:
        """获取当天的起止日期（精确到秒）"""
        start_date = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = self.now.replace(hour=23, minute=59, second=59, microsecond=0)
        return self._format_datetime(start_date), self._format_datetime(end_date)

    def get_last_week(self) -> tuple[str, str]:
        """获取近一周（过去7天）的起止日期"""
        start_date = self.now - relativedelta(days=7)
        return self._format_date(start_date), self._format_date(self.now)

    def get_last_month(self) -> tuple[str, str]:
        """获取近一月（过去30天）的起止日期"""
        start_date = self.now - relativedelta(days=30)
        return self._format_date(start_date), self._format_date(self.now)

    def get_this_year(self) -> tuple[str, str]:
        """获取今年以来的起止日期（从1月1日到今天）"""
        start_date = self.now.replace(month=1, day=1)
        return self._format_date(start_date), self._format_date(self.now)

    def get_last_year(self) -> tuple[str, str]:
        """获取近一年的起止日期"""
        start_date = self.now - relativedelta(years=1)
        return self._format_date(start_date), self._format_date(self.now)

    def get_last_two_years(self) -> tuple[str, str]:
        """获取近两年的起止日期"""
        start_date = self.now - relativedelta(years=2)
        return self._format_date(start_date), self._format_date(self.now)

    def get_last_five_years(self) -> tuple[str, str]:
        """获取近五年的起止日期"""
        start_date = self.now - relativedelta(years=5)
        return self._format_date(start_date), self._format_date(self.now)


# --- 测试运行 ---
if __name__ == "__main__":
    utils = DateRangeUtils()

    print("当前时间:", utils.now)
    print("当天:", utils.get_today())
    print("近一周:", utils.get_last_week())
    print("近一月:", utils.get_last_month())
    print("今年来:", utils.get_this_year())
    print("近一年:", utils.get_last_year())
    print("近两年:", utils.get_last_two_years())
    print("近五年:", utils.get_last_five_years())