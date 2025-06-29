import os
import sys
import json
import logging
import asyncio
from typing import Dict, Optional
import re
from typing import Dict, Optional, Tuple
# --- 项目模块 ---
# --- Project Modules ---
from src.extractor import run_extraction_pipeline
from src.boptest_client import (
    select_testcase,
    initialize,
    stop,
    set_step,
    advance_and_get_feedback
)
from src.memory_store import MemoryStore
from src.config import (
    HISTORY_WINDOW_SIZE, CONTROL_STEP, SIMULATION_STEPS,
    SELECTED_OBJECTIVE, CONTROLLABLE_PARAM_DESC, TEST_CASE_NAME, START_TIME, WARMUP_PERIOD, USE_GRAPHRAG_TOOL
)
from src.agents.information_synthesizer_agent import make_information_synthesizer_agent
from src.agents.decision_maker_agent import make_decision_maker_agent
from src.agents.knowledge_retriever_agent import make_knowledge_retriever_agent
from src.reward_calculator import RewardCalculator
from src.utils import convert_seconds_to_datetime_string
from src.core.config_loader import load_objectives_config
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
    【修复】: 一个更健壮的解析器，用于从LLM输出中提取 <think> 和 <action>。
    它能处理LLM忘记<action>标签，并直接输出JSON代码块的情况。
    """
    try:
        think_content = None
        action_content = None

        # 1. 提取 <think> 内容
        think_match = re.search(r'<think>(.*?)</think>', text, re.DOTALL)
        if think_match:
            think_content = think_match.group(1).strip()

        # 2. 提取 <action> 内容 (多种策略)
        # 策略A: 严格匹配 <action> 标签
        action_match_strict = re.search(r'<action>(.*?)</action>', text, re.DOTALL)
        if action_match_strict:
            action_content = action_match_strict.group(1).strip()
        else:
            # 策略B: 查找markdown格式的JSON代码块
            json_block_match = re.search(r'```json(.*?)```', text, re.DOTALL)
            if json_block_match:
                action_content = json_block_match.group(1).strip()
            else:
                # 策略C: 查找最后一个独立的JSON对象
                # 从</think>之后开始查找，避免匹配到think内容里的JSON
                think_end_pos = think_match.end() if think_match else -1
                search_area = text[think_end_pos:] if think_end_pos != -1 else text

                # 寻找最后一个 '{' 和 '}' 来捕获JSON
                start_brace = search_area.rfind('{')
                end_brace = search_area.rfind('}')
                if start_brace != -1 and end_brace > start_brace:
                    potential_json = search_area[start_brace:end_brace + 1]
                    try:
                        # 验证它是否是有效的JSON
                        json.loads(potential_json)
                        action_content = potential_json.strip()
                    except json.JSONDecodeError:
                        logging.warning("Found a bracket pair, but it's not valid JSON.")
                        pass

        if not think_content or not action_content:
            logging.warning(f"Parsing failed: Could not find both <think> and a valid <action>/JSON block.")

        return think_content, action_content

    except Exception as e:
        logging.error(f"An exception occurred during LLM output parsing: {e}")
        return None, None


async def run_agent_workflow():
    """
    项目的主工作流，现在使用async/await以兼容AutoGen。
    The main project workflow, now using async/await for AutoGen compatibility.
    """
    testid = None

    try:
        # # === 阶段 0: 静态建筑信息提取 ===(建议分两部分来)
        # logging.info("=" * 50)
        # logging.info("Executing Stage 0: Static Building Information Extraction.")
        # await asyncio.to_thread(run_extraction_pipeline)
        # logging.info("Stage 0 finished.")
        # # === 阶段 0: 静态建筑信息提取 ===

        # 【修改】: 加载并选择目标
        objectives_config = load_objectives_config()
        if SELECTED_OBJECTIVE not in objectives_config:
            raise ValueError(f"Selected objective '{SELECTED_OBJECTIVE}' not found in objectives_config.yaml")

        selected_objective_config = objectives_config[SELECTED_OBJECTIVE]
        objective_description = selected_objective_config['description']
        reward_function_name = selected_objective_config['reward_function']

        # 动态组装完整的用户需求
        user_demand_for_llm = f"{CONTROLLABLE_PARAM_DESC}\n{objective_description}"

        logging.info(f"Running simulation with objective: '{SELECTED_OBJECTIVE}'")
        logging.info(f"Reward function to be used: '{reward_function_name}'")

        # === 阶段 1: BOPTEST环境初始化 ===
        logging.info("=" * 50)
        logging.info("Executing Stage 1: Select Test Case and Initialize.")
        testcase_name = TEST_CASE_NAME
        testid = await asyncio.to_thread(select_testcase, testcase_name)

        if not testid:
            logging.error("选择测试案例失败，进程中止。 (Failed to select test case, halting.)")
            return
        # 【新增】: 设置全局控制步长
        await asyncio.to_thread(set_step, testid, CONTROL_STEP)
        start_time = START_TIME
        warmup_period = WARMUP_PERIOD
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
        static_info_path = os.path.join(os.path.dirname(__file__), 'data', 'output', 'static_building_info.json')
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

            # --- 【新增】阶段 3.5: 知识检索 (条件性执行) ---
            retrieved_knowledge = "No external knowledge was consulted."
            if USE_GRAPHRAG_TOOL:
                logging.info(f"--- [Step {i + 1}] Stage 3.5: Knowledge Retrieval ---")
                try:
                    knowledge_retriever = make_knowledge_retriever_agent()
                    # 构造给知识检索代理的输入
                    retriever_input = (
                        f"[CURRENT STATE]:\n{synthesized_input}\n\n"
                        f"[USER GOAL]:\n{user_demand_for_llm}"
                    )
                    # 运行知识检索代理
                    retrieval_result = await knowledge_retriever.run(task=retriever_input)
                    # 知识就是最后一个消息的内容
                    retrieved_knowledge = retrieval_result.messages[-1].content
                    logging.info("--- Knowledge retrieval successful ---")
                except Exception as e:
                    logging.error(f"Knowledge retrieval failed: {e}. Proceeding without external knowledge.")

            # --- 阶段 4: 最终决策 ---
            logging.info(f"--- [Step {i + 1}] Stage 4: Decision Making ---")
            decision_maker, instruction = make_decision_maker_agent()
            last_reward = memory.get_last_reward()
            if last_reward is None: last_reward = 0.0

            # 【修改】: 构造包含所有信息的最终输入
            llm_input_for_decision = (
                f"//-- INPUTS --//\n"
                f"[CURRENT STATE]:\n{synthesized_input}\n\n"
                f"[RETRIEVED KNOWLEDGE]:\n{retrieved_knowledge}\n\n"
                f"[USER GOAL]:\n{user_demand_for_llm}\n\n"
                f"[LAST REWARD]:\n{last_reward:.4f}"
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
                        # 【修改】: 动态调用奖励函数
                        reward_function = getattr(reward_calculator, reward_function_name)
                        reward, new_obj = reward_function(kpis, last_obj)

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

