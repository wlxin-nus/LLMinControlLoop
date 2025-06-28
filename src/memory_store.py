import os
import json
import logging
from typing import List, Dict, Any, Optional

from .config import OUTPUT_DATA_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MemoryStore:
    """负责管理测试案例的经验数据。"""
    def __init__(self, testid: str, filename: str = "memory_store.json"):
        if not testid:
            raise ValueError("必须提供一个有效的testid来初始化MemoryStore。")
        self.testid = testid
        self.filepath = os.path.join(OUTPUT_DATA_DIR, filename)
        self._all_memories = self._load_all_memories()

        self.testcase_data = self._all_memories.get(self.testid, {
            "static_info": None,
            "history": [],
            "reward_state": {"last_objective_integrand": None} # 【新增】: 初始化奖励状态
        })
        self.current_run_history = self.testcase_data["history"]
        logging.info(f"MemoryStore initialized for testid: {self.testid}. Found {len(self.current_run_history)} records.")

    def _load_all_memories(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def add_static_info(self, static_data: Dict[str, Any]):
        self.testcase_data["static_info"] = static_data

    def add_initial_state(self, initial_state: Dict[str, Any]):
        if any(step.get('timestep') == 0 for step in self.current_run_history):
            return
        time = initial_state.pop('time', 0.0)
        experience_step = {
            "timestep": 0, "time": time, "observation": initial_state,
            "instruction": None, "llm_input": None, "llm_thought": None,
            "action": None, "reward": 0.0, "kpis": None # 初始奖励为0
        }
        self.current_run_history.append(experience_step)

    def get_recent_history(self, num_steps: int) -> list:
        return self.current_run_history[-num_steps:]

    def get_last_reward(self) -> float:
        """获取最新完整步骤的奖励值。"""
        if not self.current_run_history:
            return 0.0
        # 返回最后一个时间步的奖励，默认为0.0
        return self.current_run_history[-1].get("reward", 0.0)

    def get_last_objective_integrand(self) -> Optional[float]:
        """【新增】获取上一步的目标函数值。"""
        return self.testcase_data.get("reward_state", {}).get("last_objective_integrand")

    def set_last_objective_integrand(self, value: float):
        """【新增】更新目标函数值。"""
        self.testcase_data["reward_state"]["last_objective_integrand"] = value

    def update_latest_step(self, update_data: Dict[str, Any]):
        if not self.current_run_history: return
        self.current_run_history[-1].update(update_data)

    def add_new_step(self, new_observation: dict, new_time: float):
        new_timestep_number = self.current_run_history[-1]['timestep'] + 1
        experience_step = {
            "timestep": new_timestep_number, "time": new_time, "observation": new_observation,
            "instruction": None, "llm_input": None, "llm_thought": None,
            "action": None, "reward": None, "kpis": None
        }
        self.current_run_history.append(experience_step)

    def save(self):
        self._all_memories[self.testid] = self.testcase_data
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self._all_memories, f, indent=4, ensure_ascii=False)
            logging.info(f"MemoryStore 已成功保存至 {self.filepath}")
        except IOError as e:
            logging.error(f"写入 {self.filepath} 失败: {e}")
