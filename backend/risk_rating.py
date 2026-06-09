"""
国企法务助手 - 结构化风险评级系统

提供统一的风险评级标准、数据模型与计算函数，
供合同审核、合规审查等技能模块调用。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from collections import Counter


# ============================================================
# 1. 风险发生概率
# ============================================================
class RiskProbability:
    """风险发生概率等级"""

    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"

    ALL = [HIGH, MEDIUM, LOW]

    LABELS = {
        HIGH: "高 - 极有可能发生",
        MEDIUM: "中 - 有一定可能性",
        LOW: "低 - 发生可能性较低",
    }


# ============================================================
# 2. 风险影响程度
# ============================================================
class RiskImpact:
    """风险影响程度等级"""

    SEVERE = "严重"
    MODERATE = "一般"
    MINOR = "轻微"

    ALL = [SEVERE, MODERATE, MINOR]

    LABELS = {
        SEVERE: "严重 - 重大经济损失或法律责任",
        MODERATE: "一般 - 一定程度影响",
        MINOR: "轻微 - 影响较小",
    }


# ============================================================
# 3. 风险等级
# ============================================================
class RiskLevel:
    """综合风险等级"""

    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"

    ICON = {
        HIGH: "🔴",
        MEDIUM: "🟡",
        LOW: "🟢",
    }

    LABEL = {
        HIGH: "高风险",
        MEDIUM: "中风险",
        LOW: "低风险",
    }


# ---- 风险评级矩阵 (probability × impact) ----
# key: (probability, impact) → (risk_level, risk_icon)
_RISK_MATRIX: Dict[Tuple[str, str], Tuple[str, str]] = {
    # 高概率
    (RiskProbability.HIGH, RiskImpact.SEVERE):   (RiskLevel.HIGH,   RiskLevel.ICON[RiskLevel.HIGH]),
    (RiskProbability.HIGH, RiskImpact.MODERATE):  (RiskLevel.HIGH,   RiskLevel.ICON[RiskLevel.HIGH]),
    (RiskProbability.HIGH, RiskImpact.MINOR):     (RiskLevel.MEDIUM, RiskLevel.ICON[RiskLevel.MEDIUM]),
    # 中概率
    (RiskProbability.MEDIUM, RiskImpact.SEVERE):  (RiskLevel.HIGH,   RiskLevel.ICON[RiskLevel.HIGH]),
    (RiskProbability.MEDIUM, RiskImpact.MODERATE): (RiskLevel.MEDIUM, RiskLevel.ICON[RiskLevel.MEDIUM]),
    (RiskProbability.MEDIUM, RiskImpact.MINOR):    (RiskLevel.LOW,    RiskLevel.ICON[RiskLevel.LOW]),
    # 低概率
    (RiskProbability.LOW, RiskImpact.SEVERE):     (RiskLevel.MEDIUM, RiskLevel.ICON[RiskLevel.MEDIUM]),
    (RiskProbability.LOW, RiskImpact.MODERATE):   (RiskLevel.LOW,    RiskLevel.ICON[RiskLevel.LOW]),
    (RiskProbability.LOW, RiskImpact.MINOR):      (RiskLevel.LOW,    RiskLevel.ICON[RiskLevel.LOW]),
}

# 矩阵的可视化表格，用于展示与系统提示词
RISK_MATRIX_TABLE = (
    "风险评级矩阵（发生概率 × 影响程度）：\n"
    "| 概率\\影响 | 严重 | 一般 | 轻微 |\n"
    "|-----------|------|------|------|\n"
    "| 高 | 🔴高 | 🔴高 | 🟡中 |\n"
    "| 中 | 🔴高 | 🟡中 | 🟢低 |\n"
    "| 低 | 🟡中 | 🟢低 | 🟢低 |"
)


# ============================================================
# 4. 数据模型
# ============================================================
@dataclass
class RiskItem:
    """合同审核风险项"""

    risk_level: str          # 高/中/低
    risk_icon: str           # 🔴/🟡/🟢
    risk_type: str           # 争议风险/履约风险/合规风险/效力风险
    related_clause: str      # 关联条款
    risk_description: str    # 风险描述
    legal_basis: str         # 法律依据
    suggestion: str          # 应对建议
    probability: str         # 高/中/低
    impact: str              # 严重/一般/轻微


@dataclass
class ComplianceRiskItem:
    """合规审查风险项"""

    issue_id: str            # G/P/D 前缀 + 数字，如 G01, P03
    issue_type: str          # 问题类型
    legal_basis: str         # 法律依据
    risk_level: str          # 高/中/低
    risk_icon: str           # 🔴/🟡/🟢
    suggestion: str          # 整改建议
    priority: str            # 整改优先级: 立即/近期/计划


# ============================================================
# 5. 核心函数
# ============================================================
def calculate_risk_level(probability: str, impact: str) -> Tuple[str, str]:
    """根据发生概率和影响程度计算风险等级与图标。

    Args:
        probability: 发生概率，取 "高"/"中"/"低"
        impact:      影响程度，取 "严重"/"一般"/"轻微"

    Returns:
        (risk_level, risk_icon) 元组，例如 ("高", "🔴")
    """
    key = (probability, impact)
    if key in _RISK_MATRIX:
        return _RISK_MATRIX[key]
    # 对未知输入做模糊回退：严格匹配失败时按严重程度保守判定
    raise ValueError(
        f"无效的风险输入: probability={probability!r}, impact={impact!r}。"
        f"probability 取值: {RiskProbability.ALL}, impact 取值: {RiskImpact.ALL}"
    )


def generate_risk_summary(risks: List[RiskItem]) -> str:
    """生成 Markdown 格式的风险摘要，按等级统计。

    Args:
        risks: RiskItem 列表

    Returns:
        Markdown 格式的风险摘要字符串
    """
    if not risks:
        return (
            "## 风险评估摘要\n\n"
            "✅ **未发现明显法律风险**，合同条款整体合规。\n"
        )

    counter = Counter(r.risk_level for r in risks)
    high_count = counter.get(RiskLevel.HIGH, 0)
    medium_count = counter.get(RiskLevel.MEDIUM, 0)
    low_count = counter.get(RiskLevel.LOW, 0)
    total = len(risks)

    summary_lines = [
        "## 风险评估摘要",
        "",
        f"共识别 **{total}** 项风险：",
        "",
        f"| 风险等级 | 数量 | 占比 |",
        f"|---------|------|------|",
    ]
    for level, count, icon in [
        (RiskLevel.HIGH, high_count, RiskLevel.ICON[RiskLevel.HIGH]),
        (RiskLevel.MEDIUM, medium_count, RiskLevel.ICON[RiskLevel.MEDIUM]),
        (RiskLevel.LOW, low_count, RiskLevel.ICON[RiskLevel.LOW]),
    ]:
        pct = f"{count / total * 100:.1f}%" if total > 0 else "0%"
        summary_lines.append(f"| {icon} {RiskLevel.LABEL[level]} | {count} | {pct} |")

    # 整体评级结论
    if high_count > 0:
        conclusion = "⚠️ 存在高风险项，建议优先处理高风险条款后再签署。"
    elif medium_count > 0:
        conclusion = "📋 存在中风险项，建议在签署前进行条款协商与修改。"
    else:
        conclusion = "✅ 整体风险可控，可正常签署。"

    summary_lines.append("")
    summary_lines.append(f"**整体评估**: {conclusion}")

    return "\n".join(summary_lines)