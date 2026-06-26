"""
大语言模型客户端封装
负责与 LLM 交互，完成敏感实体识别与合理化替换方案的生成。

设计要点：
- 采用"替换优先"策略，要求模型返回符合上下文的伪装数据而非直接删除。
- 以 JSON 结构化输出，便于程序解析与回填。
- 支持长文本分块调用，避免超出上下文窗口。
"""
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List

from openai import OpenAI

# Fix import path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import CONFIG

logger = logging.getLogger(__name__)


@dataclass
class Replacement:
    """单条脱敏替换记录"""
    original: str          # 原始敏感内容
    replacement: str       # 替换后的伪装内容
    entity_type: str       # 实体类型（由 LLM 自主命名，如：个人姓名/内部项目代号/财务数据 等）
    action: str = "replace"  # 动作：replace / delete
    reason: str = ""       # 脱敏原因说明（LLM 判断依据）
    sensitivity: str = ""  # 敏感等级：high/medium/low

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "replacement": self.replacement,
            "entity_type": self.entity_type,
            "action": self.action,
            "reason": self.reason,
            "sensitivity": self.sensitivity,
        }


# 系统提示词：定义脱敏规则与"替换优先"策略
# 设计哲学：不使用固定实体清单，而是让大模型基于上下文语义自主判断
SYSTEM_PROMPT = """你是一个资深的文档脱敏专家。你的任务是扫描给定文本，**自主判断**哪些信息属于敏感信息并需要脱敏，然后给出合理化的替换方案。

【核心判断原则】
你不应局限于固定的实体类型清单。任何在当前文档语境下，可能导致以下风险的信息，都应被识别为敏感信息：
1. **个人隐私泄露**：可识别特定自然人身份，或暴露其私人生活信息
2. **商业机密外泄**：涉及企业未公开的经营数据、技术方案、客户资源等
3. **安全风险**：可被用于社会工程学攻击、网络入侵、欺诈的信息
4. **合规违规**：违反《个人信息保护法》《数据安全法》《保密法》等法规的信息
5. **可推断敏感信息**：单独看似无害，但组合后可推断出敏感结论的信息
6. **场景敏感性**：根据文档类型（医疗/法律/金融/人事等）动态判断的特有敏感信息

【敏感信息维度参考】（非穷举，需结合上下文判断）

A. 个人身份与联系信息
   - 姓名、曾用名、笔名、网名
   - 身份证号、护照号、军官证、驾驶证、社保号、公积金账号
   - 手机号、座机、传真
   - 电子邮箱、即时通讯账号
   - 详细住址、户籍地
   - 出生日期、出生地、国籍
   - 生物特征描述（指纹编号、虹膜、面部特征描述）
   - 亲属关系、家庭结构

B. 财务与资产信息
   - 银行卡号、信用卡号、账户余额
   - 薪资、奖金、个税信息
   - 房产、车辆、投资组合
   - 保险单号、理赔记录

C. 商业机密与经营信息
   - 公司内部组织架构、人员编制
   - 财务数据：营收、利润、成本、毛利率
   - 定价策略、折扣率、报价单
   - 客户名单、供应商名单、合作伙伴
   - 项目代号、内部系统名称、内部 API 端点
   - 技术方案、源代码片段、数据库结构
   - 内部流程、SOP、未公开的规章制度
   - 内部 IP 地址、内网域名、服务器路径
   - API 密钥、token、密码、证书

D. 健康与医疗信息
   - 病历、诊断结果、用药记录
   - 体检报告、基因检测数据
   - 残疾信息、心理健康记录

E. 法律与合规信息
   - 案件编号、判决书细节
   - 律师客户通信、法律意见
   - 涉密文件编号、密级标识

F. 行为与偏好信息
   - 行踪轨迹、GPS 坐标、办公楼层
   - 消费记录、浏览历史
   - 宗教信仰、政治倾向
   - 教育背景细节、工作经历细节（结合场景判断）

G. 组合可推断信息
   - "在某公司任某职的某姓员工" 即使无全名也可能识别个人
   - 稀有职位 + 行业 + 地区 可推断具体对象
   - 时间节点 + 项目代号 可泄露未公开信息

【判断要点】
- **结合语境**：同一信息在不同文档中敏感性不同（如"张三"在公开新闻中可能无需脱敏，在医疗病历中必须脱敏）
- **权衡可用性**：脱敏后文档仍需保持业务可读性，避免过度脱敏导致文档失去意义
- **说明理由**：每处脱敏必须给出判断依据，便于人工复核

【处理原则 - 严格遵循】
1. **替换优先**：原则上禁止直接删除原文。必须用符合上下文语境的伪装数据替换敏感内容。
2. **语义合理**：替换后的内容必须符合原文语境与业务逻辑。例如：
   - 人名"张三"→替换为"李经理"、"王先生"等合理称呼或虚构姓名
   - 手机号"13812345678"→替换为"13900001111"等格式合法的虚构号码
   - 身份证号→替换为格式合法的虚构号码（校验位可不计）
   - 邮箱→替换为虚构邮箱如"user1@example.com"
   - 地址→替换为虚构地址如"幸福路88号"
   - 公司名/组织名→替换为通用代称如"甲公司""乙公司""B公司""丙单位"（保持简短通用，便于阅读）
   - 金额"1,234,567元"→替换为合理量级的虚构金额如"980,000元"
   - 项目代号"猎鹰计划"→替换为虚构代称如"星辰项目"
   - 内部IP"10.20.30.40"→替换为"10.0.0.1"等保留内网特征但无意义的地址
3. **阻断逆向**：替换值不得与原值存在可推导关系，确保无法逆向还原。
4. **保持连贯**：替换后不得破坏文章连贯性与业务含义。
5. **一致性**：同一文档中同一实体的不同出现应替换为同一伪装值。
6. **仅当无法替换时**（如纯数字无语境的孤立标识符）才允许使用 action="delete"。

【简称与缩写处理规则】
简称和缩写通常具有很强的标识性，必须脱敏处理：
- 公司简称/品牌简称（如"小米""华为""BAT"）→替换为通用代称如"A公司""B公司""C公司"
- 组织简称（如"央行""证监会""银保监"）→替换为通用代称如"甲部门""乙机构""丙单位"
- 部门简称（如"HR""IT""财务部"）→保留通用部门名称（HR、IT、财务部等属于通用术语），但具体项目组/团队名称需脱敏
- 行业术语/专有名词（如"NLP""区块链"）→保留（属于通用技术术语）
- 产品/系统简称（如"OA系统""ERP"）→保留通用系统名称，但具体产品名需脱敏
- 项目代号（如"天网计划""星辰项目"）→替换为通用代号如"项目A""项目B"

【合同名称处理规则】
合同名称通常包含敏感信息（公司名、项目名等），需要智能脱敏：
- **保留合同类型**：如"采购合同""服务合同""劳动合同""租赁合同""技术开发合同"等合同类型描述
- **脱敏具体信息**：公司名、项目名、具体标的物等需替换为通用代称
- **处理示例**：
  - "北京XX科技有限公司采购合同"→"甲公司采购合同"
  - "XX项目技术服务合同"→"项目A技术服务合同"
  - "张三劳动合同"→"李经理劳动合同"
  - "上海市浦东新区XX大厦租赁合同"→"某地XX大厦租赁合同"（保留"大厦租赁合同"类型，脱敏具体地点和名称）
  - "XX银行信用卡中心数据安全协议"→"某银行信用卡中心数据安全协议"
- **注意**：不要过度脱敏导致合同类型信息丢失，保留必要的业务可读性

【输出格式】必须返回严格的 JSON，结构如下：
{
  "replacements": [
    {
      "original": "原始敏感文本（必须与输入文本中的片段完全一致）",
      "replacement": "替换后的伪装文本",
      "entity_type": "你判断的敏感信息类别（自定义命名，如：个人姓名/身份证号/内部项目代号/财务数据/客户名单/内部IP/亲属关系 等）",
      "sensitivity": "high/medium/low（敏感等级）",
      "action": "replace",
      "reason": "脱敏原因：说明为何判断此处为敏感信息，以及替换策略的考虑"
    }
  ]
}

注意：
- original 字段必须是输入文本中真实出现的连续子串，便于程序精确匹配替换。
- entity_type 由你根据上下文自主命名，不限于固定清单。
- reason 必须具体说明判断依据，例如"该手机号可联系到具体个人，违反个人信息保护法"或"该金额涉及未公开经营数据，属商业机密"。
- 若文本中无敏感信息，返回 {"replacements": []}。
- 不要输出任何 JSON 以外的内容。"""


