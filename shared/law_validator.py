"""
法条自动校验引擎

功能：
1. 从 LLM 回复中自动提取法条引用（支持多种格式）
2. 批量到国家法律法规数据库校验时效性
3. 关联性分析（法与法的关系、法与场景的关系）
4. 修正建议生成（发现错误/冲突时）

完整校验流程：
    提取引用 → 名称解析 → 批量查询 → 时效判断 → 关联分析 → 生成报告
"""

import re
import asyncio
import sys
import os
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(__file__))
from law_search import law_search_tool, FLKApiClient, LawSearchResult


_chinese_num_map = {
    '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
    '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
    '零': '0', '百': '100', '千': '1000', '万': '10000',
}

_cn_char_to_arabic = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
    '十': 10, '百': 100, '千': 1000,
}

LAW_NAME_ALIASES = {
    '中华人民共和国民法典': ['民法典', '民法'],
    '中华人民共和国刑法': ['刑法'],
    '中华人民共和国公司法': ['公司法'],
    '中华人民共和国劳动法': ['劳动法'],
    '中华人民共和国劳动合同法': ['劳动合同法', '劳动法'],
    '中华人民共和国合同法': ['合同法'],
    '中华人民共和国婚姻法': ['婚姻法'],
    '中华人民共和国继承法': ['继承法'],
    '中华人民共和国物权法': ['物权法'],
    '中华人民共和国侵权责任法': ['侵权责任法', '民法典侵权责任编'],
    '中华人民共和国担保法': ['担保法'],
    '中华人民共和国反垄断法': ['反垄断法'],
    '中华人民共和国反不正当竞争法': ['反不正当竞争法'],
    '中华人民共和国消费者权益保护法': ['消费者权益保护法', '消法'],
    '中华人民共和国证券法': ['证券法'],
    '中华人民共和国保险法': ['保险法'],
    '中华人民共和国票据法': ['票据法'],
    '中华人民共和国企业破产法': ['企业破产法', '破产法'],
    '中华人民共和国仲裁法': ['仲裁法'],
    '中华人民共和国律师法': ['律师法'],
    '中华人民共和国民事诉讼法': ['民事诉讼法', '民诉法'],
    '中华人民共和国刑事诉讼法': ['刑事诉讼法', '刑诉法'],
    '中华人民共和国行政诉讼法': ['行政诉讼法', '行诉法'],
    '中华人民共和国行政复议法': ['行政复议法'],
    '中华人民共和国行政处罚法': ['行政处罚法'],
    '中华人民共和国行政许可法': ['行政许可法'],
    '中华人民共和国行政强制法': ['行政强制法'],
    '中华人民共和国治安管理处罚法': ['治安管理处罚法'],
    '中华人民共和国国家安全法': ['国家安全法'],
    '中华人民共和国网络安全法': ['网络安全法'],
    '中华人民共和国数据安全法': ['数据安全法'],
    '中华人民共和国个人信息保护法': ['个人信息保护法'],
    '中华人民共和国环境保护法': ['环境保护法'],
    '中华人民共和国土地管理法': ['土地管理法'],
    '中华人民共和国城市房地产管理法': ['城市房地产管理法'],
    '中华人民共和国建筑法': ['建筑法'],
    '中华人民共和国招标投标法': ['招标投标法', '招投标法'],
    '中华人民共和国政府采购法': ['政府采购法'],
    '中华人民共和国产品质量法': ['产品质量法'],
    '中华人民共和国安全生产法': ['安全生产法'],
    '中华人民共和国食品安全法': ['食品安全法'],
    '中华人民共和国药品管理法': ['药品管理法'],
    '中华人民共和国传染病防治法': ['传染病防治法'],
    '中华人民共和国消防法': ['消防法'],
    '中华人民共和国宪法': ['宪法'],
    '中华人民共和国立法法': ['立法法'],
    '中华人民共和国外商投资法': ['外商投资法'],
    '中华人民共和国出口管制法': ['出口管制法'],
    '中华人民共和国知识产权法': ['知识产权法'],
    '中华人民共和国著作权法': ['著作权法'],
    '中华人民共和国商标法': ['商标法'],
    '中华人民共和国专利法': ['专利法'],
}

FULL_NAME_TO_SHORT = {}
for _full, _aliases in LAW_NAME_ALIASES.items():
    for _a in _aliases:
        FULL_NAME_TO_SHORT[_a] = _full

LAW_FULL_NAMES = list(LAW_NAME_ALIASES.keys())

