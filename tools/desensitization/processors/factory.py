"""
处理器工厂
根据文件扩展名返回对应的处理器实例。
对于旧版格式（.doc/.xls/.ppt），通过 LibreOffice 转换为新版格式后再处理。
"""
import logging
import os
import subprocess
import sys
from typing import Optional

# Fix import path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import LEGACY_TO_NEW, SUPPORTED_EXTENSIONS
from core.llm_client import LLMClient
from processors.base import BaseProcessor
from processors.word_processor import WordProcessor
from processors.excel_processor import ExcelProcessor
from processors.ppt_processor import PPTProcessor
from processors.pdf_processor import PDFProcessor
from processors.image_processor import ImageProcessor

logger = logging.getLogger(__name__)

# 处理器类别 -> 处理器类的映射（统一从 config 的 SUPPORTED_EXTENSIONS 分发）
_PROCESSOR_CLASSES = {
    "word": WordProcessor,
    "excel": ExcelProcessor,
    "ppt": PPTProcessor,
    "pdf": PDFProcessor,
    "image": ImageProcessor,
}


def get_processor(file_path: str, llm_client: LLMClient) -> Optional[BaseProcessor]:
    """根据文件类型返回处理器实例"""
    ext = os.path.splitext(file_path)[1].lower()
    category = SUPPORTED_EXTENSIONS.get(ext)

    if category is None:
        logger.warning("不支持的文件格式: %s", ext)
        return None

    # 旧版格式：转换为新版后递归调用
    if category.endswith("_legacy"):
        converted = _try_convert_legacy(file_path)
        if converted:
            return get_processor(converted, llm_client)
        logger.warning(
            "旧版格式 %s 需要安装 LibreOffice (soffice) 以自动转换。"
            "请将文件另存为 .docx/.xlsx/.pptx 后重试。", ext
        )
        return None

    processor_cls = _PROCESSOR_CLASSES.get(category)
    if processor_cls is None:
        logger.warning("未注册处理器类别: %s", category)
        return None
    return processor_cls(llm_client)


def _try_convert_legacy(file_path: str) -> Optional[str]:
    """
    尝试用 LibreOffice 将旧版 Office 格式转换为新版。
    需要系统安装 soffice 命令。
    """
    soffice = os.getenv("SOFFICE_PATH", "soffice")
    ext = os.path.splitext(file_path)[1].lower()
    new_ext = LEGACY_TO_NEW.get(ext)
    if not new_ext:
        return None
    target_format = new_ext.lstrip(".")
    try:
        out_dir = os.path.dirname(file_path) or "."
        result = subprocess.run(
            [soffice, "--headless", "--convert-to",
             target_format, "--outdir", out_dir, file_path],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            return None
        # 查找生成的转换文件
        base = os.path.splitext(os.path.basename(file_path))[0]
        converted = os.path.join(out_dir, base + new_ext)
        if os.path.exists(converted):
            logger.info("已将 %s 转换为 %s", file_path, converted)
            return converted
    except FileNotFoundError:
        logger.debug("未找到 soffice 命令")
    except Exception as e:
        logger.debug("LibreOffice 转换失败: %s", e)
    return None
