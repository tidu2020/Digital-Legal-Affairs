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