LAW_CONTEXT_RULES = {
    '合同': ['中华人民共和国合同法', '中华人民共和国民法典', '中华人民共和国招标投标法',
             '中华人民共和国政府采购法', '中华人民共和国担保法'],
    '劳动': ['中华人民共和国劳动法', '中华人民共和国劳动合同法', '中华人民共和国安全生产法'],
    '公司治理': ['中华人民共和国公司法', '中华人民共和国证券法', '中华人民共和国企业破产法'],
    '知识产权': ['中华人民共和国著作权法', '中华人民共和国商标法', '中华人民共和国专利法'],
    '刑事': ['中华人民共和国刑法', '中华人民共和国刑事诉讼法'],
    '行政': ['中华人民共和国行政处罚法', '中华人民共和国行政许可法', '中华人民共和国行政复议法'],
    '招投标': ['中华人民共和国招标投标法', '中华人民共和国政府采购法'],
    '数据': ['中华人民共和国网络安全法', '中华人民共和国数据安全法', '中华人民共和国个人信息保护法'],
    '采购': ['中华人民共和国政府采购法', '中华人民共和国招标投标法', '中华人民共和国产品质量法'],
    '制度': ['中华人民共和国公司法', '中华人民共和国立法法', '中华人民共和国行政许可法'],
}


@dataclass
class LawReference:
    """从文本中提取的法条引用"""
    raw_text: str
    law_name: Optional[str] = None
    full_law_name: Optional[str] = None
    article_num: Optional[str] = None
    paragraph: Optional[str] = None
    context_keywords: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """单条法条校验结果"""
    reference: LawReference
    status: str = "unknown"
    db_law_name: str = ""
    db_article: str = ""
    detail_url: str = ""
    is_valid: bool = False
    db_status_text: str = ""
    published_date: str = ""
    effective_date: str = ""
    correction: str = ""
    relevance: str = ""


def _chinese_to_arabic(cn: str) -> str:
    """中文数字转阿拉伯数字"""
    cn = cn.replace('第', '').replace('条', '')
    if cn.isdigit():
        return cn
    result = 0
    unit = 1
    for i in range(len(cn) - 1, -1, -1):
        char = cn[i]
        if char not in _cn_char_to_arabic:
            return cn
        num = _cn_char_to_arabic[char]
        if num >= 10:
            if num > unit:
                unit = num
            else:
                result += unit
                unit = num
        else:
            result += num * unit
    return str(result)


def extract_law_references(text: str) -> List[LawReference]:
    """
    从文本中提取所有法条引用（重写版，提高准确率）

    支持格式：
    - 《中华人民共和国民法典》第143条
    - 民法典第143条
    - 《民法典》第一百四十三条
    - 根据《公司法》第XX条规定
    """
    references = []
    
    # 核心匹配模式：法律名 + 第X条
    # 优先匹配带书名号的格式
    primary_patterns = [
        # 《完整法律名》第X条（包含"法"或不包含"法"）
        r'《([^》]{2,30})》\s*第([一二三四五六七八九十百千\d]+)条',
        # 无书名号：法律名第X条
        r'([^《\s]{2,25}法)\s*第([一二三四五六七八九十百千\d]+)条',
    ]
    
    for pattern in primary_patterns:
        for match in re.finditer(pattern, text):
            law_name_raw = match.group(1).strip()
            article_cn = match.group(2)
            
            # 清理法律名称
            law_name_clean = law_name_raw.replace('《', '').replace('》', '').strip()
            
            # 解析完整法律名称
            full_name = _resolve_law_name(law_name_clean)
            if not full_name:
                # 尝试通过别名反向查找
                for full, aliases in LAW_NAME_ALIASES.items():
                    if law_name_clean in full or any(law_name_clean in alias for alias in aliases):
                        full_name = full
                        break
                if not full_name:
                    # 如果仍然无法解析，跳过
                    continue
            
            # 转换条款号为阿拉伯数字
            article_num = _chinese_to_arabic(article_cn)
            
            # 验证条款号是否为有效数字
            if not article_num.isdigit():
                continue
            
            # 创建引用对象
            ref = LawReference(
                raw_text=match.group(0),
                law_name=law_name_clean,
                full_law_name=full_name,
                article_num=article_num
            )
            references.append(ref)
    
    # 处理"第X条和第Y条"的格式
    multi_pattern = r'([^《\s]{2,20}法)\s*第([一二三四五六七八九十百千\d]+)条\s*(?:和|与|及|、)\s*第([一二三四五六七八九十百千\d]+)条'
    for match in re.finditer(multi_pattern, text):
        law_name_clean = match.group(1).strip()
        full_name = _resolve_law_name(law_name_clean)
        
        if not full_name:
            continue
        
        for article_cn in [match.group(2), match.group(3)]:
            article_num = _chinese_to_arabic(article_cn)
            if article_num.isdigit():
                ref = LawReference(
                    raw_text=match.group(0),
                    law_name=law_name_clean,
                    full_law_name=full_name,
                    article_num=article_num
                )
                references.append(ref)
    
    # 提取上下文关键词并去重
    for ref in references:
        ref.context_keywords = _extract_context(text, ref)
    
    return _dedupe_references(references)


