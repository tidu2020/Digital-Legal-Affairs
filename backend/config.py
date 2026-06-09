"""
国企法务助手 - 配置文件
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
UPLOAD_DIR = DATA_DIR / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)

# 兜底：手动加载 .env 文件（确保 python-dotenv 未安装时也能读取配置）
def _load_env_file(env_path: Path):
    """手动解析 .env 文件"""
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key not in os.environ or not os.environ.get(key):
                        os.environ[key] = val

# 先后尝试项目根目录和 backend 目录的 .env
_load_env_file(BASE_DIR / ".env")
_load_env_file(Path(__file__).parent / ".env")

LLM_CONFIG = {
    "base_url": os.getenv(
        "LLM_BASE_URL",
        "https://chatai.bii.com.cn/open-api/llm/k8s/qwen/v1/chat/completions",
    ),
    "api_key": os.getenv("LLM_API_KEY", ""),
    "model": os.getenv("LLM_MODEL", "qwen"),
    "thinking_enabled": os.getenv("LLM_THINKING", "false").lower() == "true",
}

EMBEDDING_CONFIG = {
    "model_name": "shibing624/text2vec-base-chinese",
    "dimension": 768,
    "max_length": 512,
}

RAG_CONFIG = {
    "top_k": 5,
    "similarity_threshold": 0.3,
    "max_context_length": 4000,
}

SERVER_CONFIG = {
    "host": "0.0.0.0",
    "port": 1824,
    "debug": True,
}