import os
from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件
load_dotenv()

# --- 【修改】: 从环境变量中安全地获取 OpenAI API 密钥 ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 如果没有在 .env 文件中找到密钥，则抛出错误
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env file. Please add your key to the .env file.")

# --- 路径配置 (无变化) ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "input")
OUTPUT_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "output")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "configs") # 【新增】: Config目录路径

BOPTEST_BASE_URL = "http://127.0.0.1:80"

TEST_CASE_NAME = "bestest_hydronic_heat_pump"

# 确保目录存在
os.makedirs(OUTPUT_DATA_DIR, exist_ok=True)
os.makedirs(INPUT_DATA_DIR, exist_ok=True)

# --- 模拟参数 ---
START_TIME = 16*24*3600
WARMUP_PERIOD = 7*24*3600
HISTORY_WINDOW_SIZE = 3
CONTROL_STEP = 3600
SIMULATION_STEPS = 14*24

# --- 【修改】: 目标选择与用户自定义描述 ---

# 1. 选择本次模拟要运行的目标。
#    这个名字必须与 'configs/objectives_config.yaml' 中的一个键完全匹配。
SELECTED_OBJECTIVE = "balance_energy_comfort"

# 2. 用户自定义的、关于可控参数的描述。
#    这部分会与所选目标的描述动态拼接。
CONTROLLABLE_PARAM_DESC = (
    "The controllable parameter is oveHeaPumY_u in the range ‘min_value’: 0.0, "
    "‘max_value’: 1.0, Heat pump modulating signal for compressor speed between 0 (not working) and 1 (working at maximum capacity)"
)

# --- 【新增】: GraphRAG 工具配置 ---
# Desc: Master switch to enable or disable the GraphRAG tool for the decision agent.
# Set to False to run the agent without the knowledge retrieval tool.
USE_GRAPHRAG_TOOL = False

# Desc: Path to the GraphRAG settings file.
GRAPHRAG_SETTINGS_PATH = r"D:/graphrag/ragtest/settings.yaml"