def _extract_context(text: str, ref: LawReference) -> List[str]:
    """提取法条引用周围的上下文关键词"""
    idx = text.find(ref.raw_text)
    if idx < 0:
        return []

    start = max(0, idx - 100)
    end = min(len(text), idx + len(ref.raw_text) + 100)
    surrounding = text[start:end]

    keywords = []
    context_map = {
        '合同': '合同审查', '劳动': '劳动用工', '公司': '公司治理',
        '知识产权': '知识产权', '刑事': '刑事合规', '行政': '行政管理',
        '招投标': '招投标', '数据': '数据合规', '采购': '采购管理',
        '安全': '安全生产', '制度': '制度审查', '合规': '合规管理',
        '章程': '公司治理', '投资': '投资管理', '融资': '融资管理',
    }

    for kw, ctx in context_map.items():
        if kw in surrounding:
            keywords.append(ctx)

    return keywords if keywords else ['一般法律咨询']


def _clean_law_name(law_name: str) -> str:
    """清理法律名称中的特殊字符"""
    if law_name is None:
        return None
    # 去除书名号
    law_name = law_name.replace('《', '').replace('》', '')
    # 去除多余空格
    law_name = law_name.strip()
    return law_name


def _dedupe_references(references: List[LawReference]) -> List[LawReference]:
    """去重并清理名称"""
    seen = set()
    result = []
    for r in references:
        # 清理名称
        r.law_name = _clean_law_name(r.law_name)
        r.full_law_name = _clean_law_name(r.full_law_name)
        
        key = (r.full_law_name, r.article_num, r.paragraph)
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result


def _extract_law_keyword(full_name: str) -> str:
    """提取法律名称的核心关键词，去除'中华人民共和国'等前缀"""
    prefix = "中华人民共和国"
    if full_name.startswith(prefix):
        return full_name[len(prefix):]
    return full_name


def _resolve_law_name(law_name: str) -> Optional[str]:
    """将缩写/别名解析为完整法律名称"""
    if law_name in FULL_NAME_TO_SHORT:
        return FULL_NAME_TO_SHORT[law_name]
    for full_name in LAW_FULL_NAMES:
        if law_name in full_name or full_name.endswith(law_name):
            return full_name
    return None


def _analyze_context_relevance(ref: LawReference, user_query: str = "") -> str:
    """分析法条与审查场景的关联性"""
    if not ref.context_keywords:
        return "一般引用"

    relevance_map = {
        '合同审查': ['合同', '违约', '履行', '解除', '无效', '撤销', '担保'],
        '劳动用工': ['劳动', '用工', '工资', '解除', '补偿', '社保', '工伤'],
        '公司治理': ['公司', '股东', '董事', '章程', '决议', '出资', '清算'],
        '知识产权': ['知识', '专利', '商标', '著作', '侵权', '许可'],
        '招投标': ['招标', '投标', '中标', '评标', '采购'],
        '数据合规': ['数据', '信息', '隐私', '安全', '跨境'],
        '安全生产': ['安全', '事故', '消防', '应急', '生产'],
    }

    matched = []
    for ctx in ref.context_keywords:
        for scene, indicators in relevance_map.items():
            if ctx == scene:
                matched.append(scene)
                break
            if any(ind in (ref.law_name or '') for ind in indicators):
                matched.append(scene)
                break

    if matched:
        return f"与{matched[0]}场景高度相关"
    return "需进一步确认关联性"


