import os
import sys
import json
import logging
import asyncio
from typing import Dict, Optional

# --- AutoGen 核心组件 (根据新版API修正) ---
# --- AutoGen Core Components (Revised for new API) ---
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.messages import TextMessage

# --- 项目模块 ---
# --- Project Modules ---
#from src.extractor import run_extraction_pipeline
from src.boptest_client import select_testcase, initialize, stop
from src.memory_store import MemoryStore
from src.config import OUTPUT_DATA_DIR
from src.agents.information_synthesizer_agent import make_information_synthesizer_agent

# --- 设置日志记录 ---
# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_json_file(filepath: str) -> Optional[Dict]:
    """一个辅助函数，用于加载JSON文件。 (A helper function to load a JSON file.)"""
    if not os.path.exists(filepath):
        logging.error(f"JSON文件未找到 (JSON file not found): {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"读取或解析 {filepath} 时出错 (Error reading or parsing {filepath}). Error: {e}")
        return None


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

        start_time = 0
        warmup_period = 86400
        initial_state = await asyncio.to_thread(initialize, testid, start_time, warmup_period)

        if not initial_state:
            logging.error("BOPTEST环境初始化失败。 (BOPTEST environment initialization failed.)")
            return

        logging.info("BOPTEST环境初始化成功! (BOPTEST environment initialized successfully!)")

        # === 阶段 2: 记录初始状态和静态信息到Memory Store ===
        logging.info("=" * 50)
        logging.info("Executing Stage 2: Log to Memory Store.")
        memory = MemoryStore(testid)
        static_info_filename = "static_building_info_v3.json"
        static_info_path = os.path.join(OUTPUT_DATA_DIR, static_info_filename)
        static_info = load_json_file(static_info_path)

        if static_info:
            memory.add_static_info(static_info)
        else:
            logging.warning(f"无法加载静态信息 (Could not load static info)。")

        memory.add_initial_state(initial_state)
        memory.save()

        # === 阶段 3: 信息综合与经验提炼 (单代理任务模式) ===
        # === Stage 3: Information Synthesis (Single Agent Task Mode) ===
        logging.info("=" * 50)
        logging.info("Executing Stage 3: Information Synthesis Agent Workflow.")

        # 3.1 创建代理
        # 3.1 Create the agent
        information_synthesizer = make_information_synthesizer_agent()

        # 3.2 准备输入信息
        # 3.2 Prepare input message
        current_memory = memory.testcase_data
        input_for_synthesizer = {
            "static_info": current_memory.get("static_info"),
            "history": current_memory.get("history")
        }
        task_message_content = json.dumps(input_for_synthesizer, indent=4)

        # 3.3 [核心修正] 直接在单个代理上运行任务
        # 3.3 [KEY FIX] Directly run the task on the single agent
        logging.info("--- 向信息处理器代理发送任务... (Sending task to Information Synthesizer Agent...) ---")
        chat_result = await information_synthesizer.run(task=task_message_content)

        # 3.4 打印结果
        # 3.4 Print the result
        # 结果在最后一个消息的内容中
        # The result is in the content of the last message
        synthesized_input = chat_result.messages[-1].content if chat_result.messages else "代理没有返回消息。"

        logging.info("--- 信息处理器代理已完成任务。 (Information Synthesizer Agent has completed the task.) ---")
        print("\n" + "=" * 25 + " 精炼后的输入文本 (Synthesized Input Text) " + "=" * 25)
        print(synthesized_input)
        print("=" * 81 + "\n")

    finally:
        # === 最终步骤: 停止测试案例 ===
        # === Final Step: Stop the Test Case ===
        if testid:
            logging.info("=" * 50)
            logging.info(f"Executing Final Stage: Stopping test case with testid: {testid}")
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

