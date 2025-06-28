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

BOPTEST_BASE_URL = "http://127.0.0.1:80"

# 确保目录存在
os.makedirs(OUTPUT_DATA_DIR, exist_ok=True)
os.makedirs(INPUT_DATA_DIR, exist_ok=True)

# --- 【新增】: 控制输入给Agent的历史记录步数 ---
HISTORY_WINDOW_SIZE = 3
# --- 【新增】: 定义用户的长期控制需求 ---
USER_DEMAND = (
    "The controllable parameter is con_oveTSetHea_u in the range ‘min_value’: 278.15, ‘max_value’: 308.15, “unit”: ‘K’."
    "The primary goal is to minimize energy consumption while strictly ensuring "
    "that thermal comfort conditions are maintained within an acceptable range."
)
CONTROL_STEP = 3600
SIMULATION_STEPS = 3
