import logging
from autogen_agentchat.agents import AssistantAgent
from typing import Tuple

# --- 项目模块 ---
from src.core.llm_client import get_deepseek_client
from src.core.prompt_loader import load_prompt

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def make_decision_maker_agent(
        name: str = "DecisionMakerAgent",
        prompt_file: str = "decision_maker_prompt",
        **kwargs
) -> Tuple[AssistantAgent, str]:
    """
    配置并返回一个用于决策的AutoGen AssistantAgent。
    这个版本是一个纯粹的思考者，不携带任何工具。
    """
    agent_model_client = get_deepseek_client()
    instruction = load_prompt(prompt_file)

    # 决策代理现在不再直接与工具交互
    agent = AssistantAgent(
        name=name,
        system_message=instruction,
        model_client=agent_model_client,
        **kwargs
    )

    return agent, instruction