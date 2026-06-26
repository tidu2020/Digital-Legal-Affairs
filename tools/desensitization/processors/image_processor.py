"""
图片处理器
基于 pytesseract (OCR) + Pillow，对图片中的敏感文字进行识别与遮盖替换：
1. OCR 提取图片中的文字及其位置（bounding box）
2. 将文字送 LLM 分析生成替换方案
3. 对每处敏感文字，用白色矩形遮盖原文，并在原位置绘制替换文字

说明：图片本身非"可编辑文本"格式，本处理器采用"遮盖+重绘"方式，
在保留图片视觉结构的前提下完成脱敏，是图片类文件的最佳可行方案。
"""
import logging
import os
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

from core.llm_client import Replacement
from processors.base import BaseProcessor

logger = logging.getLogger(__name__)

# 遮盖区域向外扩展的像素数
_COVER_PAD = 2


class ImageProcessor(BaseProcessor):
    """图片处理器（jpg/png/bmp/tiff）"""

    def extract_text(self, file_path: str) -> str:
        ocr_data = self._run_ocr(file_path)
        if not ocr_data:
            return ""
        # 将词级数据合并为行级文本，便于 LLM 理解上下文
        lines = self._group_into_lines(ocr_data)
        return "\n".join(line["text"] for line in lines if line["text"])

    def apply_replacements(
        self, file_path: str, replacements: List[Replacement]
    ) -> List[Replacement]:
        # 复用 extract_text 阶段的 OCR 结果，避免重复调用
        ocr_data = self._run_ocr(file_path)
        if not ocr_data:
            logger.error("OCR 未返回数据，无法进行图片脱敏")
            return []

        img = Image.open(file_path).convert("RGB")
        lines = self._group_into_lines(ocr_data)

        applied_set = set()
        applied: List[Replacement] = []

        draw = ImageDraw.Draw(img)
        # 字号根据行高自适应
        font = self._load_font(img, size=12)

        for line in lines:
            line_text = line["text"]
            if not line_text:
                continue
            for r in replacements:
                if not r.original or r.original not in line_text:
                    continue

                # 按词级 bbox 精确遮盖匹配到的敏感词，而非整行
                cover_boxes = self._find_word_boxes(ocr_data, line, r.original)
                if not cover_boxes:
                    # 回退：遮盖整行
                    cover_boxes = [line["bbox"]]

                replacement_text = (
                    r.replacement if r.action == "replace" else ""
                )
                for box in cover_boxes:
                    self._cover_and_redraw(draw, img, box, replacement_text, font)

                self._track_applied(applied_set, applied, r)

        # 保存为原格式
        save_format = os.path.splitext(file_path)[1].lower().lstrip(".")
        fmt_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG",
                   "bmp": "BMP", "tiff": "TIFF", "tif": "TIFF"}
        img.save(file_path, format=fmt_map.get(save_format, "PNG"))
        return applied

    # ------------------------------------------------------------------
    # OCR 与缓存
    # ------------------------------------------------------------------

    def _run_ocr(self, file_path: str) -> Optional[Dict]:
        """
        对图片执行 OCR，返回 image_to_data 的字典结果。
        OCR 是耗时操作，调用方应缓存结果避免重复调用。
        """
        try:
            import pytesseract
        except ImportError:
            logger.error("未安装 pytesseract，无法进行 OCR")
            return None

        from config import CONFIG
        lang = CONFIG.processing.ocr_lang

        img = Image.open(file_path)
        return pytesseract.image_to_data(
            img, lang=lang, output_type=pytesseract.Output.DICT
        )

    @staticmethod
    def _group_into_lines(data: Dict) -> List[dict]:
        """将 OCR 词级数据按行分组，返回每行的文本与边界框"""
        n = len(data["text"])
        line_groups: dict = {}
        for i in range(n):
            text = data["text"][i].strip()
            if not text:
                continue
            block = data["block_num"][i]
            line = data["line_num"][i]
            par = data["par_num"][i]
            key = (block, par, line)
            if key not in line_groups:
                line_groups[key] = {
                    "texts": [],
                    "word_indices": [],
                    "left": data["left"][i],
                    "top": data["top"][i],
                    "right": data["left"][i] + data["width"][i],
                    "bottom": data["top"][i] + data["height"][i],
                }
            else:
                g = line_groups[key]
                g["left"] = min(g["left"], data["left"][i])
                g["top"] = min(g["top"], data["top"][i])
                g["right"] = max(g["right"], data["left"][i] + data["width"][i])
                g["bottom"] = max(g["bottom"], data["top"][i] + data["height"][i])
            line_groups[key]["texts"].append(text)
            line_groups[key]["word_indices"].append(i)

        lines = []
        for key in sorted(line_groups.keys()):
            g = line_groups[key]
            lines.append({
                "text": " ".join(g["texts"]),
                "bbox": (g["left"], g["top"], g["right"], g["bottom"]),
                "word_indices": g["word_indices"],
            })
        return lines

    @staticmethod
    def _find_word_boxes(data: Dict, line: dict, original: str) -> List[tuple]:
        """
        在指定行内查找敏感词的精确词级 bbox。
        若敏感词跨多个词，则合并这些词的 bbox。
        """
        indices = line["word_indices"]
        words = [data["text"][i] for i in indices]

        # 尝试在词序列中匹配敏感词（去除空格后比较，提升容错）
        target = original.replace(" ", "").lower()
        boxes: List[tuple] = []

        # 滑动窗口匹配连续词
        for start in range(len(words)):
            for end in range(start + 1, len(words) + 1):
                combined = "".join(words[start:end]).lower()
                if target in combined:
                    # 合并这些词的 bbox
                    left = min(data["left"][indices[i]] for i in range(start, end))
                    top = min(data["top"][indices[i]] for i in range(start, end))
                    right = max(
                        data["left"][indices[i]] + data["width"][indices[i]]
                        for i in range(start, end)
                    )
                    bottom = max(
                        data["top"][indices[i]] + data["height"][indices[i]]
                        for i in range(start, end)
                    )
                    boxes.append((left, top, right, bottom))
                    break
            else:
                continue
            break
        return boxes

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------

    @staticmethod
    def _cover_and_redraw(draw, img, bbox, replacement_text, font):
        """遮盖指定区域并在原位置绘制替换文本"""
        pad = _COVER_PAD
        cover_box = (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(img.width, bbox[2] + pad),
            min(img.height, bbox[3] + pad),
        )
        draw.rectangle(cover_box, fill="white")

        if replacement_text:
            try:
                draw.text(
                    (cover_box[0], cover_box[1]),
                    replacement_text,
                    fill="black",
                    font=font,
                )
            except Exception as e:
                logger.warning("绘制替换文本失败: %s", e)

    @staticmethod
    def _load_font(img: Image.Image, size: int = 12):
        """加载字体，优先中文字体，失败则回退默认"""
        # 中文字体优先，避免中文显示为方块
        font_paths = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    continue
        # 回退默认字体
        try:
            return ImageFont.load_default()
        except Exception:
            return None
