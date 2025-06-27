# src/agents/information_synthesizer_agent.py

from autogen_agentchat.agents import AssistantAgent
# Assuming the user's project structure has a 'src' root in PYTHONPATH
from src.core.llm_client import get_deepseek_client
from src.core.prompt_loader import load_prompt

def make_information_synthesizer_agent(
    name: str = "Information_Synthesizer",
    prompt_file: str = "information_synthesizer_prompt",
    **kwargs
) -> AssistantAgent:
    """
    创建一个AssistantAgent，它将静态和动态的建筑信息综合成一个简洁的摘要。
    Creates an AssistantAgent that synthesizes static and dynamic building
    information into a concise summary.

    Args:
        name (str, optional): The name of the agent.
        prompt_file (str, optional): The filename of the system prompt.
        **kwargs: Additional keyword arguments for the AssistantAgent.

    Returns:
        AssistantAgent: An instance of the Information Synthesizer agent.
    """
    # 获取配置好的Deepseek客户端
    # Get the configured Deepseek client
    agent_model_client = get_deepseek_client()

    # 从指定的提示文件加载系统消息
    # Load the system message from the specified prompt file
    system_message = load_prompt(prompt_file)

    # [关键修正] 使用新的'model_client'参数代替旧的'llm_config'
    # [KEY FIX] Use the new 'model_client' parameter instead of the old 'llm_config'
    return AssistantAgent(
        name=name,
        model_client=agent_model_client,
        system_message=system_message,
        **kwargs
    )

