"""
国企法务助手 - 结构化输出模板

为 LLM 提供标准化的报告输出格式，确保不同审查任务的输出一致、完整。
"""

# ──────────────────────────────────────────────
# 模板定义
# ──────────────────────────────────────────────

REGULATION_REVIEW_TEMPLATE = """\
## 制度审核报告

### 一、基本信息
- 制度名称：[待填写]
- 制定部门：[待填写]
- 审核日期：[待填写]
- 审核依据：[待填写]

### 二、四维审查

#### 2.1 合法性审查
[是否符合上位法规定]

#### 2.2 合规性审查
[是否符合监管要求]

#### 2.3 风险可控性审查
[制度执行风险是否可控]

#### 2.4 体系兼容性审查
[与现有制度体系是否兼容]

### 三、总体结论
[综合审查结论]

### 四、整改建议
[具体整改建议列表]\
"""

CONTRACT_RISK_TEMPLATE = """\
## 合同风险审核报告

### 一、风险总览
- 审查条款总数：[N]
- 高风险项：[N] 🔴
- 中风险项：[N] 🟡
- 低风险项：[N] 🟢

### 二、风险清单

#### 🔴 高风险
| 编号 | 风险类型 | 关联条款 | 风险描述 | 法律依据 | 应对建议 |
|------|---------|---------|---------|---------|---------|

#### 🟡 中风险
| 编号 | 风险类型 | 关联条款 | 风险描述 | 法律依据 | 应对建议 |
|------|---------|---------|---------|---------|---------|

#### 🟢 低风险
| 编号 | 风险类型 | 关联条款 | 风险描述 | 法律依据 | 应对建议 |
|------|---------|---------|---------|---------|---------|

### 三、关键建议摘要
[最重要的3-5条建议]

### 四、分析局限性
[本分析基于AI模型，仅供参考]\
"""

COMPLIANCE_REVIEW_TEMPLATE = """\
## 合规审查报告

### 一、审查结论摘要
[总体合规评估]

### 二、风险清单

#### 🔴 重大风险
| 编号 | 问题类型 | 法律依据 | 风险描述 | 整改建议 | 优先级 |
|------|---------|---------|---------|---------|--------|

#### 🟡 重要风险
| 编号 | 问题类型 | 法律依据 | 风险描述 | 整改建议 | 优先级 |
|------|---------|---------|---------|---------|--------|

#### 🟢 一般风险
| 编号 | 问题类型 | 法律依据 | 风险描述 | 整改建议 | 优先级 |
|------|---------|---------|---------|---------|--------|

### 三、整改建议汇总
[按优先级排序的整改建议列表]\
"""

# ──────────────────────────────────────────────
# 模板注册表
# ──────────────────────────────────────────────

_TEMPLATES = {
    "regulation_review": REGULATION_REVIEW_TEMPLATE,
    "contract_risk": CONTRACT_RISK_TEMPLATE,
    "compliance_review": COMPLIANCE_REVIEW_TEMPLATE,
}

_TEMPLATE_INSTRUCTIONS = {
    "regulation_review": (
        "请按照以下格式输出制度审核报告，确保包含所有章节："
        "基本信息、四维审查（合法性、合规性、风险可控性、体系兼容性）、总体结论、整改建议。"
    ),
    "contract_risk": (
        "请按照以下格式输出合同风险审核报告，确保包含所有章节："
        "风险总览、按等级分类的风险清单（高🔴/中🟡/低🟢）、关键建议摘要、分析局限性。"
    ),
    "compliance_review": (
        "请按照以下格式输出合规审查报告，确保包含所有章节："
        "审查结论摘要、按等级分类的风险清单（重大🔴/重要🟡/一般🟢）、整改建议汇总。"
    ),
}


# ──────────────────────────────────────────────
# 公共接口
# ──────────────────────────────────────────────

def get_template(template_name: str) -> str:
    """根据模板名称返回对应的模板字符串。

    Args:
        template_name: 模板名称，可选值为 "regulation_review", "contract_risk", "compliance_review"

    Returns:
        对应的模板字符串

    Raises:
        ValueError: 当 template_name 不在注册表中时
    """
    if template_name not in _TEMPLATES:
        available = ", ".join(_TEMPLATES.keys())
        raise ValueError(
            f"未知的模板名称 '{template_name}'，可用模板: {available}"
        )
    return _TEMPLATES[template_name]


def get_template_instruction(template_name: str) -> str:
    """返回指定模板的 LLM 使用指令。

    Args:
        template_name: 模板名称，可选值为 "regulation_review", "contract_risk", "compliance_review"

    Returns:
        对应模板的使用指令字符串

    Raises:
        ValueError: 当 template_name 不在注册表中时
    """
    if template_name not in _TEMPLATE_INSTRUCTIONS:
        available = ", ".join(_TEMPLATE_INSTRUCTIONS.keys())
        raise ValueError(
            f"未知的模板名称 '{template_name}'，可用模板: {available}"
        )
    return _TEMPLATE_INSTRUCTIONS[template_name]