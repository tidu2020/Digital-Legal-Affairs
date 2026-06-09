"""
国企法务助手 - 合同信息结构化提取模块
"""
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class PartyInfo:
    name: str = ""
    role_label: str = ""


@dataclass
class ClauseSummary:
    title: str = ""
    summary: str = ""
    risk_assessment: str = ""


@dataclass
class ContractInfo:
    contract_name: str = ""
    contract_type: str = ""
    type_keywords: List[str] = field(default_factory=list)
    party_a: PartyInfo = field(default_factory=PartyInfo)
    party_b: PartyInfo = field(default_factory=PartyInfo)
    main_obligation_a: str = ""
    main_obligation_b: str = ""
    subject_matter: str = ""
    price: str = ""
    payment_method: str = ""
    existing_clauses: List[ClauseSummary] = field(default_factory=list)
    missing_clauses: List[str] = field(default_factory=list)
    inferred_party: str = ""
    inference_reason: str = ""


# ============================================================
# 提取系统提示词
# ============================================================

EXTRACTION_SYSTEM_PROMPT = """你是一位合同信息提取专家。请从给定的合同文本中提取以下结构化信息。

【必须输出纯JSON，以{开头、}结尾，不要用```json```包裹】

【输出格式】
{
  "contract_name": "合同名称",
  "contract_type": "合同类型（买卖/借款/租赁/融资租赁/保理/承揽/建设工程/委托/物业服务/中介/合伙/技术/服务/特许经营/运输/保管/仓储/行纪/居间/赠与/保证/其他）",
  "type_keywords": ["关键词1", "关键词2"],
  "party_a": {"name": "甲方名称", "role_label": "甲方"},
  "party_b": {"name": "乙方名称", "role_label": "乙方"},
  "main_obligation_a": "甲方的主给付义务",
  "main_obligation_b": "乙方的主给付义务",
  "subject_matter": "交易标的",
  "price": "价款或对价",
  "payment_method": "支付方式",
  "existing_clauses": [
    {"title": "条款标题", "summary": "原文前50字摘要", "risk_assessment": "初步风险评估"}
  ],
  "missing_clauses": ["缺失的应备条款列表"],
  "inferred_party": "推断的己方立场（甲方/乙方/无法推断）",
  "inference_reason": "推断理由"
}

【提取要求】
1. 若某字段无法从文本中提取，填写空字符串或空数组。
2. existing_clauses 按原文条款顺序逐条输出，summary 截取该条款原文前50字。
3. 缺失条款对照该类合同的应备条款清单判断。
4. 己方立场推断：分析权利义务条款的整体平衡性。
5. 不明确类型填写"其他"。"""


# ============================================================
# 合同提取器
# ============================================================

class ContractExtractor:
    """合同信息结构化提取器"""

    def __init__(self, llm_client):
        """
        Args:
            llm_client: LLM 客户端实例，需有 async chat(messages, stream=False) 方法
        """
        self._llm_client = llm_client

    async def extract(self, contract_text: str) -> ContractInfo:
        """从合同文本中提取结构化信息

        Args:
            contract_text: 合同全文文本

        Returns:
            ContractInfo: 结构化合同信息
        """
        if not contract_text or not contract_text.strip():
            print("[ContractExtractor] 合同文本为空")
            return ContractInfo()

        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"请从以下合同文本中提取结构化信息：\n\n{contract_text}"}
        ]

        try:
            print("[ContractExtractor] 请求 LLM 提取合同信息...")
            response = await self._llm_client.chat(messages, stream=False, temperature=0.3)
            print(f"[ContractExtractor] LLM 返回长度: {len(response)}")
            return self._parse_response(response)
        except Exception as e:
            print(f"[ContractExtractor] 提取失败: {e}")
            return ContractInfo()

    def _parse_response(self, response: str) -> ContractInfo:
        """解析 LLM 返回的 JSON 字符串为 ContractInfo

        Args:
            response: LLM 返回的原始文本

        Returns:
            ContractInfo: 解析后的结构化信息
        """
        # 尝试多种方式提取 JSON
        json_str = self._extract_json(response)

        if json_str is None:
            print("[ContractExtractor] 无法从响应中提取 JSON")
            return ContractInfo()

        try:
            data = json.loads(json_str)
            return self._dict_to_contract_info(data)
        except json.JSONDecodeError as e:
            print(f"[ContractExtractor] JSON 解析失败: {e}")
            return ContractInfo()

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """从文本中提取 JSON 字符串

        支持:
        - 纯 JSON
        - ```json ... ``` 包裹
        - 文本中嵌入的 JSON 对象
        """
        if not text:
            return None

        text = text.strip()

        # 尝试直接解析
        if text.startswith("{") and text.endswith("}"):
            return text

        # 尝试去除 ```json ``` 包裹
        code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if code_block_match:
            return code_block_match.group(1).strip()

        # 尝试在文本中查找 JSON 对象
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json_match.group(0).strip()

        return None

    @staticmethod
    def _dict_to_contract_info(data: dict) -> ContractInfo:
        """将字典转换为 ContractInfo 对象"""
        # 解析甲方信息
        party_a_data = data.get("party_a", {})
        party_a = PartyInfo(
            name=party_a_data.get("name", ""),
            role_label=party_a_data.get("role_label", ""),
        )

        # 解析乙方信息
        party_b_data = data.get("party_b", {})
        party_b = PartyInfo(
            name=party_b_data.get("name", ""),
            role_label=party_b_data.get("role_label", ""),
        )

        # 解析条款摘要
        existing_clauses = []
        for clause_data in data.get("existing_clauses", []):
            existing_clauses.append(ClauseSummary(
                title=clause_data.get("title", ""),
                summary=clause_data.get("summary", ""),
                risk_assessment=clause_data.get("risk_assessment", ""),
            ))

        return ContractInfo(
            contract_name=data.get("contract_name", ""),
            contract_type=data.get("contract_type", ""),
            type_keywords=data.get("type_keywords", []),
            party_a=party_a,
            party_b=party_b,
            main_obligation_a=data.get("main_obligation_a", ""),
            main_obligation_b=data.get("main_obligation_b", ""),
            subject_matter=data.get("subject_matter", ""),
            price=data.get("price", ""),
            payment_method=data.get("payment_method", ""),
            existing_clauses=existing_clauses,
            missing_clauses=data.get("missing_clauses", []),
            inferred_party=data.get("inferred_party", ""),
            inference_reason=data.get("inference_reason", ""),
        )


# ============================================================
# 便捷函数
# ============================================================

async def extract_contract_info(contract_text: str) -> ContractInfo:
    """从合同文本中提取结构化信息的便捷函数

    自动导入全局 llm_client 并创建提取器。

    Args:
        contract_text: 合同全文文本

    Returns:
        ContractInfo: 结构化合同信息
    """
    try:
        from llm_client import llm_client
        extractor = ContractExtractor(llm_client)
        return await extractor.extract(contract_text)
    except Exception as e:
        print(f"[extract_contract_info] 错误: {e}")
        return ContractInfo()