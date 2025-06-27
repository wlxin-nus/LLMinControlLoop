import os
import json
import logging
from typing import List, Dict, Any, Optional

# 从config模块导入输出目录的路径
# Import the path for the output directory from the config module
from .config import OUTPUT_DATA_DIR

# --- 模块级别的日志记录设置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class MemoryStore:
    """
    负责管理测试案例的经验数据。
    为每个testid存储一个单一的static_info对象和一份模拟步骤的时间序列历史记录。

    Manages experience data for test cases. For each testid, it stores a single
    static_info object and a time-series history of simulation steps.
    """

    def __init__(self, testid: str, filename: str = "memory_store.json"):
        """
        初始化MemoryStore实例。

        Args:
            testid (str): 当前测试案例的唯一ID。
            filename (str): 用于存储经验的JSON文件名。
        """
        if not testid:
            raise ValueError("必须提供一个有效的testid来初始化MemoryStore。")

        self.testid = testid
        self.filepath = os.path.join(OUTPUT_DATA_DIR, filename)
        self._all_memories = self._load_all_memories()

        # 获取当前测试案例的数据，如果不存在则创建一个默认结构
        # Get data for the current test case, or create a default structure if it doesn't exist
        self.testcase_data = self._all_memories.get(self.testid, {
            "static_info": None,
            "history": []
        })
        # 将历史记录分配给一个实例变量以便于访问
        # Assign the history to an instance variable for easier access
        self.current_run_history = self.testcase_data["history"]

        logging.info(f"MemoryStore initialized for testid: {self.testid}")
        logging.info(f"Found {len(self.current_run_history)} existing historical records for this testid.")

    def _load_all_memories(self) -> Dict[str, Dict[str, Any]]:
        """从JSON文件中加载所有测试案例的数据。"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"读取或解析 {self.filepath} 时出错。将从空的记忆库开始。错误: {e}")
                return {}
        return {}

    def add_static_info(self, static_data: Dict[str, Any]):
        """
        为当前测试案例添加或更新静态建筑信息。
        每个testid只存储一次。
        """
        self.testcase_data["static_info"] = static_data
        logging.info("已为该testid添加/更新静态信息。")

    def add_initial_state(self, initial_state: Dict[str, Any]):
        """将BOPTEST返回的初始状态添加为第一条历史记录。"""
        if any(step.get('timestep') == 0 for step in self.current_run_history):
            logging.warning("初始状态 (timestep 0) 已存在，跳过添加。")
            return

        time = initial_state.pop('time', 0.0)

        experience_step = {
            "timestep": 0,
            "time": time,
            "observation": initial_state,
            "instruction": None,
            "llm_input": None,
            "llm_thought": None,
            "action": None,
            "reward": None,
            "kpis": None
        }

        self.current_run_history.append(experience_step)
        logging.info(f"已添加初始状态作为timestep 0。当前总记录数: {len(self.current_run_history)}")

    def save(self):
        """将所有记忆数据写回到JSON文件中。"""
        # 用当前testid的数据更新主字典
        self._all_memories[self.testid] = self.testcase_data

        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self._all_memories, f, indent=4, ensure_ascii=False)
            logging.info(f"MemoryStore 已成功保存至 {self.filepath}")
        except IOError as e:
            logging.error(f"写入 {self.filepath} 失败。错误: {e}")

