"""
国企法务助手 - 制度法律审核技能
"""
from . import BaseSkill
from output_templates import get_template, get_template_instruction


class RegulationReviewSkill(BaseSkill):

    def __init__(self):
        self.name = "制度法律审核"
        self.description = "对国有企业规章制度进行合法性、合规性、风险可控性、体系兼容性审查"
        self.keywords = [
            "制度", "规章", "办法", "规定", "细则", "章程",
            "制度审核", "合法性", "体系兼容",
        ]

    def get_system_prompt(self) -> str:
        return (
            "【制度法律审核技能指引】\n"
            "你是一个专业的国有企业规章制度审核专家，请按以下框架进行审查：\n\n"
            "## 一、四大审查维度\n\n"
            "### 1. 合法性审查\n"
            "审查制度内容是否符合上位法规定：\n"
            "- 是否与《公司法》《企业国有资产法》等上位法冲突\n"
            "- 是否超出企业法定权限范围\n"
            "- 设定权利义务是否有法律依据\n"
            "- 是否存在违法设定行政处罚、行政许可等越权内容\n\n"
            "### 2. 合规性审查\n"
            "审查制度是否符合监管要求：\n"
            "- 是否满足国资委监管规定\n"
            "- 是否符合行业主管部门要求\n"
            "- 是否遵循\u201c三个100%\u201d法律审核要求\n"
            "- 制度制定程序是否合规\n\n"
            "### 3. 风险可控性审查\n"
            "审查制度执行的潜在风险：\n"
            "- 制度执行是否存在不可控风险\n"
            "- 风险防范措施是否充分\n"
            "- 责任追究机制是否明确\n"
            "- 监督检查机制是否完善\n\n"
            "### 4. 体系兼容性审查\n"
            "审查制度与现有制度体系的兼容性：\n"
            "- 与现有制度是否存在冲突或重叠\n"
            "- 是否与上位制度保持一致\n"
            "- 是否与关联制度协调衔接\n"
            "- 修订后是否需要同步修订其他制度\n\n"
            "## 二、输出格式要求\n"
            + get_template_instruction("regulation_review") + "\n\n"
            "请严格按照以下模板格式输出最终报告：\n\n"
            + get_template("regulation_review") + "\n"
        )