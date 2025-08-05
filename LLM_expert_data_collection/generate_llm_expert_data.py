# ==============================================================================
#
# LLM_expert_data_collection/generate_llm_expert_data.py
#
# ==============================================================================
#
# 目的:
#   - 使用LLM作为专家控制器，在BOPTEST环境中运行7天模拟。
#   - 采用与PPO基准完全相同的"过程奖励"机制来计算每一步的奖励。
#   - 生成一个与RBC专家数据格式完全对齐的数据集，用于后续的模仿学习。
#   - [V5] 增强LLM感知能力，使其接收完整的26维状态向量。
#
# ==============================================================================

# --- 基础库与标准库 ---
import os
import sys
import json
import logging
import requests
import asyncio
import pandas as pd
import numpy as np
import re
from collections import deque
from typing import Dict, Optional, Any, Tuple

# --- 关键：添加项目根目录到Python路径 ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# --- 从您的LLMinControlLoop框架中导入模块 ---
try:
    from src.boptest_client import (
        select_testcase,
        initialize,
        stop,
        set_step,
        advance
    )
    from src.agents.information_synthesizer_agent import make_information_synthesizer_agent
    from src.agents.decision_maker_agent import make_decision_maker_agent
    from src.utils import convert_seconds_to_datetime_string
except ImportError as e:
    print("=" * 80)
    print("[IMPORT ERROR] 无法导入 'src' 目录下的模块。")
    print(f"错误详情: {e}")
    print("请确保此脚本位于 'LLM_expert_data_collection' 文件夹下，")
    print("且该文件夹与 'src' 文件夹在同一个父目录中。")
    print("=" * 80)
    sys.exit(1)

# --- 日志记录设置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# 阶段一：全局参数与配置
# ==============================================================================

# --- BOPTEST & 模拟参数 ---
BOPTEST_URL = 'http://127.0.0.1:80'
TESTCASE = 'bestest_air'
TRAINING_START_TIME = 146 * 24 * 3600
TESTING_START_TIME = 153 * 24 * 3600
EPISODE_LENGTH = 7 * 24 * 3600
WARMUP_PERIOD = 7 * 24 * 3600

# --- 周期定义 ---
CONTROL_PERIOD = 900
SAMPLING_PERIOD = 60

# --- 路径定义 ---
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(OUTPUT_DIR, "datasets")
STATIC_INFO_PATH = os.path.join(PROJECT_ROOT, "data", "output", "static_building_info.json")
os.makedirs(DATASET_DIR, exist_ok=True)

# --- 调试与奖励权重 ---
DEBUG_MODE = True
W_COST, W_TEMP, W_SLEW = 100.0, 1.0, 10.0


# ==============================================================================
# 阶段二：辅助函数
# ==============================================================================

def get_price_by_time_of_use(time_seconds: float) -> float:
    ON_PEAK_PRICE, MID_PEAK_PRICE, OFF_PEAK_PRICE = 0.13814, 0.08420, 0.04440
    seconds_in_day = time_seconds % 86400
    if 12 * 3600 <= seconds_in_day < 19 * 3600:
        return ON_PEAK_PRICE
    elif (6 * 3600 <= seconds_in_day < 12 * 3600) or (19 * 3600 <= seconds_in_day < 22 * 3600):
        return MID_PEAK_PRICE
    else:
        return OFF_PEAK_PRICE


def parse_llm_action(text: str) -> float:
    try:
        action_match = re.search(r'<action>(.*?)</action>', text, re.DOTALL)
        if action_match:
            action_str = action_match.group(1).strip()
            if action_str.startswith("```json"): action_str = action_str[7:]
            if action_str.endswith("```"): action_str = action_str[:-3]
            action_json = json.loads(action_str)
            return np.clip(float(action_json['fcu_oveFan_u']), 0.0, 1.0)

        json_block_match = re.search(r'```json(.*?)```', text, re.DOTALL)
        if json_block_match:
            action_str = json_block_match.group(1).strip()
            action_json = json.loads(action_str)
            return np.clip(float(action_json['fcu_oveFan_u']), 0.0, 1.0)

        action_json = json.loads(text)
        return np.clip(float(action_json['fcu_oveFan_u']), 0.0, 1.0)
    except Exception as e:
        logging.error(f"解析LLM动作失败: {e}. Raw text: '{text}'. 返回安全动作0.0。")
        return 0.0


def load_json_file(path: str) -> Dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning(f"JSON文件未找到: {path}. 返回空字典。")
        return {}
    except json.JSONDecodeError:
        logging.error(f"无法解析JSON文件: {path}. 返回空字典。")
        return {}


