import yaml
import os
from dotenv import load_dotenv

# 确保环境变量已加载
# Ensure environment variables are loaded
load_dotenv()

def load_config(path: str = "configs/agent_config.yaml") -> dict:
    """
    加载并解析YAML配置文件。
    Loads and parses the YAML configuration file.

    Args:
        path (str, optional): YAML配置文件的路径。
                              Path to the YAML config file.

    Returns:
        dict: 解析后的配置字典。
              The parsed configuration dictionary.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"配置文件未找到: {path}。请确保文件存在于正确的路径。")
    except yaml.YAMLError as e:
        raise ValueError(f"解析YAML文件时出错: {path}。错误: {e}")

