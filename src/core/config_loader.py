import yaml
from pathlib import Path
from typing import Dict, Any

# 从主配置中导入CONFIG_DIR路径
from src.config import CONFIG_DIR


def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """
    一个通用的函数，用于加载和解析任何YAML文件。
    A generic function to load and parse any YAML file.

    Args:
        file_path (Path): The path to the YAML file.

    Returns:
        Dict[str, Any]: The content of the YAML file as a dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the config file is not valid YAML.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Error parsing YAML file {file_path}: {e}")


def load_objectives_config() -> Dict[str, Any]:
    """加载目标配置文件。 (Loads the objectives configuration file.)"""
    objectives_path = Path(CONFIG_DIR) / 'objectives_config.yaml'
    return load_yaml_file(objectives_path)

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