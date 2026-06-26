"""
PDF 处理器
基于 PyMuPDF (fitz)，通过 redaction（修订）机制实现文本替换：
1. 提取全文文本供 LLM 分析
2. 对每处敏感文本，定位其在页面上的位置，添加 redact 标注
3. 应用 redaction 时填入替换文本，保留 PDF 的可编辑文本属性

注：PDF 经 redaction 后文本层仍为可选可编辑文本（非展平图片），
满足"保留源格式可编辑状态"的要求。
"""
import logging
import os
import tempfile
from typing import List

import fitz  # PyMuPDF

from core.llm_client import Replacement
from processors.base import BaseProcessor

logger = logging.getLogger(__name__)


class PDFProcessor(BaseProcessor):
    """PDF 处理器"""

    def extract_text(self, file_path: str) -> str:
        doc = fitz.open(file_path)
        parts: List[str] = []
        for page in doc:
            parts.append(page.get_text("text"))
        doc.close()
        return "\n".join(parts)

    def apply_replacements(
        self, file_path: str, replacements: List[Replacement]
    ) -> List[Replacement]:
        doc = fitz.open(file_path)
        applied_set = set()
        applied: List[Replacement] = []

        for page in doc:
            # 收集本页所有需替换的 (rect, replacement_text) 以便 redaction 后重绘
            redraw_list = []
            for r in replacements:
                if not r.original:
                    continue
                # 在页面中搜索敏感文本的所有出现位置
                rects = page.search_for(r.original, quads=False)
                if not rects:
                    # 尝试去除空格后搜索（处理换行/空格差异）
                    # 注意：去空格搜索可能匹配到原文中本不含空格的位置，
                    # 因此只对原文中确实包含空格的敏感词启用此回退
                    no_space = r.original.replace(" ", "")
                    if no_space != r.original and no_space:
                        rects = page.search_for(no_space, quads=False)
                if not rects:
                    continue

                replacement_text = (
                    r.replacement if r.action == "replace" else ""
                )
                for rect in rects:
                    # 添加 redact 标注：仅用于删除原文（白色填充）
                    # 替换文本不通过 redaction 写入（默认字体不支持 CJK），
                    # 改为 redaction 后用内置 CJK 字体手动插入
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                    redraw_list.append((rect, replacement_text))

                self._track_applied(applied_set, applied, r)

            # 应用本页所有 redaction（删除原文底层内容）
            page.apply_redactions()

            # 在原位置重绘替换文本（使用内置 CJK 字体 china-s）
            for rect, replacement_text in redraw_list:
                if not replacement_text:
                    continue
                self._insert_text_at_rect(page, rect, replacement_text)

        # PyMuPDF 不允许以非增量方式保存到原路径，先写临时文件再替换
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".pdf", dir=os.path.dirname(file_path)
        )
        os.close(tmp_fd)
        try:
            doc.save(tmp_path, deflate=True, garbage=4)
            doc.close()
            os.replace(tmp_path, file_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
        return applied

    @staticmethod
    def _insert_text_at_rect(page, rect, text: str):
        """在矩形区域插入替换文本，使用内置 CJK 字体，字号自适应原区域高度"""
        # PDF 文本插入点为基线左下角
        point = fitz.Point(rect.x0, rect.y1 - 1)
        # 字号根据原文本高度估算
        fontsize = max(6, min(rect.height * 0.85, 14))
        try:
            page.insert_text(
                point, text, fontname="china-s",
                fontsize=fontsize, color=(0, 0, 0),
            )
        except Exception as e:
            logger.warning("PDF 插入替换文本失败 (%s): %s", text, e)
