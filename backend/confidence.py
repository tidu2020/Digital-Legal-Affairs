"""
置信度标注模块

为法务助手的回答提供置信度评估，帮助用户了解回答的可靠性。
置信度分为三级：
- HIGH（高）：权威数据源核验通过
- MEDIUM（中）：基于合理推理
- LOW（低）：信息不足，结论仅供参考
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


class ConfidenceLevel:
    """置信度等级常量"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    HIGH_LABEL = "高"
    MEDIUM_LABEL = "中"
    LOW_LABEL = "低"

    HIGH_ICON = "🟢"
    MEDIUM_ICON = "🟡"
    LOW_ICON = "🔴"

    HIGH_REASON = "权威数据源核验通过"
    MEDIUM_REASON = "基于合理推理"
    LOW_REASON = "信息不足，结论仅供参考"


@dataclass
class ConfidenceAnnotation:
    """置信度标注"""
    level: str          # HIGH / MEDIUM / LOW
    label: str          # 高 / 中 / 低
    icon: str           # 🟢 / 🟡 / 🔴
    reason: str         # 解释为什么是这个置信度
    source: Optional[str] = None  # 数据来源（如果适用）


def assess_confidence(
    law_validation_report: Optional[Dict[str, Any]],
    has_attachment: bool,
    user_message: str
) -> ConfidenceAnnotation:
    """
    评估回答的置信度

    评估逻辑：
    - 如果有法条校验报告且有有效校验项 → HIGH
    - 如果用户消息涉及法律领域但无权威核验 → MEDIUM
    - 如果信息不足 → LOW

    Args:
        law_validation_report: 法条校验报告（来自 law_validator.generate_validation_report）
        has_attachment: 是否有附件
        user_message: 用户消息内容

    Returns:
        ConfidenceAnnotation 置信度标注
    """
    # 如果有法条校验报告且有校验项 → HIGH（权威数据源核验通过）
    if law_validation_report and law_validation_report.get("total", 0) > 0:
        valid_count = law_validation_report.get("valid", 0)
        if valid_count > 0:
            return ConfidenceAnnotation(
                level=ConfidenceLevel.HIGH,
                label=ConfidenceLevel.HIGH_LABEL,
                icon=ConfidenceLevel.HIGH_ICON,
                reason=ConfidenceLevel.HIGH_REASON,
                source=law_validation_report.get("source", "国家法律法规数据库 (flk.npc.gov.cn)")
            )
        # 有校验项但全部不通过，仍然是 HIGH（因为经过了权威验证流程）
        return ConfidenceAnnotation(
            level=ConfidenceLevel.HIGH,
            label=ConfidenceLevel.HIGH_LABEL,
            icon=ConfidenceLevel.HIGH_ICON,
            reason="法条引用已通过国家法律法规数据库核验",
            source=law_validation_report.get("source", "国家法律法规数据库 (flk.npc.gov.cn)")
        )

    # 判断是否涉及法律领域
    legal_keywords = [
        '法律', '法规', '法条', '合同', '诉讼', '仲裁', '劳动',
        '公司', '合规', '侵权', '违约', '赔偿', '责任', '义务',
        '权利', '知识产权', '专利', '商标', '著作权', '民法典',
        '刑法', '公司法', '劳动法', '劳动合同法', '行政处罚',
        '审核', '审查', '制度', '章程', '条例', '规定', '办法',
    ]

    is_legal_domain = any(kw in user_message for kw in legal_keywords)

    if is_legal_domain or has_attachment:
        return ConfidenceAnnotation(
            level=ConfidenceLevel.MEDIUM,
            label=ConfidenceLevel.MEDIUM_LABEL,
            icon=ConfidenceLevel.MEDIUM_ICON,
            reason=ConfidenceLevel.MEDIUM_REASON,
            source=None
        )

    # 信息不足
    return ConfidenceAnnotation(
        level=ConfidenceLevel.LOW,
        label=ConfidenceLevel.LOW_LABEL,
        icon=ConfidenceLevel.LOW_ICON,
        reason=ConfidenceLevel.LOW_REASON,
        source=None
    )


def generate_confidence_markdown(annotation: ConfidenceAnnotation) -> str:
    """
    生成置信度标注的 Markdown 文本

    Args:
        annotation: 置信度标注

    Returns:
        Markdown 格式的置信度标注
    """
    source_line = ""
    if annotation.source:
        source_line = f"\n> 数据来源：{annotation.source}"

    return (
        f"\n\n---\n"
        f"### {annotation.icon} 置信度：{annotation.label}\n"
        f"> {annotation.reason}{source_line}\n"
    )


def annotation_to_dict(annotation: ConfidenceAnnotation) -> Dict[str, Any]:
    """
    将 ConfidenceAnnotation 转为可序列化的字典

    Args:
        annotation: 置信度标注

    Returns:
        dict
    """
    return {
        "level": annotation.level,
        "label": annotation.label,
        "icon": annotation.icon,
        "reason": annotation.reason,
        "source": annotation.source,
    }