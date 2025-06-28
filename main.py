import os
import sys
import json
import logging
import asyncio
from typing import Dict, Optional
import re
from typing import Dict, Optional, Tuple
# --- AutoGen 核心组件 (根据新版API修正) ---
# --- AutoGen Core Components (Revised for new API) ---
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.messages import TextMessage

# --- 项目模块 ---
# --- Project Modules ---
#from src.extractor import run_extraction_pipeline
from src.boptest_client import (
    select_testcase,
    initialize,
    stop,
    set_step,
    advance_and_get_feedback
)
from src.memory_store import MemoryStore
from src.config import OUTPUT_DATA_DIR, HISTORY_WINDOW_SIZE, USER_DEMAND, CONTROL_STEP, SIMULATION_STEPS
from src.agents.information_synthesizer_agent import make_information_synthesizer_agent
from src.agents.decision_maker_agent import make_decision_maker_agent
from src.reward_calculator import RewardCalculator
from src.utils import convert_seconds_to_datetime_string
# --- 设置日志记录 ---
# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_json_file(filepath: str) -> Optional[Dict]:
    """一个辅助函数，用于加载JSON文件。"""
    if not os.path.exists(filepath):
        logging.error(f"JSON文件未找到: {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"读取或解析 {filepath} 时出错. Error: {e}")
        return None


# --- 【新增】: 解析LLM输出的辅助函数 ---
def parse_llm_output(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    一个辅助函数，用于从LLM的输出中解析出 <think> 和 <action> 的内容。
    """
    try:
        think_match = re.search(r'<think>(.*?)</think>', text, re.DOTALL)
        action_match = re.search(r'<action>(.*?)</action>', text, re.DOTALL)

        think_content = think_match.group(1).strip() if think_match else None
        action_content = action_match.group(1).strip() if action_match else None

        if not think_content or not action_content:
            logging.warning(f"解析LLM输出失败：未能找到 think 或 action 标签。原始文本: {text}")

        return think_content, action_content
    except Exception as e:
        logging.error(f"解析LLM输出时发生异常。错误: {e}")
        return None, None


async def run_agent_workflow():
    """
    项目的主工作流，现在使用async/await以兼容AutoGen。
    The main project workflow, now using async/await for AutoGen compatibility.
    """
    testid = None

    try:
        # === 阶段 0: 静态建筑信息提取 ===
        logging.info("=" * 50)
        logging.info("Executing Stage 0: Static Building Information Extraction.")
        #await asyncio.to_thread(run_extraction_pipeline)
        logging.info("Stage 0 finished.")

        # === 阶段 1: BOPTEST环境初始化 ===
        logging.info("=" * 50)
        logging.info("Executing Stage 1: Select Test Case and Initialize.")
        testcase_name = "bestest_air"
        testid = await asyncio.to_thread(select_testcase, testcase_name)

        if not testid:
            logging.error("选择测试案例失败，进程中止。 (Failed to select test case, halting.)")
            return
        # 【新增】: 设置全局控制步长
        await asyncio.to_thread(set_step, testid, CONTROL_STEP)
        start_time = 31*24*3600
        warmup_period = 86400
        initial_state = await asyncio.to_thread(initialize, testid, start_time, warmup_period)

        if not initial_state:
            logging.error("BOPTEST环境初始化失败。 (BOPTEST environment initialization failed.)")
            return

        logging.info("BOPTEST环境初始化成功! (BOPTEST environment initialized successfully!)")

        # === 阶段 2: 记录初始状态和静态信息到Memory Store (您的原有代码) ===
        logging.info("=" * 50)
        logging.info("Executing Stage 2: Log to Memory Store.")
        memory = MemoryStore(testid)
        # 【修复】: 创建 RewardCalculator 的一个实例
        reward_calculator = RewardCalculator()
        static_info_path = os.path.join(OUTPUT_DATA_DIR, "static_building_info.json")
        static_info = load_json_file(static_info_path)

        if static_info:
            memory.add_static_info(static_info)
        else:
            logging.warning("无法加载静态信息。")

        memory.add_initial_state(initial_state)
        # 注意：这里的save()会保存初始状态，后续步骤完成后会再次保存
        memory.save()

        # ======================================================================
        # === 主控制循环 ===
        # ======================================================================
        for i in range(SIMULATION_STEPS):
            current_step_data = memory.current_run_history[-1]
            current_step_num = memory.current_run_history[-1]['timestep']
            logging.info(
                "\n" + "#" * 70 + f"\n# Starting Control Loop: Step {current_step_num + 1}/{SIMULATION_STEPS}\n" + "#" * 70 + "\n")

            # --- 阶段 3: 信息综合 (含时间转换) ---
            information_synthesizer = make_information_synthesizer_agent()
            recent_history = memory.get_recent_history(num_steps=HISTORY_WINDOW_SIZE)

            # 【新增】: 转换时间并加入输入字典
            current_time_seconds = current_step_data.get('time')
            human_readable_time = convert_seconds_to_datetime_string(current_time_seconds)

            input_for_synthesizer = {
                "static_info": memory.testcase_data.get("static_info"),
                "history": recent_history,
                "human_readable_time": human_readable_time  # 将可读时间传入
            }
            synthesized_input = \
            (await information_synthesizer.run(task=json.dumps(input_for_synthesizer, indent=4))).messages[-1].content

            # --- 阶段 4: 决策制定 (含奖励反馈) ---
            decision_maker, instruction = make_decision_maker_agent()

            # 【修改】: 构造发送给LLM的完整任务字符串
            last_reward = memory.get_last_reward()
            # 【修复】: 确保 last_reward 不为 None，以避免格式化错误
            if last_reward is None:
                last_reward = 0.0
            llm_input_for_decision = (
                f"--- CONTEXT AND USER DEMAND ---\n"
                f"{synthesized_input}\n\n"
                f"User's primary goal: {USER_DEMAND}\n\n"
                f"--- FEEDBACK ON YOUR LAST ACTION ---\n"
                f"Your previous action resulted in a reward of: {last_reward:.4f}.\n"
                f"A higher reward is better. If the reward is negative, you must analyze why and adjust your strategy."
            )

            llm_raw_output = (await decision_maker.run(task=llm_input_for_decision)).messages[-1].content
            llm_thought, llm_action_str = parse_llm_output(llm_raw_output)

            # --- 阶段 5: 环境交互与反馈记录 ---
            logging.info(f"--- [Step {i + 1}] Stage 5: Environment Interaction & Feedback ---")
            if llm_thought and llm_action_str:
                try:
                    action_json = json.loads(llm_action_str)
                    print(f"\n[Step {current_step_num + 1}] Action Decided: {action_json}")

                    feedback = await asyncio.to_thread(advance_and_get_feedback, testid, action_json)

                    if feedback:
                        kpis = feedback.get("kpis", {})
                        last_obj = memory.get_last_objective_integrand()
                        # 【修复】: 通过实例来调用方法
                        reward, new_obj = reward_calculator.calculate_reward_ener_plus_discomfort(kpis, last_obj)
                        memory.set_last_objective_integrand(new_obj)

                        print(f"[Step {current_step_num + 1}] KPIs Received: {kpis}")
                        print(f"[Step {current_step_num + 1}] Reward Calculated: {reward:.4f}")

                        memory.update_latest_step({
                            "instruction": instruction, "llm_input": llm_input_for_decision,
                            "llm_thought": llm_thought, "action": action_json,
                            "kpis": kpis, "reward": reward
                        })

                        new_obs = feedback.get("observation", {})
                        new_time = new_obs.pop('time', 0.0)
                        memory.add_new_step(new_observation=new_obs, new_time=new_time)

                        memory.save()
                    else:
                        break
                except json.JSONDecodeError: break
            else:
                break  # 如果LLM输出无法解析，则终止循环

    finally:
        # === 最终步骤: 停止测试案例 ===
        if testid:
            logging.info("=" * 50 + "\nExecuting Final Stage: Stopping test case\n" + "=" * 50)
            await asyncio.to_thread(stop, testid)
            logging.info("Test case stopped.")


if __name__ == "__main__":
    if not os.path.exists('src/__init__.py'):
        with open('src/__init__.py', 'w') as f: pass
    if not os.path.exists('src/core/__init__.py'):
        with open('src/core/__init__.py', 'w') as f: pass
    if not os.path.exists('src/agents/__init__.py'):
        with open('src/agents/__init__.py', 'w') as f: pass

    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    try:
        import nest_asyncio

        nest_asyncio.apply()
    except ImportError:
        logging.warning("nest_asyncio未找到。将使用`asyncio.run`。")

    try:
        asyncio.run(run_agent_workflow())
    except KeyboardInterrupt:
        logging.info("程序被用户中断。")

