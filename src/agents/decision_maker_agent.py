import logging
from autogen_agentchat.agents import AssistantAgent

# 【修改】: 导入通用的 Deepseek 客户端获取函数
# [CHANGE]: Import the generic Deepseek client getter function
from src.core.llm_client import get_deepseek_client
# 从项目中加载prompt的工具 (无变化)
# Load prompt utility from the project (no change)
from src.core.prompt_loader import load_prompt

# 设置日志 (无变化)
# Setup logging (no change)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def make_decision_maker_agent(
        name: str = "DecisionMakerAgent",
        prompt_file: str = "decision_maker_prompt",
        **kwargs
) -> tuple[AssistantAgent, str]:
    """
    配置并返回一个专门用于决策的AutoGen AssistantAgent。
    此版本使用标准的 get_deepseek_client() 来获取LLM客户端，以确保一致性。

    Configures and returns an AutoGen AssistantAgent specialized for making control decisions.
    This version uses the standard get_deepseek_client() to ensure consistency.

    Args:
        name (str, optional): The name of the agent.
        prompt_file (str, optional): The filename of the system prompt.
        **kwargs: Additional keyword arguments for the AssistantAgent.

    Returns:
        Tuple[AssistantAgent, str]: A tuple containing the configured agent
                                     and its system message string.
    """
    # 【修改】: 获取标准的 Deepseek 客户端
    # [CHANGE]: Get the standard Deepseek client
    agent_model_client = get_deepseek_client()

    # 加载此代理的特定指令（prompt） (无变化)
    # Load the specific instruction (prompt) for this agent (no change)
    instruction = load_prompt(prompt_file)

    # 创建代理实例
    agent = AssistantAgent(
        name=name,
        system_message=instruction,
        model_client=agent_model_client,
        **kwargs
    )

    # 【修改】: 返回代理和指令
    return agent, instruction
