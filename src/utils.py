import datetime


def convert_seconds_to_datetime_string(seconds: float) -> str:
    """
    Converts seconds from the start of the year into a human-readable string.
    将从年初开始的秒数转换为人类可读的日期时间字符串。

    Args:
        seconds (float): The total seconds elapsed since the beginning of the year.
                         从年初开始经过的总秒数。

    Returns:
        str: A formatted string, e.g., "Month 2, Day 1, 14:00".
             一个格式化的字符串，例如："Month 2, Day 1, 14:00"。
    """
    if seconds is None:
        return "Time not available"

    # 假设为非闰年 (2019年，BOPTEST常用的基准年份)
    # Assume a non-leap year (e.g., 2019, a common baseline for BOPTEST)
    start_of_year = datetime.datetime(2019, 1, 1)

    # 计算当前时间
    # Calculate the current date and time
    current_datetime = start_of_year + datetime.timedelta(seconds=seconds)

    # 格式化输出字符串
    # Format the output string
    # 例如: "Month 2, Day 1, 14:30"
    # Example: "Month 2, Day 1, 14:30"
    return current_datetime.strftime("Month %m, Day %d, %H:%M")