class LLMClient:
    """大语言模型客户端（OpenAI 兼容接口）"""

    def __init__(self):
        cfg = CONFIG.llm
        missing = []
        if not cfg.api_key:
            missing.append("LLM_API_KEY")
        if not cfg.base_url:
            missing.append("LLM_BASE_URL")
        if not cfg.model:
            missing.append("LLM_MODEL")
        if missing:
            raise ValueError(
                "未配置 LLM 连接信息：" + ", ".join(missing)
                + "。请在环境变量或 .env 文件中设置（参考 .env.example）。"
            )
        self.client = OpenAI(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout=cfg.request_timeout,
        )
        self.model = cfg.model
        self.temperature = cfg.temperature
        self.max_chars_per_chunk = cfg.max_chars_per_chunk
        self.enable_thinking = cfg.enable_thinking
        self.stream = cfg.stream
        self.force_json_format = cfg.force_json_format

    def _build_extra_body(self) -> dict:
        """
        构建 qwen 专用的 extra_body 参数：
        - chat_template_kwargs.enable_thinking：控制思考模式
        """
        extra = {}
        if self.enable_thinking:
            extra["chat_template_kwargs"] = {"enable_thinking": True}
        return extra

    def _call_llm(self, text: str) -> dict:
        """单次调用 LLM，返回解析后的 JSON 字典（含指数退避重试）"""
        user_prompt = (
            f"请对以下文本进行脱敏分析，识别所有敏感信息并给出替换方案。\n\n"
            f"【待脱敏文本】\n{text}\n\n"
            f"请严格按指定 JSON 格式输出替换方案。"
        )

        # 构建请求参数
        kwargs = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": self.stream,
        }
        # 仅在需要时强制 JSON 格式（部分 qwen 部署不支持 response_format）
        if self.force_json_format:
            kwargs["response_format"] = {"type": "json_object"}
        # 注入 qwen 专用参数（enable_thinking 等）
        extra_body = self._build_extra_body()
        if extra_body:
            kwargs["extra_body"] = extra_body

        # 预声明 content，避免 except 块引用未定义变量
        content = ""
        last_exc = None
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                if self.stream:
                    content = self._collect_stream(response)
                else:
                    content = response.choices[0].message.content or "{}"
                return self._safe_parse_json(content)
            except json.JSONDecodeError as e:
                logger.error("LLM 返回 JSON 解析失败 (尝试 %d/%d): %s", attempt, max_retries, e)
                last_exc = e
                # JSON 解析失败不重试，直接走兜底
                return self._extract_json_fallback(content)
            except Exception as e:
                last_exc = e
                if attempt < max_retries:
                    wait = 2 ** (attempt - 1)  # 1s, 2s, 4s
                    logger.warning(
                        "LLM 调用失败 (尝试 %d/%d)，%ds 后重试: %s",
                        attempt, max_retries, wait, e
                    )
                    import time
                    time.sleep(wait)
                else:
                    logger.error("LLM 调用失败（已重试 %d 次）: %s", max_retries, e)
        raise last_exc

    @staticmethod
    def _collect_stream(response) -> str:
        """收集流式响应的完整内容"""
        chunks: List[str] = []
        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                chunks.append(delta.content)
        return "".join(chunks)

    @staticmethod
    def _safe_parse_json(content: str) -> dict:
        """安全解析 JSON，失败时走兜底提取"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return LLMClient._extract_json_fallback(content)

    @staticmethod
    def _extract_json_fallback(text: str) -> dict:
        """JSON 解析失败时的兜底提取"""
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"replacements": []}

    def desensitize_text(self, text: str) -> List[Replacement]:
        """
        对一段文本进行脱敏分析，返回替换方案列表。
        长文本会自动分块处理。
        """
        if not text or not text.strip():
            return []

        # 分块处理
        chunks = self._split_text(text, self.max_chars_per_chunk)
        all_replacements: List[Replacement] = []

        # 用于跨块保持实体一致性：记录 original -> replacement 映射
        consistency_map: dict = {}

        for idx, chunk in enumerate(chunks, 1):
            logger.info("正在处理文本块 %d/%d（%d 字符）", idx, len(chunks), len(chunk))
            # 在 prompt 中注入已确定的替换映射，保持一致性
            enriched_chunk = self._inject_consistency(chunk, consistency_map)
            result = self._call_llm(enriched_chunk)

            for item in result.get("replacements", []):
                original = item.get("original", "").strip()
                replacement = item.get("replacement", "").strip()
                if not original:
                    continue
                # 若该 original 已有统一替换值，则沿用
                if original in consistency_map:
                    replacement = consistency_map[original]
                else:
                    consistency_map[original] = replacement

                all_replacements.append(
                    Replacement(
                        original=original,
                        replacement=replacement,
                        entity_type=item.get("entity_type", "未知"),
                        action=item.get("action", "replace"),
                        reason=item.get("reason", ""),
                        sensitivity=item.get("sensitivity", ""),
                    )
                )

        # 去重（同一 original 可能跨块出现）
        seen = set()
        unique: List[Replacement] = []
        for r in all_replacements:
            if r.original in seen:
                continue
            seen.add(r.original)
            unique.append(r)
        return unique

    @staticmethod
    def _split_text(text: str, max_chars: int) -> List[str]:
        """按段落/长度切分文本，尽量在段落边界切分"""
        if len(text) <= max_chars:
            return [text]

        chunks: List[str] = []
        # 优先按换行切分
        paragraphs = text.split("\n")
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 1 > max_chars:
                if current:
                    chunks.append(current)
                # 单段超长则硬切
                while len(para) > max_chars:
                    chunks.append(para[:max_chars])
                    para = para[max_chars:]
                current = para
            else:
                current = current + "\n" + para if current else para
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _inject_consistency(chunk: str, consistency_map: dict) -> str:
        """将已确定的替换映射注入文本块，提示模型保持一致性"""
        if not consistency_map:
            return chunk
        mapping_str = "\n".join(
            f"- 「{k}」→「{v}」" for k, v in consistency_map.items()
        )
        hint = (
            f"【一致性提示】以下替换关系已在文档前文确定，请保持一致：\n{mapping_str}\n\n"
        )
        return hint + chunk
