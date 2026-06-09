"""
国企法务助手 - 合同分块处理

支持将长合同文本按条款标记（第X条）智能分块，
用于解决大模型上下文窗口限制问题。
"""
import re
from typing import List


# 匹配"第X条"样式的条款标记（含中文数字与阿拉伯数字）
CLAUSE_PATTERN = re.compile(r'(第[一二三四五六七八九十百千\d]+条[^.。\n]*)')


def estimate_tokens(text: str) -> int:
    """
    粗略估算文本的 token 数量。
    中文占主导时，按字符数 / 2 估算。
    """
    return len(text) // 2


def split_contract(text: str, max_chars: int = 12000) -> List[str]:
    """
    将合同文本按条款拆分，合并为不超过 max_chars 的分块。

    分块策略：
    1. 优先按"第X条"条款标记拆分
    2. 回退到按段落（\n\n）拆分
    3. 最终回退：返回原文整体
    """
    if not text or not text.strip():
        return []

    # ---- 策略一：按条款标记拆分 ----
    clauses = CLAUSE_PATTERN.split(text)

    # 如果存在条款标记，clauses 的长度会 > 1
    if len(clauses) > 1:
        header = clauses[0].strip()  # 第一个条款标记之前的内容作为"头部"
        clause_items = []
        # 成对收集 (标记, 内容)
        i = 1
        while i < len(clauses):
            marker = clauses[i]
            content = clauses[i + 1] if i + 1 < len(clauses) else ""
            clause_items.append(marker + content)
            i += 2

        return _group_into_chunks(clause_items, max_chars, header)

    # ---- 策略二：按段落拆分 ----
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    if len(paragraphs) > 1:
        return _group_into_chunks(paragraphs, max_chars, header="")

    # ---- 策略三：直接返回原文 ----
    return [text]


def _group_into_chunks(items: List[str], max_chars: int, header: str = "") -> List[str]:
    """
    将 items 按顺序合入分块，每个分块不超过 max_chars。

    规则：
    - 第一个分块包含 header + 尽可能多的 items
    - 后续分块也前置 header（保持上下文连续性）
    - 当当前分块长度超过 max_chars * 0.8 时，后续 item 放入新分块
    """
    threshold = int(max_chars * 0.8)
    chunks: List[str] = []
    current: List[str] = []

    # 第一个分块从 header 开始
    if header:
        current = [header]

    for item in items:
        proposed = current + [item]
        proposed_text = "\n".join(proposed)

        if len(proposed_text) <= max_chars and len(proposed_text) <= threshold:
            # 还在舒适区，继续合并
            current = proposed
        elif len(proposed_text) <= max_chars:
            # 已超过阈值但未超过上限，可以合入
            current = proposed
        else:
            # 放不下，结算当前分块
            if current:
                chunks.append("\n".join(current))
            # 后续分块都以 header 开头
            if header:
                current = [header, item]
            else:
                current = [item]

    # 最后一个分块
    if current:
        chunks.append("\n".join(current))

    return chunks


def should_chunk(
    text: str,
    prompt: str,
    context_limit: int = 8000,
    safety_ratio: float = 0.75,
) -> bool:
    """
    判断是否需要分块处理。

    计算逻辑：
    - 估算 text + prompt 的总 token 数（中文按字符数 / 2）
    - 若估算值 > context_limit * safety_ratio * 0.75，则需要分块
    """
    total_chars = len(text) + len(prompt)
    estimated_tokens = total_chars // 2
    threshold = int(context_limit * safety_ratio * 0.75)
    return estimated_tokens > threshold


class ContractChunker:
    """合同分块器，提供面向对象的接口封装。"""

    def __init__(self, max_chunk_chars: int = 12000):
        self.max_chunk_chars = max_chunk_chars

    def split(self, text: str) -> List[str]:
        """对合同文本进行分块。"""
        return split_contract(text, max_chars=self.max_chunk_chars)

    def should_chunk(self, text: str, system_prompt: str) -> bool:
        """判断是否需要分块处理。"""
        return should_chunk(text, system_prompt)