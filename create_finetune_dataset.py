# -*- coding: utf-8 -*-
import json
import argparse
import re
from pathlib import Path
from typing import Dict, Any, List, Optional


def extract_section(text: str, title: str) -> Optional[str]:
    """
    从多段文本中根据标题提取特定部分的内容。
    例如，从 `... [TITLE]:\n content ...` 中提取 `content`。

    Args:
        text: 包含多个部分的完整文本。
        title: 要提取的部分的标题 (例如, "CURRENT STATE")。

    Returns:
        提取到的内容字符串，如果未找到则返回 None。
    """
    # 使用正则表达式匹配标题和其后的内容
    # re.DOTALL 使得 '.' 可以匹配包括换行符在内的任意字符
    pattern = re.compile(rf"\[{re.escape(title)}\]:\n(.*?)(?=\n\[[A-Z\s]+\]:|\Z)", re.DOTALL)
    match = pattern.search(text)
    if match:
        # .strip() 用于移除内容开头和结尾的空白字符
        return match.group(1).strip()
    return None


def format_llama_factory_entry(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 memory_store 中的单条记录转换为 LLaMA-Factory 的 Alpaca 格式。

    Args:
        record:来自 memory_store['history'] 的单条记录字典。

    Returns:
        一个符合 Alpaca 格式的字典。
    """
    # FIX: 确保即使值为 null/None，也将其视为空字符串，防止 TypeError
    llm_input_text = record.get("llm_input") or ""

    # 1. 提取 [USER GOAL] 并构建 'instruction'
    user_goal = extract_section(llm_input_text, "USER GOAL")
    instruction = (
        "You are a world-class building control AI expert. "
        "Your mission is to generate an optimal control action based on the provided context. "
        "Your primary objective is as follows: "
        f"{user_goal if user_goal else 'No specific goal provided.'}"
    )

    # 2. 提取 [CURRENT STATE] 和 [RETRIEVED KNOWLEDGE] 来构建 'input'
    current_state = extract_section(llm_input_text, "CURRENT STATE")
    retrieved_knowledge = extract_section(llm_input_text, "RETRIEVED KNOWLEDGE")

    context_input = (
        f"**Current State Analysis:**\n{current_state if current_state else 'Not available.'}\n\n"
        f"**Relevant Knowledge:**\n{retrieved_knowledge if retrieved_knowledge else 'Not available.'}"
    )

    # 3. 组合 'llm_thought' 和 'action' 来构建 'output'
    # 这种XML风格的格式有助于模型学习思考过程和最终行动之间的结构
    # FIX: 确保 thought 和 action 也是 None-safe 的
    thought = record.get("llm_thought") or ""
    action = record.get("action", {})
    # 将 action 字典转换为紧凑的 JSON 字符串
    action_str = json.dumps(action, separators=(',', ':'))

    output = f"<think>{thought}</think>\n<action>{action_str}</action>"

    # 4. 'system' 字段直接使用原始的详细指令
    # FIX: 确保 system_prompt 也是 None-safe 的
    system_prompt = record.get("instruction") or ""

    # 组装最终的条目
    finetune_entry = {
        "instruction": instruction,
        "input": context_input,
        "output": output,
        "system": system_prompt,
        "history": []  # 目前我们不添加多轮历史，但保留字段以便未来扩展
    }

    return finetune_entry


def convert_memory_to_finetune_data(input_path: Path, output_path: Path):
    """
    读取 memory_store JSON 文件，将其转换为 .jsonl 格式，并写入输出文件。
    """
    print(f"🚀 Starting conversion from '{input_path}' to '{output_path}'...")

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: Input file not found at '{input_path}'")
        return
    except json.JSONDecodeError:
        print(f"❌ Error: Could not decode JSON from '{input_path}'")
        return

    # memory_store 的顶层键是 run_id，我们需要获取其值
    if not isinstance(data, dict) or not data:
        print(f"❌ Error: Expected a non-empty dictionary in '{input_path}'")
        return

    run_id = next(iter(data))
    history = data.get(run_id, {}).get("history", [])

    if not history:
        print("⚠️ Warning: No 'history' records found in the input file.")
        return

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    converted_count = 0
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in history:
            # 确保记录是有效的字典
            if not isinstance(record, dict):
                continue

            finetune_entry = format_llama_factory_entry(record)

            # 将格式化后的字典转换为 JSON 字符串并写入文件，每条记录占一行
            f.write(json.dumps(finetune_entry, ensure_ascii=False) + '\n')
            converted_count += 1

    print(f"✅ Conversion complete! Successfully converted {converted_count} records.")
    print(f"📄 Your fine-tuning dataset is ready at: '{output_path}'")


if __name__ == "__main__":
    # 设置命令行参数解析器
    parser = argparse.ArgumentParser(
        description="Convert building control simulation memory files to LLaMA-Factory ready fine-tuning datasets."
    )
    parser.add_argument(
        "--input_file",
        type=str,
        required=True,
        help="Path to the source memory_store JSON file."
    )
    parser.add_argument(
        "--output_file",
        type=str,
        required=True,
        help="Path to the destination .jsonl file for the fine-tuning data."
    )

    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output_file)

    convert_memory_to_finetune_data(input_path, output_path)