import requests
import logging
from typing import Optional, Dict, Any

# 从当前包的config模块中导入BOPTEST_BASE_URL
# Import BOPTEST_BASE_URL from the config module in the current package
from .config import BOPTEST_BASE_URL

# --- 模块级别的日志记录设置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def _handle_request_errors(func):
    """
    一个装饰器，用于统一处理requests库可能抛出的常见异常。
    A decorator to handle common exceptions from the requests library.
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.Timeout as e:
            logging.error(f"Request timed out. The BOPTEST server might be busy or slow. Error: {e}")
            return None
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Failed to connect to the BOPTEST server. Please ensure BOPTEST is running. Error: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP Error occurred. Status: {e.response.status_code}, Body: {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"An unexpected request error occurred: {e}")
            return None

    return wrapper


@_handle_request_errors
def select_testcase(testcase_name: str) -> Optional[str]:
    """
    向BOPTEST API发送请求，选择一个测试案例并获取其唯一的testid。
    Sends a request to the BOPTEST API to select a test case and retrieve its unique testid.

    Args:
        testcase_name (str): 要选择的测试案例的名称。
                             The name of the test case to be selected.

    Returns:
        Optional[str]: 如果成功，返回一个字符串格式的testid。如果失败，返回None。
                       The testid as a string on success. Returns None on failure.
    """
    url = f"{BOPTEST_BASE_URL}/testcases/{testcase_name}/select"
    logging.info(f"Selecting testcase '{testcase_name}' with POST request to {url}")
    response = requests.post(url, timeout=120)
    response.raise_for_status()
    data = response.json()
    testid = data.get('testid')
    if not testid:
        logging.error(f"Response from {url} is missing 'testid'. Response: {data}")
        return None
    logging.info(f"Successfully selected testcase. Received testid: {testid}")
    return testid


@_handle_request_errors
def initialize(testid: str, start_time: int, warmup_period: int) -> Optional[Dict[str, Any]]:
    """
    向BOPTEST API发送initialize请求，以启动并预热一个已选定的模拟环境。
    Sends an initialize request to the BOPTEST API to start and warm up a selected simulation environment.

    Args:
        testid (str): 从select_testcase获取的唯一测试ID。
                      The unique test ID obtained from select_testcase.
        start_time (int): 模拟的开始时间（秒），相对于年度的开始。
                          The start time of the simulation in seconds.
        warmup_period (int): 预热时长（秒）。
                             The duration of the warm-up period in seconds.

    Returns:
        Optional[Dict[str, Any]]: 成功时返回包含初始状态的字典，失败时返回None。
                                  A dictionary with the initial state on success, None on failure.
    """
    # [关键修正] URL现在是 /initialize/{testid} 端点，并且使用 PUT 方法
    # [KEY CHANGE] The URL is now the /initialize/{testid} endpoint, and the method is PUT
    url = f"{BOPTEST_BASE_URL}/initialize/{testid}"

    # [关键修正] testid 不再是payload的一部分
    # [KEY CHANGE] testid is no longer part of the payload
    payload = {
        'start_time': start_time,
        'warmup_period': warmup_period
    }

    logging.info(f"Sending PUT request to {url} with payload: {payload}")
    response = requests.put(url, json=payload, timeout=240)  # 增加超时以应对较长的预热
    response.raise_for_status()
    initial_state = response.json().get('payload', {})
    logging.info("Successfully initialized BOPTEST environment.")
    logging.debug(f"Received initial state: {initial_state}")
    return initial_state


@_handle_request_errors
def advance(testid: str, control_inputs: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    推进模拟一个步长。
    Advance the simulation by one step.

    Args:
        testid (str): 测试实例的唯一ID。
                      The unique test ID.
        control_inputs (Optional[Dict[str, Any]]): 要覆盖的控制输入字典。
                                                    A dictionary of control inputs to overwrite.

    Returns:
        Optional[Dict[str, Any]]: 成功时返回新的测量值字典，失败时返回None。
                                  A dictionary of new measurements on success, None on failure.
    """
    url = f"{BOPTEST_BASE_URL}/advance/{testid}"
    logging.info(f"Advancing simulation for testid {testid} with inputs: {control_inputs or {} }")
    response = requests.post(url, json=control_inputs or {}, timeout=120)
    response.raise_for_status()
    return response.json().get('payload', {})


@_handle_request_errors
def get_kpis(testid: str) -> Optional[Dict[str, Any]]:
    """
    获取当前的KPI（关键性能指标）值。
    Get the current Key Performance Indicator (KPI) values.

    Args:
        testid (str): 测试实例的唯一ID。
                      The unique test ID.

    Returns:
        Optional[Dict[str, Any]]: 包含KPI值的字典，或在失败时返回None。
                                  A dictionary of KPI values, or None on failure.
    """
    url = f"{BOPTEST_BASE_URL}/kpi/{testid}"
    logging.info(f"Fetching KPIs for testid {testid}")
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.json().get('payload', {})


@_handle_request_errors
def stop(testid: str) -> Optional[Dict[str, Any]]:
    """
    停止一个测试案例实例。
    Stop a test case instance.

    Args:
        testid (str): 测试实例的唯一ID。
                      The unique test ID.

    Returns:
        Optional[Dict[str, Any]]: 成功时返回API的响应，失败时返回None。
                                  The API response on success, or None on failure.
    """
    url = f"{BOPTEST_BASE_URL}/stop/{testid}"
    logging.info(f"Stopping test case with testid {testid}")
    response = requests.put(url, timeout=60)
    response.raise_for_status()
    return response.json()
