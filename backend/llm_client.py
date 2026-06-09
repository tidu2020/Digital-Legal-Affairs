"""
国企法务助手 - 私有化大模型客户端（异步版）
"""
import json
import re
from typing import AsyncIterator, Dict, Any, Optional

import httpx

from config import LLM_CONFIG
from skills.skill_loader import skill_loader


LQ = "\u201c"  # left double quotation mark
RQ = "\u201d"  # right double quotation mark


class LLMClient:
    """私有化部署的大模型客户端（基于 httpx 异步 HTTP，支持连接池复用）"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or LLM_CONFIG
        self.base_url = self.config["base_url"]
        self.api_key = self.config["api_key"]
        self.model = self.config["model"]
        self.thinking_enabled = self.config.get("thinking_enabled", False)
        self._fallback_mode = False
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=20),
            )
        return self._client

    async def chat(
        self,
        messages: list,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> str:
        if self._fallback_mode:
            return self._generate_mock_response(messages)

        # thinking 模式下 reasoning_tokens 计入 max_tokens，需要更大的配额
        effective_max_tokens = max_tokens * 3 if self.thinking_enabled else max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": effective_max_tokens,
            "stream": stream,
        }

        if self.thinking_enabled:
            payload["chat_template_kwargs"] = {"enable_thinking": True}

        client = await self._get_client()
        try:
            print(f"[LLM] 请求 API, 消息数: {len(messages)}, max_tokens: {effective_max_tokens}")
            response = await client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                msg = result["choices"][0]["message"]
                reply = msg.get("content", "")
                # thinking 模式下 content 可能为空字符串（reasoning 消耗了全部 token）
                if not reply and self.thinking_enabled:
                    reasoning = msg.get("reasoning_content", "")
                    if reasoning:
                        print(f"[LLM] thinking 模式 content 为空，reasoning 长度: {len(reasoning)}")
                        return f"思考过程：\n{reasoning}\n\n---\n\n抱歉，模型思考过程消耗了过多 token，未能生成最终回复。请尝试简化问题或稍后重试。"
                print(f"[LLM] 回复成功, 长度: {len(reply)}")
                return reply
            return "抱歉，未能获取到有效回复。"

        except httpx.TimeoutException:
            print("[LLM] 请求超时，切换模拟模式")
            self._fallback_mode = True
            return self._generate_mock_response(messages)
        except httpx.HTTPError as e:
            print(f"[LLM] 请求失败: {e}，切换模拟模式")
            self._fallback_mode = True
            return self._generate_mock_response(messages)
        except Exception as e:
            print(f"[LLM] 未知错误: {e}，切换模拟模式")
            self._fallback_mode = True
            return self._generate_mock_response(messages)

    def _generate_mock_response(self, messages: list) -> str:
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        user_message_lower = user_message.lower()

        if "三个100%" in user_message or "100%" in user_message:
            return (
                "**三个100%** 是国有企业法人务合规的核心要求：\n\n"
                "1. **重大经营决策法律审核率 100%**\n"
                "   - 涵盖合并、分立、破产、解散、增减资本、修订章程、重组改制、上市、股权收购/转让、资产收购/转让/租赁、投融资、对外担保、招投标等事项\n\n"
                "2. **规章制度法律审核率 100%**\n"
                "   - 所有新增和修订的规章制度必须经过法律合规部审核\n\n"
                "3. **合同法律审核率 100%**\n"
                "   - 所有合同协议文本必须经过法律合规部审核\n\n"
                "---\n>>> 以上为系统模拟回复。请确保大模型API服务正常运行以获取实时回复。"
            )

        if "合同" in user_message:
            return (
                "**合同管理要点**：\n\n"
                f"国有企业法人务合规遵循{LQ}六部门协作审核{RQ}机制：\n\n"
                "| 部门 | 主要职责 |\n|------|----------|\n"
                "| 合同管理部 | 归口管理，组织谈判，起草范本 |\n"
                "| 法律合规部 | 法律审核，参与重大合同起草谈判 |\n"
                "| 财务管理部 | 财务条款审核 |\n"
                "| 需求部门 | 提出合同需求，确定相对方 |\n"
                "| 承办部门 | 起草文本、组织谈判、资料立卷 |\n"
                "| 履约部门 | 履行监控、支付管理、变更处理 |\n\n"
                "**关键时限**：\n"
                "- 重大合同谈判需提前3个工作日通知法律合规部\n"
                "- 履约评价：每年6月末和12月末各一次\n\n"
                "---\n>>> 以上为系统模拟回复。请确保大模型API服务正常运行以获取实时回复。"
            )

        if "诉讼" in user_message or "仲裁" in user_message or "案件" in user_message:
            return (
                "**诉讼仲裁案件管理要点**：\n\n"
                "**案件分类处理**：\n"
                "- 国企/子公司为涉案主体：法律合规部牵头处理\n"
                "- 下属企业为涉案主体：下属企业自行处理，法律合规部指导监督\n\n"
                "**重大案件标准**（涉案金额）：\n"
                "| 涉案金额 | 包案领导 |\n|----------|----------|\n"
                "| >=1000万元 | 涉案责任部门主管领导 + 下属企业主要领导 |\n"
                "| >=5000万元 | 国企主要领导 + 下属企业主要领导 |\n\n"
                "**关键时限**：\n"
                "- 收到应诉文书 -> 填报案件情况：3个工作日\n"
                "- 下属企业拟提起诉讼：至少提前10个工作日\n"
                "- 收到判决/裁定/调解书：3个工作日内报送\n\n"
                "---\n>>> 以上为系统模拟回复。请确保大模型API服务正常运行以获取实时回复。"
            )

        if "合规" in user_message:
            return (
                "**合规管理体系要点**：\n\n"
                f"推行{LQ}四位一体{RQ}合规体系：法务、合规、内控、风控融合管理。\n\n"
                f"**{LQ}三张清单{RQ}机制**：\n"
                f"1. **合规义务清单** - 明确{LQ}必须做什么、禁止做什么{RQ}\n"
                "2. **流程控制清单** - 明确关键节点的审核标准\n"
                "3. **岗位职责清单** - 各岗位合规责任与失职后果\n\n"
                "**重点领域**：\n"
                "- 公司治理、财务税收、劳动用工、安全生产\n"
                "- 知识产权、数据安全、采购管理、投资管理、融资担保\n\n"
                "**举报渠道**：\n"
                "- 举报邮箱：hgjb@bii.com.cn\n"
                "- 举报电话：84686317\n\n"
                "---\n>>> 以上为系统模拟回复。请确保大模型API服务正常运行以获取实时回复。"
            )

        return (
            f"感谢您的咨询！您的问题是：\n\n> {user_message}\n\n"
            "作为国企法务助手，我可以为您提供以下方面的咨询：\n\n"
            "1. **制度法律审核** - 规章制度合法性、合规性审核\n"
            "2. **合同管理咨询** - 合同全生命周期管理流程\n"
            "3. **诉讼仲裁案件管理** - 案件处理流程和时限要求\n"
            "4. **合规管理体系咨询** - 四位一体合规体系建设\n"
            "5. **法务合规公文写作** - 按国有企业标准模板起草公文\n\n"
            "---\n>>> 当前系统运行在模拟模式，请确保大模型API服务正常。"
        )

    async def chat_stream(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> AsyncIterator[str]:
        if self._fallback_mode:
            response = self._generate_mock_response(messages)
            for chunk in self._chunk_text(response, 8):
                yield chunk
            return

        # thinking 模式下 reasoning_tokens 计入 max_tokens，需要更大的配额
        effective_max_tokens = max_tokens * 3 if self.thinking_enabled else max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": effective_max_tokens,
            "stream": True,
        }

        if self.thinking_enabled:
            payload["chat_template_kwargs"] = {"enable_thinking": True}

        client = await self._get_client()
        try:
            print(f"[LLM-Stream] 请求 API, 消息数: {len(messages)}, max_tokens: {effective_max_tokens}")
            async with client.stream(
                "POST", self.base_url, headers=headers, json=payload
            ) as response:
                response.raise_for_status()
                chunk_count = 0
                has_content = False
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            json_data = json.loads(data)
                            if "choices" in json_data and json_data["choices"]:
                                delta = json_data["choices"][0].get("delta", {})
                                # thinking 模式：先输出 reasoning_content，再输出 content
                                # 两者不会同时出现在同一个 delta 中
                                if "content" in delta and delta["content"]:
                                    chunk_count += 1
                                    has_content = True
                                    yield delta["content"]
                                # reasoning_content 不输出给用户，但记录日志
                                elif "reasoning_content" in delta and delta["reasoning_content"]:
                                    if not has_content:
                                        # 首次收到 reasoning，提示用户正在思考
                                        pass
                        except json.JSONDecodeError:
                            continue
                print(f"[LLM-Stream] 完成, 共 {chunk_count} 个数据块")

        except Exception as e:
            print(f"[LLM-Stream] API 失败: {e}，切换模拟模式")
            self._fallback_mode = True
            response = self._generate_mock_response(messages)
            for chunk in self._chunk_text(response, 8):
                yield chunk

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 8):
        sentences = re.split(r"(\n\n|\n|。|！|？|，|；|：|\)|）)", text)
        buffer = ""
        for part in sentences:
            buffer += part
            if len(buffer) >= chunk_size:
                yield buffer
                buffer = ""
        if buffer:
            for i in range(0, len(buffer), chunk_size):
                yield buffer[i : i + chunk_size]


def build_legal_system_prompt(knowledge_context: str = "", user_message: str = "") -> str:
    """构建系统提示词，支持技能匹配增强"""
    base_prompt = (
        "你是国企法务合规助手，基于国企法务合规体系提供专业支持。\n\n"
        "核心能力：\n"
        "1. 制度法律审核 - 合法性、合规性、风险可控性、体系兼容性审核\n"
        "2. 合同管理咨询 - 合同全生命周期管理和风险提示\n"
        "3. 诉讼仲裁案件管理 - 案件处理流程和时限\n"
        f"4. 合规管理咨询 - {LQ}四位一体{RQ}合规体系\n"
        "5. 法务公文写作 - 按国企标准模板起草\n\n"

        "6. 法条引用规范（重要！）：\n"
        "   - 引用法律时必须使用书名号《》括起完整法律名称，如《中华人民共和国民法典》\n"
        "   - 引用具体条款时使用格式：《XX法》第X条，如《中华人民共和国公司法》第16条\n"
        "   - 使用阿拉伯数字标注条款号，如第1条、第10条、第143条\n"
        "   - 如果知道法律的公布日期和施行日期，请一并标注\n"
        "   - 禁止引用已知废止或已被替代的法律\n\n"

        "7. 法条检索与校验 - 当系统提供【法条检索结果】时，你必须严格依据其中"
        "国家法律法规数据库(flk.npc.gov.cn)的检索结果来引用法条。"
        "如果检索结果中某法律标注为'已废止'或'已修改'，必须提醒用户注意时效性。"
        "如果检索结果中法条未找到或与你的认知不一致，优先采信官方数据库的结果。\n\n"

        "原则：以现行制度为依据；主动提示关键时限；区分一般与重大事项；"
        "涉及重大决策时提醒需正式法律意见。\n\n"
        "关键术语：三个100%、四位一体、三张清单、三道防线。\n"

        "法条引用格式示例：\n"
        "  - 《中华人民共和国民法典》第143条（2020年公布，2021年施行）\n"
        "  - 《中华人民共和国劳动合同法》第39条\n"
        "  - 《中华人民共和国公司法》第16条第2款\n"
    )

    if knowledge_context:
        base_prompt += f"\n【知识库参考】\n{knowledge_context}\n请结合参考内容回答。"
        if "法条检索结果" in knowledge_context:
            base_prompt += (
                "\n⚠️ 法条引用规则：请优先引用上述【法条检索结果】中的法条内容。"
                "如果检索结果与你训练数据有冲突，以检索结果为准。"
                "标注法条时效性状态，引用时注明来源为'国家法律法规数据库'。"
            )

    # 技能匹配增强：根据用户消息匹配专项技能指引
    if user_message:
        try:
            scheduler = _get_skill_scheduler()
            base_prompt = scheduler.build_system_prompt(user_message, base_prompt)
        except Exception as e:
            print(f"[Skill] 技能匹配失败: {e}")

    return base_prompt


# 技能调度器缓存
_skill_scheduler = None


def _get_skill_scheduler():
    """懒加载技能调度器"""
    global _skill_scheduler
    if _skill_scheduler is None:
        _skill_scheduler = skill_loader.load_all_skills()
    return _skill_scheduler


llm_client = LLMClient()