async def _validate_single(ref: LawReference) -> ValidationResult:
    """校验单条法条引用"""
    result = ValidationResult(reference=ref)
    result.relevance = _analyze_context_relevance(ref)

    if not ref.full_law_name:
        result.status = "resolved"
        result.correction = f"无法识别法律名称'{ref.law_name}'，请使用完整法律名称"
        return result

    try:
        # 搜索策略：始终只搜索法律名称，不搜索条款号
        # 原因：flk.npc.gov.cn 的搜索API对带条款号的关键词返回不准的结果
        search_query = ref.full_law_name

        law_results, _ = law_search_tool.flk_client.search_laws(
            keyword=search_query, 
            search_type=1,  # 标题精确搜索
            page_size=10
        )

        if not law_results:
            result.status = "not_found"
            result.correction = (
                f"在国家法律法规数据库中未找到'{ref.full_law_name}'"
                f"{'第' + ref.article_num + '条' if ref.article_num else ''}。"
                f"请核实法律名称和条款号是否正确。"
            )
            return result

        # 智能匹配：遍历所有结果找最佳匹配
        best = None
        best_score = -1
        full_name = ref.full_law_name
        
        for law in law_results:
            title = law.title
            score = 0
            
            # 1. 标题完全等于法律名（最高优先级）
            if title == full_name:
                score += 300  # 完全匹配，最高分
            
            # 2. 标题以法律名开头（如"中华人民共和国民法典(2021年施行)"）
            elif title.startswith(full_name):
                score += 250
            
            # 3. 法律名完全包含标题（标题是简称）
            elif full_name.startswith(title) and title.endswith('法'):
                score += 200
            
            # 4. 标题包含完整法律名
            elif full_name in title:
                score += 150
            
            # 5. 有效性加权
            if law.sxx == 3:  # 有效
                score += 50
            elif law.sxx == 1:  # 已废止
                score -= 100  # 大幅降权
            elif law.sxx == 2:  # 已修改
                score -= 30
            
            if score > best_score:
                best_score = score
                best = law
        
        # 得分阈值：低于100分认为没有匹配
        if best is None or best_score < 100:
            result.status = "not_found"
            result.correction = (
                f"在国家法律法规数据库中未找到'{ref.full_law_name}'的匹配结果。"
                f"搜索到 {len(law_results)} 条结果但均不匹配，请核实法律名称是否正确。"
            )
            return result
        
        result.db_law_name = best.title
        result.detail_url = best.detail_url
        result.published_date = best.gbrq
        result.effective_date = best.sxrq
        result.db_status_text = best.status_text
        result.is_valid = best.is_valid

        name_match = best_score >= 50

        if best.sxx == 1:
            result.status = "deprecated"
            result.correction = (
                f"'{best.title}'已被废止（公布日期: {best.gbrq}）。"
                f"请勿引用已废止的法律，建议查阅现行有效版本或替代法律。"
            )
        elif best.sxx == 2:
            result.status = "modified"
            result.correction = (
                f"'{best.title}'已被修改（公布日期: {best.gbrq}，施行日期: {best.sxrq}）。"
                f"请确认所引用条款是否为最新版本。建议访问 {best.detail_url} 查看现行有效条文。"
            )
        elif best.sxx == 4:
            result.status = "not_effective"
            result.correction = (
                f"'{best.title}'尚未生效（施行日期: {best.sxrq}）。"
                f"当前不可引用此法律作为法律依据。"
            )
        elif not name_match:
            result.status = "name_mismatch"
            result.correction = (
                f"数据库中找到的法律名称为'{best.title}'，与引用的'{ref.full_law_name}'不一致。"
                f"请确认引用正确的法律名称。"
            )
        else:
            result.status = "valid"
            if ref.article_num:
                result.correction = (
                    f"'{best.title}'现行有效。"
                    f"请访问 {best.detail_url} 确认第{ref.article_num}条完整原文。"
                )
            else:
                result.correction = f"'{best.title}'现行有效。"

    except Exception as e:
        result.status = "error"
        result.correction = f"校验请求失败: {str(e)}"

    return result


async def validate_law_references(
    references: List[LawReference],
    user_query: str = ""
) -> List[ValidationResult]:
    """批量校验法条引用"""
    if not references:
        return []

    tasks = [_validate_single(ref) for ref in references]
    results = await asyncio.gather(*tasks)

    for r in results:
        if not r.relevance or r.relevance == "一般引用":
            r.relevance = _analyze_context_relevance(r.reference, user_query)

    return results


