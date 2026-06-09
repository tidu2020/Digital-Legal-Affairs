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
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
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

HIERARCHY_LEVELS = {
    1: "法律",
    2: "行政法规",
    3: "地方性法规",
    4: "部门规章",
    5: "司法解释",
}

HIERARCHY_KEYWORDS = {
    1: ["法"],
    2: ["条例"],
    3: ["地方性法规", "省", "自治区", "直辖市", "设区的市"],
    4: ["办法", "规定", "细则"],
    5: ["司法解释", "批复", "解答"],
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
class LawVerificationDetail:
    """法条真实性核验详情"""
    article: str = ""          # 法条编号
    original_content: str = "" # 原引用的法条内容
    status: str = ""           # 核验状态: ✅已验证/⚠️存疑/❌错误
    reason: str = ""           # 核验详细说明
    correct_article: str = ""  # 修正后的法条编号（如无错误则为空）
    correct_content: str = ""  # 修正后的法条内容（如无错误则为空）
    is_effective: bool = True  # 是否现行有效
    remarks: str = ""          # 备注说明


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
    从文本中提取所有法条引用

    支持格式：
    - 《中华人民共和国民法典》第143条
    - 民法典第143条
    - 《民法典》第一百四十三条
    - 根据《公司法》第XX条规定
    - 第X条（结合上下文推断法律名）
    """
    references = []

    for full_name, aliases in LAW_NAME_ALIASES.items():
        short_name = aliases[0]
        alias_patterns = [re.escape(a) for a in aliases]

        for alias_pat in alias_patterns:
            patterns = [
                rf'《?{alias_pat}》?\s*第([一二三四五六七八九十百千\d]+)条(?:\s*之?\s*([一二三四五六七八九十百千\d]+)\s*[款项])?',
                rf'《?{alias_pat}》?\s*第([一二三四五六七八九十百千\d]+)条',
            ]

            for pat in patterns:
                for m in re.finditer(pat, text):
                    article_cn = m.group(1)
                    article_arabic = _chinese_to_arabic(article_cn)
                    paragraph = m.group(2) if m.lastindex and m.lastindex >= 2 else None

                    skip_this = False
                    if m.start() > 0:
                        alias_pos_in_match = m.group(0).find(alias_pat)
                        if alias_pos_in_match >= 0:
                            law_name_start = m.start() + alias_pos_in_match
                            law_name_end = law_name_start + len(alias_pat)
                            for check_len in range(1, 6):
                                candidate = text[law_name_start - check_len:law_name_end]
                                for fl_name, fl_aliases in LAW_NAME_ALIASES.items():
                                    if candidate in fl_aliases or candidate == fl_name:
                                        skip_this = True
                                        break
                                if skip_this:
                                    break
                    if skip_this:
                        continue

                    ref = LawReference(
                        raw_text=m.group(0),
                        law_name=short_name,
                        full_law_name=full_name,
                        article_num=article_arabic,
                        paragraph=_chinese_to_arabic(paragraph) if paragraph else None
                    )

                    if ref not in references:
                        references.append(ref)

    generic_patterns = [
        r'《([^》]+)》\s*第([一二三四五六七八九十百千\d]+)条',
        r'([^《\s]{2,10}法)\s*第([一二三四五六七八九十百千\d]+)条',
    ]

    for pat in generic_patterns:
        for m in re.finditer(pat, text):
            law_name_raw = m.group(1).strip()
            article_cn = m.group(2)
            article_arabic = _chinese_to_arabic(article_cn)

            prefix_char = text[m.start() - 1] if m.start() > 0 else ''
            if prefix_char and (prefix_char.isalpha() or prefix_char in '动'):
                continue

            resolved_full = None
            for full, aliases in LAW_NAME_ALIASES.items():
                if law_name_raw in aliases or law_name_raw == full:
                    resolved_full = full
                    break

            if not resolved_full and '法' in law_name_raw:
                found_longer = False
                for fl_name in LAW_FULL_NAMES:
                    if fl_name != law_name_raw and fl_name.endswith(law_name_raw) and len(fl_name) > len(law_name_raw):
                        before_pos = m.start() - (len(fl_name) - len(law_name_raw))
                        if before_pos >= 0:
                            possible_full = text[before_pos:m.end()]
                            if fl_name in possible_full or any(a in possible_full for a in LAW_NAME_ALIASES.get(fl_name, [])):
                                found_longer = True
                                break
                if not found_longer:
                    for full in LAW_FULL_NAMES:
                        if law_name_raw in full or full.endswith(law_name_raw):
                            resolved_full = full
                            break

            ref = LawReference(
                raw_text=m.group(0),
                law_name=law_name_raw,
                full_law_name=resolved_full,
                article_num=article_arabic
            )

            if ref not in references:
                references.append(ref)

    context_law_patterns = [
        r'(?:根据|依据|按照)\s*《?([^，。；》\s]{2,15}法)》?\s*(?:的?\s*规定|之规定)?',
        r'《([^》]{2,15}法)》',
    ]

    for pat in context_law_patterns:
        for m in re.finditer(pat, text):
            law_name_raw = m.group(1).strip()

            already_has = any(
                r.law_name and law_name_raw in r.law_name
                for r in references if r.law_name
            )
            if already_has:
                continue

            resolved_full = None
            for full, aliases in LAW_NAME_ALIASES.items():
                if law_name_raw in aliases or law_name_raw == full:
                    resolved_full = full
                    break

            if resolved_full:
                ref = LawReference(
                    raw_text=m.group(0),
                    law_name=law_name_raw,
                    full_law_name=resolved_full
                )

                if ref not in references:
                    references.append(ref)

    multi_article_patterns = [
        r'《?([^》]{2,20}法?)》?\s*第([一二三四五六七八九十百千\d]+)条\s*(?:和|与|及|、)\s*第([一二三四五六七八九十百千\d]+)条',
        r'《?([^》]{2,20}法?)》?\s*第([一二三四五六七八九十百千\d]+)条\s*(?:和|与|及|、)\s*([一二三四五六七八九十百千\d]+)条',
    ]

    for pat in multi_article_patterns:
        for m in re.finditer(pat, text):
            law_name_raw = m.group(1).strip()
            for group_idx in [2, 3]:
                article_cn = m.group(group_idx)
                if not article_cn:
                    continue
                article_arabic = _chinese_to_arabic(article_cn)

                resolved_full = None
                for full, aliases in LAW_NAME_ALIASES.items():
                    if law_name_raw in aliases or law_name_raw == full or full.endswith(law_name_raw):
                        resolved_full = full
                        break

                if not resolved_full:
                    resolved_full = _resolve_law_name(law_name_raw)
                if not resolved_full:
                    continue

                ref = LawReference(
                    raw_text=m.group(0),
                    law_name=law_name_raw,
                    full_law_name=resolved_full or law_name_raw if '法' in law_name_raw else None,
                    article_num=article_arabic
                )

                if ref not in references:
                    references.append(ref)

    for ref in list(references):
        if not ref.article_num or not ref.full_law_name:
            continue
        idx = text.find(ref.raw_text)
        if idx < 0:
            continue
        nearby_start = max(0, idx - 20)
        nearby_end = min(len(text), idx + len(ref.raw_text) + 50)
        nearby = text[nearby_start:nearby_end]
        extra_pattern = r'第([一二三四五六七八九十百千\d]+)条'
        seen_nums = {ref.article_num}
        for em in re.finditer(extra_pattern, nearby):
            if em.group(0) not in nearby:
                continue
            extra_article = _chinese_to_arabic(em.group(1))
            if extra_article not in seen_nums:
                seen_nums.add(extra_article)
                extra_ref = LawReference(
                    raw_text=em.group(0),
                    law_name=ref.law_name,
                    full_law_name=ref.full_law_name,
                    article_num=extra_article
                )
                if extra_ref not in references:
                    references.append(extra_ref)

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


def _dedupe_references(references: List[LawReference]) -> List[LawReference]:
    """去重"""
    seen = set()
    result = []
    for r in references:
        key = (r.full_law_name, r.article_num, r.paragraph)
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result


def _resolve_law_name(law_name: str) -> Optional[str]:
    """将缩写/别名解析为完整法律名称"""
    if law_name in FULL_NAME_TO_SHORT:
        return FULL_NAME_TO_SHORT[law_name]
    for full_name in LAW_FULL_NAMES:
        if law_name in full_name or full_name.endswith(law_name):
            return full_name
    return None


def _determine_hierarchy_level(law_name: str) -> tuple:
    """根据法律名称判断层级

    Returns:
        (level_number, level_label) 例如 (1, "法律"), (4, "部门规章")
    """
    if not law_name:
        return (0, "未知")

    # 从高序号向低序号检查，避免"办法"中的"法"被误判为法律
    for level in sorted(HIERARCHY_KEYWORDS.keys(), reverse=True):
        keywords = HIERARCHY_KEYWORDS[level]
        for kw in keywords:
            if kw in law_name:
                return (level, HIERARCHY_LEVELS[level])

    return (0, "未知")


def _check_hierarchy_conflict(refs: List[LawReference]) -> List[Dict]:
    """检查不同层级法律之间的潜在冲突（纵向冲突）

    Returns:
        冲突项列表，每项包含 conflict_type, description, recommendation
    """
    if len(refs) < 2:
        return []

    conflicts = []
    refs_with_level = []
    for ref in refs:
        if ref.full_law_name:
            level_num, level_label = _determine_hierarchy_level(ref.full_law_name)
            refs_with_level.append((ref, level_num, level_label))

    valid_refs = [(r, ln, ll) for r, ln, ll in refs_with_level if ln > 0]
    if len(valid_refs) < 2:
        return conflicts

    valid_refs.sort(key=lambda x: x[1])

    for i in range(len(valid_refs)):
        for j in range(i + 1, len(valid_refs)):
            ri, lni, lli = valid_refs[i]
            rj, lnj, llj = valid_refs[j]
            if lnj > lni:
                conflicts.append({
                    "conflict_type": "vertical",
                    "laws": [
                        {"name": ri.full_law_name or ri.law_name, "level": lni, "level_label": lli},
                        {"name": rj.full_law_name or rj.law_name, "level": lnj, "level_label": llj},
                    ],
                    "description": f"'{lli}'（{ri.full_law_name or ri.law_name}）与 '{llj}'（{rj.full_law_name or rj.law_name}）处于不同层级",
                    "recommendation": f"上位法优先：应优先适用效力层级更高的 '{lli}'。下位法不得与上位法相抵触。"
                })

    return conflicts


def _check_same_level_conflict(refs: List[LawReference]) -> List[Dict]:
    """检查同一层级法律之间的潜在冲突（横向冲突）

    Returns:
        冲突项列表，每项包含 conflict_type, description, recommendation
    """
    if len(refs) < 2:
        return []

    conflicts = []
    by_level = {}

    for ref in refs:
        if ref.full_law_name:
            level_num, level_label = _determine_hierarchy_level(ref.full_law_name)
            if level_num > 0:
                if level_num not in by_level:
                    by_level[level_num] = []
                by_level[level_num].append((ref, level_label))

    for level_num, items in by_level.items():
        if len(items) >= 2:
            level_label = items[0][1]
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    ri, lli = items[i]
                    rj, llj = items[j]
                    law_name_i = ri.full_law_name or ri.law_name or ""
                    law_name_j = rj.full_law_name or rj.law_name or ""

                    rec = "新法优先：以最新颁布的法律为准；若存在特别法与一般法关系，则特别法优先。"
                    description = (
                        f"同属'{level_label}'层级的 '{law_name_i}' 与 '{law_name_j}' 可能对同一事项有不同规定。"
                    )
                    conflicts.append({
                        "conflict_type": "horizontal",
                        "laws": [
                            {"name": law_name_i, "level": level_num, "level_label": lli},
                            {"name": law_name_j, "level": level_num, "level_label": llj},
                        ],
                        "description": description,
                        "recommendation": rec,
                    })

    return conflicts


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
        search_query = ref.full_law_name
        if ref.article_num:
            search_query += f" 第{ref.article_num}条"

        law_results, _ = law_search_tool.flk_client.search_laws(
            keyword=search_query, page_size=3
        )

        if not law_results:
            result.status = "not_found"
            result.correction = (
                f"在国家法律法规数据库中未找到'{ref.full_law_name}'"
                f"{'第' + ref.article_num + '条' if ref.article_num else ''}。"
                f"请核实法律名称和条款号是否正确。"
            )
            return result

        best = law_results[0]
        result.db_law_name = best.title
        result.detail_url = best.detail_url
        result.published_date = best.gbrq
        result.effective_date = best.sxrq
        result.db_status_text = best.status_text
        result.is_valid = best.is_valid

        name_match = (
            ref.full_law_name in best.title
            or best.title in ref.full_law_name
            or any(alias in best.title for alias in LAW_NAME_ALIASES.get(ref.full_law_name, []))
        )

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
    response_text: str = "",
    references: List[LawReference] = None,
) -> Dict:
    """生成结构化校验报告

    Args:
        results: 校验结果列表
        response_text: 原始回复文本
        references: 法条引用列表（用于层级和冲突检查）
    """
    if not results:
        return None

    if references is None:
        references = [r.reference for r in results]

    valid_count = sum(1 for r in results if r.status == "valid")
    deprecated_count = sum(1 for r in results if r.status == "deprecated")
    modified_count = sum(1 for r in results if r.status == "modified")
    not_found_count = sum(1 for r in results if r.status == "not_found")
    other_count = len(results) - valid_count - deprecated_count - modified_count - not_found_count

    items = []
    for r in results:
        law_name = r.reference.full_law_name or r.reference.law_name or ""
        hierarchy_level, hierarchy_label = _determine_hierarchy_level(law_name)
        items.append({
            "reference": r.reference.raw_text,
            "law_name": law_name,
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
            "hierarchy_level": hierarchy_level,
            "hierarchy_label": hierarchy_label,
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

    vertical_conflicts = _check_hierarchy_conflict(references)
    horizontal_conflicts = _check_same_level_conflict(references)
    all_conflicts = vertical_conflicts + horizontal_conflicts

    report = {
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

    if all_conflicts:
        report["conflicts"] = all_conflicts
        report["has_conflicts"] = True

    return report


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
        status_icon = item["status_label"].split(" ")[0]
        hierarchy_label = item.get("hierarchy_label", "")
        hierarchy_info = f" [{hierarchy_label}]" if hierarchy_label and hierarchy_label != "未知" else ""

        if item["status"] == "valid":
            if item["article"]:
                lines.append(
                    f"- {status_icon} **{item['law_name']}**{hierarchy_info} 第{item['article']}条："
                    f"现行有效 | {item.get('relevance', '')}"
                )
            else:
                lines.append(
                    f"- {status_icon} **{item['law_name']}**{hierarchy_info}："
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

    if report.get("has_conflicts") and report.get("conflicts"):
        lines.append("\n#### ⚠️ 层级效力与冲突检查\n")
        lines.append("> 适用规则：**上位法 > 下位法**，**特别法 > 一般法**，**新法 > 旧法**\n")

        hierarchy_summary = {}
        for item in report["items"]:
            hl = item.get("hierarchy_label", "")
            if hl and hl != "未知":
                if hl not in hierarchy_summary:
                    hierarchy_summary[hl] = []
                hierarchy_summary[hl].append(item["law_name"])

        if hierarchy_summary:
            lines.append("**引用法条层级分布：**")
            for level_label in ["法律", "行政法规", "地方性法规", "部门规章", "司法解释"]:
                if level_label in hierarchy_summary:
                    laws = hierarchy_summary[level_label]
                    lines.append(f"- {level_label}：{'、'.join(laws)}")

        lines.append("\n**冲突警告：**")
        for conflict in report["conflicts"]:
            conflict_type = conflict["conflict_type"]
            type_label = "⬆ 纵向冲突（上位法 vs 下位法）" if conflict_type == "vertical" else "↔ 横向冲突（同层级法律）"
            lines.append(f"\n{type_label}")
            lines.append(f"- {conflict['description']}")
            lines.append(f"- 适用规则：{conflict['recommendation']}")

    lines.append(f"\n*本报告由系统自动生成，仅供参考。重要法律事务请咨询专业律师。*")
    return "\n".join(lines)


def should_auto_validate(text: str, has_attachments: bool = False) -> bool:
    """判断是否应自动触发法条校验"""
    triggers = [
        '合同', '审核', '审查', '合规', '法律', '法条',
        '条款', '诉讼', '仲裁', '纠纷', '违约', '侵权',
        '赔偿', '责任', '义务', '权利', '章程', '制度',
        '劳动', '用工', '解除', '终止', '无效', '撤销',
        '保密', '竞业', '知识产权', '专利', '商标',
    ]

    if has_attachments:
        return True

    trigger_count = sum(1 for t in triggers if t in text)
    if trigger_count >= 2:
        return True

    law_name_count = sum(
        1 for aliases in LAW_NAME_ALIASES.values()
        for alias in aliases if alias in text
    )
    if law_name_count > 0:
        return True

    return False


validator = None


def get_validator():
    """获取全局校验器实例"""
    global validator
    if validator is None:
        validator = True
    return validator


def generate_hierarchy_report(refs: List[LawReference]) -> str:
    """生成层级效力摘要 Markdown 报告

    Args:
        refs: 法条引用列表

    Returns:
        Markdown 格式的层级效力摘要
    """
    if not refs:
        return ""

    by_level = {}
    for ref in refs:
        law_name = ref.full_law_name or ref.law_name or ""
        level_num, level_label = _determine_hierarchy_level(law_name)
        if level_num not in by_level:
            by_level[level_num] = {"label": level_label, "laws": []}
        if law_name not in by_level[level_num]["laws"]:
            by_level[level_num]["laws"].append(law_name)

    lines = ["\n\n---\n", "### 📊 法条层级效力分析\n"]
    lines.append("> 适用优先级：**上位法 > 下位法**，**特别法 > 一般法**，**新法 > 旧法**\n")

    for level_num in sorted(by_level.keys()):
        info = by_level[level_num]
        if level_num == 0:
            lines.append(f"**⚪ 未知层级**：{'、'.join(info['laws'])}")
        else:
            prefix = "🟢" if level_num <= 2 else "🟡" if level_num <= 4 else "🟠"
            lines.append(f"{prefix} **{info['label']}（层级 {level_num}）**：{'、'.join(info['laws'])}")

    if 1 in by_level and any(k > 1 for k in by_level):
        lines.append("\n**⚠️ 纵向效力提示：**")
        higher_laws = by_level.get(1, {}).get("laws", [])
        levels_above = [by_level[k]["label"] for k in sorted(by_level) if 1 < k < 5]
        if higher_laws and levels_above:
            laws_str = "、".join(higher_laws)
            levels_str = "、".join(levels_above)
            lines.append(
                f"- 本报告中引用了法律层级的 {laws_str}，"
                f"同时引用了 {levels_str}。"
                f"下位法不得与上位法相抵触，请注意层级效力差异。"
            )

    lines.append(f"\n*本报告由系统自动生成，仅供参考。重要法律事务请咨询专业律师。*")
    return "\n".join(lines)


# ============================================================
# 法条真实性核验增强 (Task 5)
# ============================================================

LAW_ARTICLE_VERIFICATION_PROMPT = """你是一位中国法律法规核验专家，负责对合同审查中引用的每一条法条进行准确性核验。

【核验标准】
1. 法条编号核验：核实法条编号是否真实存在、编号格式是否正确（如"民法典第153条"而非"民法典153条"）
2. 法条有效性核验：核实该法条是否为现行有效版本的最新条文
3. 法条内容核验：核实引用的法条原文是否与官方公布版本一致

【核验结果标记】
- ✅已验证：法条编号正确、现行有效、内容准确
- ⚠️存疑：法条编号存疑、或无法确认是否最新（需附具体原因）
- ❌错误：法条编号错误、或已废止、或内容有实质性错误（需附正确法条信息）

【输入】
{legal_references}

【输出格式——必须输出纯JSON】
{{
  "verification_results": [
    {{
      "original_article": "原引用的法条编号",
      "original_content": "原引用的法条内容",
      "verification_status": "✅已验证/⚠️存疑/❌错误",
      "verification_detail": "核验详细说明，至少2句话",
      "corrected_article": "修正后的法条编号（如无错误则填null）",
      "corrected_content": "修正后的法条内容（如无错误则填null）",
      "is_effective": true,
      "remarks": "备注说明"
    }}
  ],
  "summary": "总体核验结论"
}}"""


def should_verify_articles(law_refs: List[LawReference], risk_levels: List[str]) -> bool:
    """判断是否需要做法条真实性核验

    Args:
        law_refs: 法条引用列表
        risk_levels: 与 law_refs 一一对应的风险等级列表，
                     如 "🔴高风险"、"🟡中风险"、"🟢低风险"

    Returns:
        True 如果存在至少一条高风险或中风险法条需要核验
    """
    if not law_refs or not risk_levels:
        return False

    for ref, risk in zip(law_refs, risk_levels):
        if ref.article_num and ("🔴" in risk or "🟡" in risk):
            return True

    return False


async def verify_law_articles(law_refs: List[LawReference]) -> List[LawVerificationDetail]:
    """使用 LLM 逐条核验法条引用的真实性

    Args:
        law_refs: 待核验的法条引用列表

    Returns:
        LawVerificationDetail 列表，每条对应一个法条引用
    """
    if not law_refs:
        return []

    # 只核验有法条编号的引用
    refs_to_verify = [r for r in law_refs if r.article_num]
    if not refs_to_verify:
        return []

    # 构建 LLM 输入：将法条引用格式化为结构化文本
    refs_text_parts = []
    for i, ref in enumerate(refs_to_verify, 1):
        law_name = ref.full_law_name or ref.law_name or "未知法律"
        article = ref.article_num or ""
        refs_text_parts.append(
            f"{i}. 法律名称：{law_name}，法条编号：第{article}条，"
            f"原始引用：{ref.raw_text}"
        )
    refs_text = "\n".join(refs_text_parts)

    prompt = LAW_ARTICLE_VERIFICATION_PROMPT.format(legal_references=refs_text)

    messages = [
        {"role": "system", "content": "你是一位中国法律法规核验专家，只输出 JSON 格式结果。"},
        {"role": "user", "content": prompt},
    ]

    try:
        from llm_client import llm_client
        response = await llm_client.chat(messages, stream=False, temperature=0.3)
    except Exception as e:
        print(f"[LawVerification] LLM 调用失败: {e}")
        # 降级：返回基本核验结果
        return [
            LawVerificationDetail(
                article=f"{ref.full_law_name or ref.law_name or ''}第{ref.article_num}条",
                original_content=ref.raw_text,
                status="⚠️存疑",
                reason=f"LLM 核验服务不可用: {str(e)}",
                is_effective=True,
                remarks="无法完成自动核验，请人工核实"
            )
            for ref in refs_to_verify
        ]

    # 解析 LLM 返回的 JSON
    results = _parse_verification_response(response, refs_to_verify)
    return results


def _parse_verification_response(
    response: str,
    refs: List[LawReference]
) -> List[LawVerificationDetail]:
    """解析 LLM 返回的法条核验 JSON 结果

    Args:
        response: LLM 返回的原始文本
        refs: 原始法条引用列表（用于回退）

    Returns:
        LawVerificationDetail 列表
    """
    import json as json_module

    # 尝试提取 JSON 块
    json_str = response
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        if end > start:
            json_str = response[start:end].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        if end > start:
            json_str = response[start:end].strip()

    try:
        data = json_module.loads(json_str)
        verification_results = data.get("verification_results", [])
    except (json_module.JSONDecodeError, ValueError, AttributeError) as e:
        print(f"[LawVerification] JSON 解析失败: {e}")
        # 尝试从文本中提取 JSON 对象
        import re as re_module
        json_match = re_module.search(r'\{[\s\S]*"verification_results"[\s\S]*\}', response)
        if json_match:
            try:
                data = json_module.loads(json_match.group())
                verification_results = data.get("verification_results", [])
            except (json_module.JSONDecodeError, ValueError):
                verification_results = []
        else:
            verification_results = []

    results = []
    for i, ref in enumerate(refs):
        law_name = ref.full_law_name or ref.law_name or ""
        article_label = f"{law_name}第{ref.article_num}条" if ref.article_num else law_name

        if i < len(verification_results):
            vr = verification_results[i]
            corrected_article = vr.get("corrected_article") or ""
            if corrected_article in ("null", None):
                corrected_article = ""
            corrected_content = vr.get("corrected_content") or ""
            if corrected_content in ("null", None):
                corrected_content = ""
            is_effective = vr.get("is_effective", True)
            if isinstance(is_effective, str):
                is_effective = is_effective.lower() not in ("false", "no", "0")

            results.append(LawVerificationDetail(
                article=vr.get("original_article", article_label),
                original_content=vr.get("original_content", ref.raw_text),
                status=vr.get("verification_status", "⚠️存疑"),
                reason=vr.get("verification_detail", "LLM 未返回详细说明"),
                correct_article=corrected_article,
                correct_content=corrected_content,
                is_effective=is_effective,
                remarks=vr.get("remarks", ""),
            ))
        else:
            # 回退：LLM 返回结果不足
            results.append(LawVerificationDetail(
                article=article_label,
                original_content=ref.raw_text,
                status="⚠️存疑",
                reason="LLM 返回结果不完整，缺少该法条的核验信息",
                is_effective=True,
                remarks="请人工核实",
            ))

    return results


def generate_verification_markdown(verifications: List[LawVerificationDetail]) -> str:
    """生成法条核验结果的 Markdown 表格

    Args:
        verifications: 法条核验详情列表

    Returns:
        Markdown 格式的核验结果表格
    """
    if not verifications:
        return ""

    lines = ["\n\n---\n", "## 法条核验结果\n"]

    lines.append("| 法条编号 | 核验状态 | 说明 |")
    lines.append("|----------|----------|------|")

    for v in verifications:
        article = v.article or "未知"
        status = v.status or "⚠️存疑"
        reason = v.reason or ""

        # 截断过长的说明
        if len(reason) > 100:
            reason = reason[:97] + "..."

        lines.append(f"| {article} | {status} | {reason} |")

    # 添加修正建议
    corrections = [v for v in verifications if v.status == "❌错误" and v.correct_article]
    if corrections:
        lines.append("\n### 🔧 修正建议\n")
        for v in corrections:
            lines.append(f"- **{v.article}** → **{v.correct_article}**")
            if v.correct_content:
                lines.append(f"  - 修正后内容：{v.correct_content}")

    # 添加存疑提示
    doubts = [v for v in verifications if v.status == "⚠️存疑"]
    if doubts:
        lines.append("\n### ⚠️ 存疑条目\n")
        for v in doubts:
            lines.append(f"- **{v.article}**：{v.reason}")

    lines.append(f"\n*本核验结果由 AI 自动生成，仅供参考。重要法律事务请咨询专业律师。*")
    return "\n".join(lines)