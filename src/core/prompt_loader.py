import os

# 定义prompts目录的绝对路径，确保在任何地方调用都正确
# Define the absolute path to the prompts directory for robust calling
PROMPT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")

def load_prompt(name: str) -> str:
    """
    从prompts目录加载一个指定的提示文件。
    Loads a specified prompt file from the prompts directory.

    Args:
        name (str): 提示文件的名称（不含.txt后缀）。
                    The name of the prompt file (without the .txt extension).

    Returns:
        str: 提示文件的内容。
             The content of the prompt file.
    """
    path = os.path.join(PROMPT_DIR, f"{name}.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"提示文件未找到: {path}。请确保文件存在于 'prompts' 目录中。")

