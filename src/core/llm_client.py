import os
from autogen_ext.models.openai import OpenAIChatCompletionClient
from .config_loader import load_config

def get_deepseek_client() -> OpenAIChatCompletionClient:
    """
    根据配置文件创建一个Deepseek LLM客户端。
    Creates a Deepseek LLM client based on the configuration file.

    Returns:
        OpenAIChatCompletionClient: 配置好的AutoGen客户端实例。
                                    A configured AutoGen client instance.
    """
    config = load_config()
    model_cfg = config["model"]
    api_key = os.getenv(model_cfg["api_key_env_var"])

    if not api_key:
        raise ValueError(f"环境变量 '{model_cfg['api_key_env_var']}' 未设置或为空。")

    # 注意: Autogen的OpenAIChatCompletionClient可以用于任何与OpenAI API兼容的端点，
    # 包括Deepseek。我们通过base_url来指定API地址。
    # Note: Autogen's OpenAIChatCompletionClient can be used for any OpenAI-compatible
    # endpoint, including Deepseek. We specify the API address via the base_url.
    return OpenAIChatCompletionClient(
        model=model_cfg["name"],
        base_url=model_cfg["base_url"],
        api_key=api_key,
        # 从配置中读取其他参数
        # Read other parameters from the config
        temperature=model_cfg["parameters"]["temperature"],
        max_tokens=model_cfg["parameters"]["max_tokens"],
        top_p=model_cfg["parameters"]["top_p"],
        # 为autogen提供模型能力信息
        # Provide model capability information for autogen
        model_info={
            "family": model_cfg["family"],
            "json_output": model_cfg["json_output"],
            "function_calling": model_cfg["function_calling"],
            "vision": model_cfg["vision"],
            "structured_output": model_cfg["structured_output"]
        }
    )