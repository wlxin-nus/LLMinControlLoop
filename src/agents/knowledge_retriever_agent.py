import logging
from autogen_agentchat.agents import AssistantAgent
from typing import Tuple

# --- 项目模块 ---
from src.core.llm_client import get_deepseek_client
from src.core.prompt_loader import load_prompt
from src.config import GRAPHRAG_SETTINGS_PATH

# 仅在需要时尝试导入工具，以保持灵活性
try:
    from autogen_ext.tools.graphrag import LocalSearchTool

    AUTOGEN_EXT_INSTALLED = True
except ImportError:
    AUTOGEN_EXT_INSTALLED = False

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def make_knowledge_retriever_agent(
        name: str = "KnowledgeRetrieverAgent",
        prompt_file: str = "knowledge_retriever_prompt",
        **kwargs
) -> AssistantAgent:
    """
    创建一个专门负责从GraphRAG知识库中检索信息的代理。
    """
    if not AUTOGEN_EXT_INSTALLED:
        raise ImportError(
            "`autogen_ext` or its dependencies are not installed. KnowledgeRetrieverAgent cannot be created.")

    agent_model_client = get_deepseek_client()
    instruction = load_prompt(prompt_file)

    try:
        logging.info(f"KnowledgeRetrieverAgent is initializing GraphRAG tool from: {GRAPHRAG_SETTINGS_PATH}")
        graphrag_tool = LocalSearchTool.from_settings(settings_path=GRAPHRAG_SETTINGS_PATH)
    except Exception as e:
        logging.error(f"Fatal error initializing GraphRAG tool: {e}")
        # 如果工具初始化失败，则无法创建此代理
        raise

    agent = AssistantAgent(
        name=name,
        system_message=instruction,
        model_client=agent_model_client,
        tools=[graphrag_tool],
        **kwargs
    )

    return agent