"""
国企法务助手 - 案由匹配模块

根据合同类型，将其映射到《民事案件案由规定》（2025年版，法〔2025〕227号，2026年1月1日施行）的案由树。
"""
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# 系统提示词
# ---------------------------------------------------------------------------

CASE_MATCH_SYSTEM_PROMPT = """你是一位中国民事案由匹配专家。请根据合同类型，将其映射到《民事案件案由规定》（2025年版，法〔2025〕227号，2026年1月1日施行）的案由树。

2025年版案由体系为十二大部分、四级结构：
- 第一部分 人格权纠纷
- 第二部分 婚姻家庭、继承纠纷
- 第三部分 物权纠纷
- 第四部分 合同、准合同纠纷（十、合同纠纷 / 十一、不当得利纠纷 / 十二、无因管理纠纷）
- 第五部分 知识产权与竞争纠纷
- 第六部分 数据、网络虚拟财产纠纷
- 第七部分 劳动争议、人事争议、新就业形态用工纠纷
- 第八部分 海事海商纠纷
- 第九部分 与公司、证券、保险、票据等有关的民事纠纷
- 第十部分 侵权责任纠纷
- 第十一部分 非讼程序案件案由
- 第十二部分 特殊诉讼程序案件案由

合同纠纷位于第四部分"十、合同纠纷"，包含案由编号78~147，共70个三级案由。

输出 JSON 格式：
{
  "level1": "一级案由",
  "level2": "二级案由",
  "level3": "三级案由",
  "level4": "四级案由（如无则填null）",
  "full_path": "完整路径",
  "alternative_causes": ["备选案由1", "备选案由2"],
  "match_confidence": "高/中/低"
}

【必须输出纯JSON，以{开头、}结尾，不要用```json```包裹】

若为无名合同或混合合同，找出最接近的1-2个典型合同案由作为比照基准。"""


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class CaseCause:
    """案由匹配结果数据类"""

    level1: str = ""                        # 一级案由
    level2: str = ""                        # 二级案由
    level3: str = ""                        # 三级案由
    level4: Optional[str] = None            # 四级案由
    full_path: str = ""                     # 完整路径
    alternative_causes: List[str] = field(default_factory=list)  # 备选案由
    match_confidence: str = "中"             # 匹配置信度：高/中/低


# ---------------------------------------------------------------------------
# 案由匹配器
# ---------------------------------------------------------------------------

class CaseCauseMatcher:
    """案由匹配器，通过 LLM 将合同类型映射到民事案由"""

    def __init__(self, llm_client):
        """初始化案由匹配器。

        Args:
            llm_client: LLM 客户端实例，需支持 async chat 方法
        """
        self._llm_client = llm_client

    async def match(
        self,
        contract_type: str,
        type_keywords: List[str] = None,
    ) -> CaseCause:
        """将合同类型匹配到民事案由。

        Args:
            contract_type: 合同类型名称
            type_keywords: 可选的关键词列表，用于辅助匹配

        Returns:
            CaseCause: 匹配到的案由信息，匹配失败时返回默认值
        """
        try:
            keywords_str = ", ".join(type_keywords) if type_keywords else "无"
            user_prompt = (
                f"合同类型：{contract_type}\n"
                f"关键词：{keywords_str}\n\n"
                f"请匹配最合适的三级案由，输出完整四级路径。"
            )

            messages = [
                {"role": "system", "content": CASE_MATCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            response = await self._llm_client.chat(messages, stream=False)
            return self._parse_response(response, contract_type)

        except Exception as e:
            print(f"[CaseCauseMatcher] 匹配失败: {e}")
            return CaseCause()

    def _parse_response(self, response: str, contract_type: str) -> CaseCause:
        """解析 LLM 返回的 JSON 响应。

        Args:
            response: LLM 原始响应文本
            contract_type: 合同类型（用于错误日志）

        Returns:
            CaseCause: 解析后的案由信息
        """
        try:
            # 尝试提取纯 JSON（去除可能的 markdown 包裹）
            json_str = self._extract_json(response)

            data = json.loads(json_str)

            return CaseCause(
                level1=data.get("level1", ""),
                level2=data.get("level2", ""),
                level3=data.get("level3", ""),
                level4=data.get("level4"),
                full_path=data.get("full_path", ""),
                alternative_causes=data.get("alternative_causes", []),
                match_confidence=data.get("match_confidence", "中"),
            )

        except (json.JSONDecodeError, ValueError) as e:
            print(f"[CaseCauseMatcher] JSON 解析失败 ({contract_type}): {e}")
            print(f"[CaseCauseMatcher] 原始响应: {response[:500]}")
            return CaseCause()

    @staticmethod
    def _extract_json(text: str) -> str:
        """从文本中提取 JSON 字符串。

        处理 LLM 可能返回的各种格式：
        - 纯 JSON 文本
        - 被 ```json ... ``` 包裹的 JSON
        - 被 ``` ... ``` 包裹的 JSON
        - 文本中嵌入了 JSON 片段

        Args:
            text: 原始响应文本

        Returns:
            提取出的 JSON 字符串
        """
        text = text.strip()

        # 尝试匹配 ```json ... ``` 或 ``` ... ```
        fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fenced_match:
            return fenced_match.group(1).strip()

        # 尝试匹配以 { 开头、} 结尾的 JSON 片段
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            return json_match.group(0).strip()

        return text


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

async def match_case_cause(
    contract_type: str,
    keywords: List[str] = None,
) -> CaseCause:
    """将合同类型匹配到民事案由（便捷函数）。

    自动导入全局 llm_client 并创建匹配器。

    Args:
        contract_type: 合同类型名称
        keywords: 可选的关键词列表

    Returns:
        CaseCause: 匹配到的案由信息
    """
    try:
        from llm_client import llm_client
        matcher = CaseCauseMatcher(llm_client)
        return await matcher.match(contract_type, keywords)
    except Exception as e:
        print(f"[match_case_cause] 错误: {e}")
        return CaseCause()