"""
文件处理器基类
定义所有格式处理器的统一接口：
- extract_text: 提取全文文本供 LLM 分析
- apply_replacements: 将替换方案回填到文件副本，保留源格式可编辑性
- process: 编排完整脱敏流程
"""
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from core.llm_client import Replacement
from utils.file_utils import copy_file

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """单文件处理结果"""
    source_path: str                       # 源文件路径
    output_path: str                       # 脱敏后输出路径
    replacements: List[Replacement] = field(default_factory=list)  # 实际执行的替换
    success: bool = True                   # 是否成功
    error: str = ""                        # 失败原因
    file_type: str = ""                    # 文件类别

    def to_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "output_path": self.output_path,
            "file_type": self.file_type,
            "success": self.success,
            "error": self.error,
            "replacements": [r.to_dict() for r in self.replacements],
            "replacement_count": len(self.replacements),
        }


class BaseProcessor(ABC):
    """文件处理器抽象基类"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def process(self, src_path: str, output_path: str) -> ProcessResult:
        """
        完整脱敏流程：
        1. 复制源文件到输出路径（在副本上修改，保护源文件）
        2. 提取文本
        3. 调用 LLM 生成替换方案
        4. 回填替换到文件副本
        """
        file_type = os.path.splitext(src_path)[1].lower().lstrip(".")
        try:
            # 1. 复制源文件作为工作副本
            copy_file(src_path, output_path)
            logger.info("已创建工作副本: %s", output_path)

            # 2. 提取文本
            text = self.extract_text(output_path)
            if not text or not text.strip():
                logger.warning("文件 %s 未提取到文本内容", src_path)
                return ProcessResult(
                    source_path=src_path,
                    output_path=output_path,
                    file_type=file_type,
                    success=True,
                    replacements=[],
                )

            # 3. LLM 分析生成替换方案
            logger.info("正在调用 LLM 分析敏感信息: %s", src_path)
            replacements = self.llm.desensitize_text(text)
            logger.info("LLM 识别到 %d 处敏感信息", len(replacements))

            # 4. 回填替换到文件
            applied = self.apply_replacements(output_path, replacements)
            logger.info("成功回填 %d 处替换", len(applied))

            return ProcessResult(
                source_path=src_path,
                output_path=output_path,
                replacements=applied,
                success=True,
                file_type=file_type,
            )
        except Exception as e:
            logger.exception("处理文件 %s 失败: %s", src_path, e)
            return ProcessResult(
                source_path=src_path,
                output_path=output_path,
                success=False,
                error=str(e),
                file_type=file_type,
            )

    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """从文件中提取全部文本内容"""
        raise NotImplementedError

    @abstractmethod
    def apply_replacements(
        self, file_path: str, replacements: List[Replacement]
    ) -> List[Replacement]:
        """
        将替换方案回填到文件，返回实际成功应用的替换列表。
        必须保留源文件的可编辑属性。
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 通用辅助方法（供 Word/PPT 等基于段落+run 的处理器复用）
    # ------------------------------------------------------------------

    @staticmethod
    def _track_applied(
        applied_set: Set[str],
        applied: List[Replacement],
        replacement: Replacement,
    ) -> None:
        """记录一条已应用的替换（按 original 去重）"""
        if replacement.original not in applied_set:
            applied_set.add(replacement.original)
            applied.append(replacement)

    @staticmethod
    def _apply_text_replacements(
        text: str, replacements: List[Replacement]
    ) -> Tuple[str, List[Replacement]]:
        """
        通用文本替换工具：对一段文本应用所有替换。
        返回 (替换后文本, 实际应用的替换列表)。
        使用占位符两阶段替换，避免链式替换导致的问题。
        """
        if not text or not replacements:
            return text, []

        applied: List[Replacement] = []
        placeholders: List[str] = []
        result = text

        for r in replacements:
            if not r.original or r.original not in result:
                continue
            # 生成唯一占位符
            placeholder = f"\x00DESENS_{len(placeholders)}\x00"
            # 对所有出现位置进行替换
            count = result.count(r.original)
            result = result.replace(r.original, placeholder)
            placeholders.append(r.replacement if r.action == "replace" else "")
            applied.append(r)
            if count > 1:
                # 多次出现只记录一次替换记录，但说明次数
                logger.debug("「%s」在文本中出现 %d 次，已全部替换", r.original, count)

        # 第二阶段：占位符还原为实际替换值
        for i, value in enumerate(placeholders):
            result = result.replace(f"\x00DESENS_{i}\x00", value)

        return result, applied

    @classmethod
    def _replace_in_paragraph(
        cls,
        paragraph,
        replacements: List[Replacement],
        applied_set: Set[str],
        applied: List[Replacement],
    ) -> None:
        """
        在段落内做替换（适用于 python-docx / python-pptx 的 paragraph 对象）。
        - 优先在单个 run 内替换以保留格式
        - 若敏感文本跨越多个 run，则合并 run 文本后整体替换（保留首个 run 格式）
        """
        if not paragraph.runs:
            # 无 run 的段落直接处理 text（少见）
            full_text = paragraph.text
            if not full_text:
                return
            new_text, used = cls._apply_text_replacements(full_text, replacements)
            if new_text != full_text:
                # 段落无 run，直接新增一个 run 写入新文本
                paragraph.add_run(new_text)
                for r in used:
                    cls._track_applied(applied_set, applied, r)
            return

        # 检查是否有敏感文本跨越 run 边界
        full_text = "".join(run.text for run in paragraph.runs)
        cross_run_hits = [
            r for r in replacements
            if r.original and r.original in full_text
            and not any(r.original in run.text for run in paragraph.runs)
        ]

        if cross_run_hits:
            # 存在跨 run 的敏感文本：合并到首个 run，保留其格式
            new_text, used = cls._apply_text_replacements(full_text, replacements)
            if new_text != full_text and paragraph.runs:
                # 保留首个 run 的格式属性，清空其余 run
                first_run = paragraph.runs[0]
                first_run.text = new_text
                for run in paragraph.runs[1:]:
                    run.text = ""
                for r in used:
                    cls._track_applied(applied_set, applied, r)
            return

        # 单 run 内替换：逐 run 处理，最大程度保留各自格式
        for run in paragraph.runs:
            if not run.text:
                continue
            new_text, used = cls._apply_text_replacements(run.text, replacements)
            if new_text != run.text:
                run.text = new_text
                for r in used:
                    cls._track_applied(applied_set, applied, r)
