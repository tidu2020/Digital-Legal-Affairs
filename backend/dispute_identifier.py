"""
国企法务助手 - 争议焦点识别模块

从文本中自动识别潜在争议焦点，生成争议问题并进行影响权重评估。
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# 争议类型 → 关键词 → 问题模板 映射
# ---------------------------------------------------------------------------
_KEYWORD_CATEGORY_MAP: dict = {
    "合同争议": {
        "违约金": "合同约定的违约金标准是否超过法定上限？是否存在被法院调减的风险？",
        "赔偿": "合同约定的赔偿责任范围和限额是否明确？是否存在赔偿不足或过度的风险？",
        "违约": "合同违约情形的界定及违约救济措施是否充分？",
        "解除": "合同解除的条件、程序及法律后果是否明确？",
        "无效": "合同是否存在导致整体或部分条款无效的情形？",
        "撤销": "合同是否存在可撤销的法律事由（重大误解、显失公平等）？",
        "履行": "合同履行过程中是否存在履约不能或履行瑕疵的争议风险？",
        "交付": "合同交付标准、时间节点及迟延交付的违约责任是否明确？",
        "质量": "合同质量标准及质量异议处理机制是否存在争议隐患？",
        "验收": "合同验收程序、验收标准及逾期验收的法律后果是否明确？",
    },
    "劳动争议": {
        "劳动": "劳动关系认定及劳动合同的订立、履行、变更是否存在争议？",
        "用工": "用工方式（正式用工/劳务派遣/外包）是否符合劳动法律规定？",
        "工资": "工资支付标准、加班费计算及工资克扣是否存在劳动争议风险？",
        "补偿": "经济补偿金或赔偿金的计算标准、支付条件是否符合法律规定？",
        "社保": "社会保险缴纳基数及险种覆盖是否合规？是否存在未足额缴纳的风险？",
        "工伤": "工伤认定条件、工伤保险待遇及用人单位赔偿责任是否存在争议？",
        "竞业": "竞业限制协议的范围、期限及经济补偿是否符合法律强制性规定？",
    },
    "知识产权争议": {
        "专利": "专利权归属、职务发明认定及专利使用许可是否存在争议？",
        "商标": "商标权归属、商标使用许可及商标侵权风险是否已充分评估？",
        "著作": "著作权归属、委托作品权利分配及使用授权是否存在争议？",
        "侵权": "是否存在知识产权侵权的潜在风险？侵权责任承担机制是否健全？",
        "许可": "知识产权许可范围、许可期限、许可费用及分许可权利是否明确？",
        "保密": "保密信息的范围界定、保密义务期限及违约责任是否充分？",
    },
    "公司治理争议": {
        "股东": "股东权利行使、股东知情权及股东会召集程序是否存在争议？",
        "董事": "董事任职资格、忠实勤勉义务履行及董事会决议效力是否存在争议？",
        "决议": "公司股东会/董事会决议的程序合法性及内容有效性是否存在争议？",
        "章程": "公司章程条款与公司法强制性规定是否存在冲突？",
        "出资": "股东出资义务的履行、出资方式合法性及抽逃出资是否存在争议？",
        "股权": "股权转让、股权代持、优先购买权行使及相关权益是否存在争议？",
    },
}


@dataclass
class DisputeIssue:
    """争议焦点数据类"""

    issue_id: str                      # 自动生成的争议编号，如 "DISPUTE-001"
    question: str                      # 争议问题，以疑问句形式呈现
    category: str                      # 争议类型
    impact_weight: str = "中"          # 影响权重：高/中/低
    impact_icon: str = "🟡"            # 影响图标：🔴/🟡/🟢
    related_clause: Optional[str] = None   # 关联条款
    legal_basis: Optional[str] = None      # 相关法律依据

    def __post_init__(self):
        self.impact_icon = {"高": "🔴", "中": "🟡", "低": "🟢"}.get(
            self.impact_weight, "🟡"
        )


def extract_dispute_issues(text: str, context: str = "") -> List[DisputeIssue]:
    """从文本中提取潜在争议焦点。

    基于关键词匹配识别争议类型，为每个匹配到的争议焦点生成疑问句式的问题。

    Args:
        text: 待分析的文本
        context: 可选的上下文信息（预留扩展）

    Returns:
        识别出的争议焦点列表
    """
    issues: List[DisputeIssue] = []
    counter = 0

    # 合并 context 和 text 用于分析
    combined_text = f"{context} {text}"

    for category, keyword_map in _KEYWORD_CATEGORY_MAP.items():
        for keyword, question_template in keyword_map.items():
            if keyword in combined_text:
                counter += 1
                issue_id = f"DISPUTE-{counter:03d}"
                issues.append(
                    DisputeIssue(
                        issue_id=issue_id,
                        question=question_template,
                        category=category,
                    )
                )

    # 对每个 issue 进行影响权重评估
    for issue in issues:
        assess_dispute_impact(issue, combined_text)

    return issues


def assess_dispute_impact(issue: DisputeIssue, text: str) -> DisputeIssue:
    """评估争议焦点的影响权重。

    根据文本中的关键词和金额信息判断影响程度：
    - 高🔴：出现"重大""严重""巨额""刑事"等关键词，或金额超过1000万
    - 中🟡：出现"一般""中等""一定"等关键词
    - 低🟢：出现"轻微""较小""低"等关键词

    Args:
        issue: 待评估的争议焦点
        text: 用于评估的文本

    Returns:
        更新了影响权重的争议焦点（与原对象相同）
    """
    impact = "中"  # 默认中等

    # 检查高风险关键词
    high_patterns = ["重大", "严重", "巨额", "刑事"]
    for p in high_patterns:
        if p in text:
            impact = "高"
            break

    # 检查金额是否超过1000万
    if impact != "高":
        amount_match = re.search(r"(\d+)\s*万", text)
        if amount_match:
            amount_wan = int(amount_match.group(1))
            if amount_wan > 1000:
                impact = "高"

    # 检查中等风险关键词
    if impact == "中":
        mid_patterns = ["一般", "中等", "一定"]
        for p in mid_patterns:
            if p in text:
                impact = "中"
                break

    # 检查低风险关键词
    if impact == "中":
        low_patterns = ["轻微", "较小", "低"]
        for p in low_patterns:
            if p in text:
                impact = "低"
                break

    issue.impact_weight = impact
    issue.impact_icon = {"高": "🔴", "中": "🟡", "低": "🟢"}[impact]
    return issue


def generate_dispute_summary(issues: List[DisputeIssue]) -> str:
    """生成争议焦点的 Markdown 摘要表格。

    Args:
        issues: 争议焦点列表

    Returns:
        Markdown 格式的摘要表格字符串
    """
    if not issues:
        return "### ⚡ 争议焦点识别\n\n未识别到明确的争议焦点。\n"

    lines = [
        "### ⚡ 争议焦点识别",
        "",
        "| 编号 | 争议焦点 | 类型 | 影响权重 | 关联条款 |",
        "|------|---------|------|---------|---------|",
    ]

    for issue in issues:
        clause = issue.related_clause if issue.related_clause else "-"
        lines.append(
            f"| {issue.issue_id} | {issue.question} "
            f"| {issue.category} "
            f"| {issue.impact_icon}{issue.impact_weight} "
            f"| {clause} |"
        )

    return "\n".join(lines) + "\n"