def generate_validation_report(
    results: List[ValidationResult],
    response_text: str = ""
) -> Dict:
    """生成结构化校验报告"""
    if not results:
        return None

    valid_count = sum(1 for r in results if r.status == "valid")
    deprecated_count = sum(1 for r in results if r.status == "deprecated")
    modified_count = sum(1 for r in results if r.status == "modified")
    not_found_count = sum(1 for r in results if r.status == "not_found")
    other_count = len(results) - valid_count - deprecated_count - modified_count - not_found_count

    items = []
    for r in results:
        items.append({
            "reference": r.reference.raw_text,
            "law_name": r.reference.full_law_name or r.reference.law_name,
            "article": r.reference.article_num,
            "status": r.status,
            "status_label": _status_label(r.status),
            "db_law_name": r.db_law_name,
            "is_valid": r.is_valid,
            "db_status": r.db_status_text,
            "published_date": r.published_date,
            "effective_date": r.effective_date,
            "detail_url": r.detail_url,
            "relevance": r.relevance,
            "correction": r.correction,
        })

    has_issues = deprecated_count > 0 or modified_count > 0 or not_found_count > 0 or other_count > 0

    summary = []
    if valid_count > 0:
        summary.append(f"✅ {valid_count} 条引用校验通过")
    if deprecated_count > 0:
        summary.append(f"❌ {deprecated_count} 条已废止")
    if modified_count > 0:
        summary.append(f"⚠️ {modified_count} 条已被修改")
    if not_found_count > 0:
        summary.append(f"❓ {not_found_count} 条未找到")
    if other_count > 0:
        summary.append(f"⚠️ {other_count} 条存在其他问题")

    return {
        "total": len(results),
        "valid": valid_count,
        "deprecated": deprecated_count,
        "modified": modified_count,
        "not_found": not_found_count,
        "has_issues": has_issues,
        "summary": "；".join(summary),
        "source": "国家法律法规数据库 (flk.npc.gov.cn)",
        "items": items,
    }


def _status_label(status: str) -> str:
    """状态标签"""
    labels = {
        "valid": "✅ 有效",
        "deprecated": "❌ 已废止",
        "modified": "⚠️ 已修改",
        "not_found": "❓ 未找到",
        "not_effective": "🕐 尚未生效",
        "name_mismatch": "⚠️ 名称不匹配",
        "resolved": "⚠️ 无法识别",
        "error": "❌ 校验失败",
    }
    return labels.get(status, "❓ 未知")


def generate_correction_markdown(report: Optional[Dict]) -> str:
    """生成可嵌入回复的修正建议 Markdown 文本"""
    if not report or report["total"] == 0:
        return ""

    lines = ["\n\n---\n", "### ⚖️ 法条自动校验报告\n"]
    lines.append(f"> 数据来源：{report['source']}\n")
    lines.append(f"> 校验结果：{report['summary']}\n")

    if report["has_issues"]:
        lines.append("#### 需要关注的问题：\n")

    for item in report["items"]:
        ref_label = item["reference"]
        status_icon = item["status_label"].split(" ")[0]

        if item["status"] == "valid":
            if item["article"]:
                lines.append(
                    f"- {status_icon} **{item['law_name']}** 第{item['article']}条："
                    f"现行有效 | {item.get('relevance', '')}"
                )
            else:
                lines.append(
                    f"- {status_icon} **{item['law_name']}**："
                    f"现行有效 | {item.get('relevance', '')}"
                )
        elif item["status"] == "deprecated":
            lines.append(f"- ❌ **{item['reference']}**：{item['correction']}")
        elif item["status"] == "modified":
            lines.append(f"- ⚠️ **{item['reference']}**：{item['correction']}")
        else:
            lines.append(f"- ⚠️ **{item['reference']}**：{item['correction']}")

    if report["deprecated"] > 0 or report["modified"] > 0:
        lines.append("\n**🔧 修正建议：**")
        for item in report["items"]:
            if item["status"] in ("deprecated", "modified"):
                lines.append(
                    f"- '{item['reference']}' → 请访问 [{item['detail_url']}]({item['detail_url']}) 查看最新版本"
                )
        lines.append("- 建议在法律文书和合同审查中使用现行有效法律版本")

    lines.append(f"\n*本报告由系统自动生成，仅供参考。重要法律事务请咨询专业律师。*")
    return "\n".join(lines)


def should_auto_validate(text: str, has_attachments: bool = False) -> bool:
    """判断是否应自动触发法条校验"""
    # 必须包含明确引用法条的迹象才触发
    has_article_ref = bool(re.search(r'第[一二三四五六七八九十百千\d]+条', text))
    has_law_name = bool(re.search(r'《([^》]{2,20}法[^》]*)》|([^《\s]{2,10}法)\s*第', text))
    
    if has_attachments:
        # 附件场景：需要有明确的法条引用才校验
        return has_article_ref and has_law_name
    
    if has_article_ref and has_law_name:
        return True
    
    # 检查是否包含具体法律名称+条文的组合
    law_article_pattern = r'(?:民法典|刑法|公司法|劳动法|劳动合同法|合同法|公司法|行政诉讼法|民事诉讼法|刑事诉讼法|专利法|商标法|著作权法)(?:.*?)第.*?条'
    if re.search(law_article_pattern, text):
        return True
    
    return False


validator = None


def get_validator():
    """获取全局校验器实例"""
    global validator
    if validator is None:
        validator = True
    return validator