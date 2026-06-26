"""
文件工具函数
负责文件类型识别、路径处理、输出目录管理等。
"""
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

# Fix import path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import SUPPORTED_EXTENSIONS


def get_file_category(file_path: str) -> Optional[str]:
    """根据扩展名返回文件类别，不支持则返回 None"""
    ext = Path(file_path).suffix.lower()
    return SUPPORTED_EXTENSIONS.get(ext)


def is_supported(file_path: str) -> bool:
    """判断文件是否被支持"""
    return get_file_category(file_path) is not None


def ensure_dir(path: str) -> str:
    """确保目录存在，返回路径"""
    os.makedirs(path, exist_ok=True)
    return path


def build_output_path(src_path: str, output_dir: str) -> str:
    """
    构建输出文件路径，保持原文件名（"一进一出"原则）。
    若同名冲突则追加 _desensitized 后缀；若仍冲突则追加 _1、_2 序号。
    """
    src = Path(src_path)
    out_dir = Path(output_dir)
    ensure_dir(str(out_dir))
    dst = out_dir / src.name
    if not dst.exists():
        return str(dst)
    # 同名冲突时追加 _desensitized 后缀
    dst = out_dir / f"{src.stem}_desensitized{src.suffix}"
    if not dst.exists():
        return str(dst)
    # 仍冲突则追加序号
    idx = 1
    while True:
        candidate = out_dir / f"{src.stem}_desensitized_{idx}{src.suffix}"
        if not candidate.exists():
            return str(candidate)
        idx += 1


def copy_file(src: str, dst: str) -> str:
    """复制文件（用于在副本上做修改以保留源文件）"""
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)
    return dst


def human_size(num_bytes: int) -> str:
    """人类可读的文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"
