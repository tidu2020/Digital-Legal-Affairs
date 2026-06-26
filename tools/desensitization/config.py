"""
全局配置模块
通过环境变量或 .env 文件配置大模型连接信息。
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load .env from project root
_project_root = os.path.join(os.path.dirname(__file__), '..', '..')
load_dotenv(os.path.join(_project_root, '.env'))
load_dotenv()  # Also try current directory


@dataclass
class LLMConfig:
    """大语言模型相关配置"""
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "").rstrip("/chat/completions").rstrip("/"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "qwen"))
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    max_chars_per_chunk: int = int(os.getenv("LLM_MAX_CHARS_PER_CHUNK", "6000"))
    request_timeout: int = int(os.getenv("LLM_TIMEOUT", "120"))
    enable_thinking: bool = os.getenv("LLM_ENABLE_THINKING", "false").lower() == "true"
    stream: bool = os.getenv("LLM_STREAM", "false").lower() == "true"
    force_json_format: bool = os.getenv("LLM_FORCE_JSON_FORMAT", "false").lower() == "true"


@dataclass
class ProcessingConfig:
    """脱敏处理相关配置"""
    # 单批次最大文件数
    max_files_per_batch: int = 20
    # 是否优先替换（True=替换优先，False=允许删除）
    replace_first: bool = True
    # OCR 语言（图片脱敏）
    ocr_lang: str = os.getenv("OCR_LANG", "chi_sim+eng")
    # 输出目录名
    output_dir_name: str = "desensitized_output"
    # 报告目录名
    report_dir_name: str = "reports"


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)


# 全局配置单例
CONFIG = Config()


# 支持的文件格式映射：扩展名 -> 处理器类别
# 处理器类别用于 factory 分发，legacy 类别会触发 LibreOffice 转换
SUPPORTED_EXTENSIONS = {
    # Word
    ".docx": "word",
    ".doc": "word_legacy",
    # Excel
    ".xlsx": "excel",
    ".xls": "excel_legacy",
    # PowerPoint
    ".pptx": "ppt",
    ".ppt": "ppt_legacy",
    # PDF
    ".pdf": "pdf",
    # Images
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".bmp": "image",
    ".tiff": "image",
    ".tif": "image",
}

# 旧版格式 -> 新版格式的转换映射（用于 LibreOffice 转换）
LEGACY_TO_NEW = {
    ".doc": ".docx",
    ".xls": ".xlsx",
    ".ppt": ".pptx",
}