# ==============================================================================
# 阶段三：主数据生成函数
# ==============================================================================

async def generate_llm_expert_dataset(mode: str = 'train'):
    logging.info(f"\n{'=' * 80}\n===== 开始生成LLM专家数据集 ({mode.upper()}) =====\n{'=' * 80}")

    testid = None
    dataset = []
    start_time = TRAINING_START_TIME if mode == 'train' else TESTING_START_TIME

    csv_output_filename = os.path.join(DATASET_DIR, f'llm_expert_data_{mode}.csv')
    llm_log_filename = os.path.join(DATASET_DIR, f'llm_interactions_{mode}.jsonl')

    try:
        logging.info("\n--- [步骤 1/5] BOPTEST环境初始化 ---")
        testid = await asyncio.to_thread(select_testcase, TESTCASE)
        if not testid: raise RuntimeError("选择测试案例失败。")
        await asyncio.to_thread(set_step, testid, SAMPLING_PERIOD)
        initial_state = await asyncio.to_thread(initialize, testid, start_time, WARMUP_PERIOD)
        if not initial_state: raise RuntimeError("BOPTEST环境初始化失败。")
        logging.info(f"BOPTEST环境初始化成功! Test ID: {testid}")

        logging.info("\n--- [步骤 2/5] 初始化代理、状态跟踪器和静态信息 ---")
        information_synthesizer = make_information_synthesizer_agent()
        decision_maker, _ = make_decision_maker_agent()

        static_info = load_json_file(STATIC_INFO_PATH)
        if not static_info:
            logging.warning("未能加载静态建筑信息，LLM的上下文将受限。")

        y_current = initial_state
        last_llm_action, last_reward = 0.0, 0.0
        history_temp = deque([y_current.get('zon_reaTRooAir_y', 297.15)] * 4, maxlen=4)
        history_power = deque([y_current.get('fcu_reaPCoo_y', 0)] * 4, maxlen=4)

        logging.info("代理和状态跟踪器准备就绪。")

        logging.info("\n--- [步骤 3/5] 进入主控制循环 ---")
        total_control_steps = int(EPISODE_LENGTH / CONTROL_PERIOD)
        steps_per_control = int(CONTROL_PERIOD / SAMPLING_PERIOD)

        for i in range(total_control_steps):
            logging.info(f"\n" + "-" * 30 + f" 外层控制周期 {i + 1}/{total_control_steps} " + "-" * 30)

            y_control_period_start = y_current

            # --- a.1. 为数据集和LLM准备统一的26维数值状态 ---
            state_vector = {}
            forecast_points = ['TDryBul', 'HGloHor', 'PriceElectricPowerDynamic']
            forecast_payload = {'point_names': forecast_points, 'horizon': 4 * CONTROL_PERIOD,
                                'interval': CONTROL_PERIOD}
            res_forecast = requests.put(f'{BOPTEST_URL}/forecast/{testid}', json=forecast_payload)
            forecast_data = res_forecast.json().get('payload', {})
            for point in forecast_points:
                values = forecast_data.get(point, [0] * 5)
                state_vector[f'obs_{point}_current'] = values[0]
                for j in range(4): state_vector[f'obs_{point}_future_{j + 1}'] = values[j + 1]

            current_temp = y_control_period_start.get('zon_reaTRooAir_y', 297.15)
            current_power = y_control_period_start.get('fcu_reaPCoo_y', 0)
            temp_vector, power_vector = [current_temp] + list(history_temp), [current_power] + list(history_power)
            state_vector['obs_temp_current'] = temp_vector[0]
            for j in range(4): state_vector[f'obs_temp_past_{j + 1}'] = temp_vector[j + 1]
            state_vector['obs_power_current'] = power_vector[0]
            for j in range(4): state_vector[f'obs_power_past_{j + 1}'] = power_vector[j + 1]
            state_vector['obs_time_sec_of_day'] = y_control_period_start.get('time', 0) % 86400

            # --- a.2. 为LLM准备文本状态 (使用完整的26维向量) ---
            input_for_synthesizer = {
                "static_info": static_info,
                "full_state_vector": state_vector,
                "human_readable_time": convert_seconds_to_datetime_string(y_control_period_start.get('time')),
                "data_schema_notes": {
                    "temporal_order_note": "For keys with '_past_N', N=1 is the most recent past step (t-15m), and N=4 is the oldest (t-60m). For keys with '_future_N', N=1 is the next future step (t+15m)."
                }
            }
            synthesized_input = \
            (await information_synthesizer.run(task=json.dumps(input_for_synthesizer, indent=4))).messages[-1].content

            # --- a.3. 调用LLM进行决策 ---
            user_goal = ("Your goal is to be an expert building controller. Minimize a weighted sum of: "
                         "1. Energy Cost (weight=100.0), 2. Thermal Discomfort (weight=1.0), "
                         "3. Control Action Slew Rate (weight=10.0). "
                         "Provide the fan speed 'fcu_oveFan_u' (0.0 to 1.0) in JSON format.")
            llm_input_for_decision = (
                f"[CURRENT STATE]:\n{synthesized_input}\n\n[USER GOAL]:\n{user_goal}\n\n[LAST REWARD]:\n{last_reward:.4f}")
            llm_raw_output = (await decision_maker.run(task=llm_input_for_decision)).messages[-1].content
            action_llm = parse_llm_action(llm_raw_output)

            # --- b. 内部循环：执行并计算过程奖励 ---
            process_energy_cost, process_temp_violation_squared = 0.0, 0.0
            y_sample_iterator = y_control_period_start
            for _ in range(steps_per_control):
                control_signal = {'fcu_oveFan_u': action_llm, 'fcu_oveFan_activate': 1, 'fcu_oveTSup_activate': 1,
                                  'fcu_oveTSup_u': 291.15}
                y_next_sample = await asyncio.to_thread(advance, testid, control_signal)
                if not y_next_sample: break
                power = y_sample_iterator.get('fcu_reaPCoo_y', 0)
                price = get_price_by_time_of_use(y_sample_iterator.get('time', 0))
                process_energy_cost += price * (power / 1000.0) * (SAMPLING_PERIOD / 3600.0)
                temp = y_sample_iterator.get('zon_reaTRooAir_y', 0)
                time_in_day = y_sample_iterator.get('time', 0) % 86400
                setpoint = (24.0 + 273.15) if 28800 <= time_in_day < 64800 else (30.0 + 273.15)
                process_temp_violation_squared += max(0, temp - setpoint) ** 2
                y_sample_iterator = y_next_sample

            y_current = y_sample_iterator
            if not y_current: break

            # --- c. 周期结束：计算最终奖励并记录数据 ---
            action_slew_rate = (action_llm - last_llm_action) ** 2
            final_reward = -(
                        W_COST * process_energy_cost + W_TEMP * process_temp_violation_squared + W_SLEW * action_slew_rate)
            last_reward = final_reward

            log_entry = {'step': i, 'reward': final_reward, 'action_llm': action_llm,
                         'unweighted_energy_cost': process_energy_cost,
                         'unweighted_temp_violation_sq': process_temp_violation_squared,
                         'unweighted_action_slew': action_slew_rate}
            log_entry.update(state_vector)
            dataset.append(log_entry)

            pd.DataFrame(dataset).to_csv(csv_output_filename, index=False)
            with open(llm_log_filename, 'a', encoding='utf-8') as f:
                log_line = json.dumps({'step': i, 'input': llm_input_for_decision, 'output': llm_raw_output})
                f.write(log_line + '\n')

            if DEBUG_MODE:
                logging.info(f"[DEBUG] Parsed LLM Action: {action_llm:.4f} | Final Reward: {final_reward:.4f}")
                logging.info(f" incremental data saved to {csv_output_filename} and {llm_log_filename}")

            # --- d. 更新历史状态 ---
            last_llm_action = action_llm
            history_temp.append(current_temp)
            history_power.append(current_power)

        logging.info("\n--- [步骤 4/5] 主控制循环完成 ---")
        logging.info(f"最终数据集已生成，共 {len(dataset)} 条记录。")

    except Exception as e:
        logging.error(f"\n在主工作流中发生严重错误: {e}", exc_info=True)

    finally:
        logging.info("\n--- [步骤 5/5] 清理BOPTEST实例 ---")
        if testid:
            await asyncio.to_thread(stop, testid)
            logging.info(f"已停止并清理BOPTEST测试实例: {testid}")
        logging.info(f"\n{'=' * 80}\n===== LLM专家数据集生成流程结束 =====\n{'=' * 80}")


# ==============================================================================
# 阶段四：主程序入口
# ==============================================================================
if __name__ == "__main__":
    os.chdir(PROJECT_ROOT)
    logging.info(f"工作目录已更改为项目根目录: {os.getcwd()}")

    try:
        import nest_asyncio

        nest_asyncio.apply()
    except ImportError:
        pass

    asyncio.run(generate_llm_expert_dataset(mode='train'))