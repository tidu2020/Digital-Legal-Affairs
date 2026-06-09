"""
法条搜索和验证模块（增强版）
通过国家法律法规数据库 (flk.npc.gov.cn) 搜索和验证法条

功能：
1. 精准法律搜索（标题匹配，优先现行有效）
2. 自动识别"第X条"查询，返回具体条款内容
3. 自动标注时效性状态
"""

import json
import re
import requests
import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

# ===== 常量 =====

FLK_BASE_URL = "https://flk.npc.gov.cn"

# 中文数字 → 阿拉伯数字
_CN_NUM_MAP = {'零':0, '〇':0, '一':1, '二':2, '两':2, '三':3, '四':4, '五':5, '六':6, '七':7, '八':8, '九':9, '十':10, '百':100, '千':1000, '万':10000}

def cn_to_arabic(cn: str) -> int:
    """中文数字转阿拉伯数字"""
    cn = cn.strip().replace('两', '二')
    total = 0
    current = 0
    unit = 1
    for ch in cn:
        if ch in '零〇':
            continue
        if ch in '一二三四五六七八九':
            current = _CN_NUM_MAP[ch]
        elif ch == '十':
            current = current or 1
            unit = 10
            total += current * unit
            current = 0
        elif ch == '百':
            current = current or 1
            unit = 100
            total += current * unit
            current = 0
        elif ch == '千':
            current = current or 1
            unit = 1000
            total += current * unit
            current = 0
        elif ch == '万':
            current = current or 1
            total = (total + current) * 10000
            current = 0
    total += current
    return total

@dataclass
class LawSearchResult:
    """法律搜索结果"""
    title: str
    bbbs: str
    gbrq: str
    sxrq: str
    sxx: int  # 1=已废止 2=已修改 3=有效 4=尚未生效
    flxz: str
    zdjg_name: str
    detail_url: str

    @property
    def is_valid(self) -> bool:
        return self.sxx == 3

    @property
    def status_text(self) -> str:
        status_map = {1: '已废止', 2: '已修改', 3: '现行有效', 4: '尚未生效'}
        return status_map.get(self.sxx, '未知')

    @property
    def status_icon(self) -> str:
        return {1: '❌', 2: '⚠️', 3: '✅', 4: '🕐'}.get(self.sxx, '❓')

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "bbbs": self.bbbs,
            "publish_date": self.gbrq,
            "effective_date": self.sxrq,
            "status": self.status_text,
            "status_code": self.sxx,
            "law_type": self.flxz,
            "authority": self.zdjg_name,
            "detail_url": self.detail_url,
        }


@dataclass
class ArticleContent:
    """法条内容"""
    article_title: str  # 第X条
    article_number: str  # 143
    law_name: str
    content: str
    source: str
    confidence: float  # 0-1

    def to_dict(self) -> Dict:
        return {
            "article_title": self.article_title,
            "article_number": self.article_number,
            "law_name": self.law_name,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
        }


class FLKApiClient:
    """国家法律法规数据库 API 客户端"""

    def __init__(self, timeout: int = 15):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': f'{FLK_BASE_URL}/',
            'Content-Type': 'application/json;charset=utf-8',
        })
        self.timeout = timeout
        self.session.verify = False

    def _clean_html(self, text: str) -> str:
        return re.sub(r'<[^>]+>', '', text)

    def search_suggest(self, title: str) -> List[str]:
        """搜索建议"""
        try:
            resp = self.session.get(
                f"{FLK_BASE_URL}/law-search/prompts/search",
                params={"title": title},
                timeout=self.timeout,
            )
            data = resp.json()
            if data.get("code") == 200:
                return [
                    self._clean_html(item["title"])
                    for item in data.get("data", [])
                ]
            return []
        except Exception as e:
            print(f"[LawSearch] 搜索建议失败: {e}")
            return []

    def search_laws(
        self,
        keyword: str,
        title_only: bool = True,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[LawSearchResult], int]:
        """搜索法律列表

        Args:
            keyword: 搜索关键词（建议是法律名称，如"民法典"）
            title_only: True=仅搜索标题（更精准）, False=全文搜索
        """
        try:
            payload = {
                "searchRange": 1,
                "sxrq": [],
                "gbrq": [],
                "searchType": 1 if title_only else 2,  # 1=标题, 2=全文
                "sxx": [],  # 不限制状态，让前端过滤
                "gbrqYear": [],
                "flfgCodeId": [],
                "zdjgCodeId": [],
                "searchContent": keyword,
                "page": page,
                "pageSize": page_size,
            }

            resp = self.session.post(
                f"{FLK_BASE_URL}/law-search/search/list",
                json=payload,
                timeout=self.timeout,
            )
            data = resp.json()

            if data.get("code") != 200:
                return [], 0

            results = []
            for row in data.get("rows", []):
                results.append(LawSearchResult(
                    title=self._clean_html(row.get("title", "")),
                    bbbs=row.get("bbbs", ""),
                    gbrq=row.get("gbrq", ""),
                    sxrq=row.get("sxrq", ""),
                    sxx=row.get("sxx", 0),
                    flxz=row.get("flxz", ""),
                    zdjg_name=row.get("zdjgName", ""),
                    detail_url=f"{FLK_BASE_URL}/detail2?pid={row.get('bbbs', '')}",
                ))

            total = data.get("total", 0)
            return results, total

        except Exception as e:
            print(f"[LawSearch] 搜索法律失败: {e}")
            return [], 0


class LawSearchTool:
    """法条搜索工具类"""

    def __init__(self):
        self.flk_client = FLKApiClient()

    def validate_law_article(self, law_name: str, article_num: str = "") -> Dict:
        """校验某部法律的时效性状态（向后兼容）"""
        try:
            keyword = f"{law_name} {article_num}".strip()
            results, total = self.flk_client.search_laws(
                keyword=keyword, page_size=3,
            )
            if not results:
                return {
                    "found": False,
                    "message": f"未找到与 '{keyword}' 相关的法律"
                }

            law = results[0]
            return {
                "found": True,
                "title": law.title,
                "status": law.status_text,
                "is_valid": law.is_valid,
                "law_type": law.flxz,
                "authority": law.zdjg_name,
                "publish_date": law.gbrq,
                "effective_date": law.sxrq,
                "detail_url": law.detail_url,
                "total_results": total,
            }
        except Exception as e:
            return {"found": False, "error": str(e)}

    # ------ 公共接口 ------

    def search(self, query: str, num_results: int = 5) -> Dict:
        """主搜索入口，自动判断查询类型

        Args:
            query: 用户输入的查询，如:
                - "民法典" (仅查法律)
                - "民法典 第143条" (查具体条款)
                - "劳动合同法 试用期" (查主题)
        """
        result = {
            "query": query,
            "results": [],
            "articles": [],
            "total_laws": 0,
            "message": "",
        }

        # 1. 解析查询：是否包含法条编号？
        law_keyword, article_num = self._parse_query(query)
        print(f"[LawSearch] 解析: 法律名='{law_keyword}', 法条='{article_num}'")

        # 2. 搜索法律（标题搜索，精准匹配）
        search_kw = law_keyword or query

        # 法律全称映射（优先搜索全称）
        full_name_map = {
            "民法典": "中华人民共和国民法典",
            "民法总则": "中华人民共和国民法总则",
            "刑法": "中华人民共和国刑法",
            "刑事诉讼法": "中华人民共和国刑事诉讼法",
            "民事诉讼法": "中华人民共和国民事诉讼法",
            "行政诉讼法": "中华人民共和国行政诉讼法",
            "劳动合同法": "中华人民共和国劳动合同法",
            "劳动法": "中华人民共和国劳动法",
            "公司法": "中华人民共和国公司法",
            "合同法": "中华人民共和国合同法",
            "婚姻法": "中华人民共和国婚姻法",
            "继承法": "中华人民共和国继承法",
            "专利法": "中华人民共和国专利法",
            "商标法": "中华人民共和国商标法",
            "著作权法": "中华人民共和国著作权法",
            "土地管理法": "中华人民共和国土地管理法",
            "消费者权益保护法": "中华人民共和国消费者权益保护法",
            "食品安全法": "中华人民共和国食品安全法",
            "环境保护法": "中华人民共和国环境保护法",
            "道路交通安全法": "中华人民共和国道路交通安全法",
            "宪法": "中华人民共和国宪法",
            "个人所得税法": "中华人民共和国个人所得税法",
            "社会保险法": "中华人民共和国社会保险法",
        }

        full_name = full_name_map.get(search_kw, search_kw)

        # 先尝试全称搜索（更精准）
        laws, total = self.flk_client.search_laws(
            keyword=full_name,
            title_only=True,
            page_size=num_results,
        )

        # 若全称搜索没有高相关结果，再用简称补充
        if not laws and full_name != search_kw:
            laws, total = self.flk_client.search_laws(
                keyword=search_kw,
                title_only=True,
                page_size=num_results,
            )

        # 降级：标题搜索无果 -> 全文搜索
        if not laws:
            laws, total = self.flk_client.search_laws(
                keyword=search_kw, title_only=False, page_size=num_results,
            )

        if not laws:
            result["message"] = f"未找到与 '{query}' 相关的法律法规"
            return result

        result["total_laws"] = total

        # 3. 结果排序：优先现行有效 > 类型 > 短标题
        laws_sorted = self._sort_laws(laws)
        result["results"] = [l.to_dict() for l in laws_sorted[:num_results]]

        # 4. 如果查询了具体条款，尝试获取条款内容
        if article_num:
            target_law = next((l for l in laws_sorted if l.is_valid), laws_sorted[0])
            article = self._fetch_article_content(
                law_name=target_law.title,
                article_num=article_num,
                bbbs=target_law.bbbs,
            )
            if article:
                result["articles"] = [article.to_dict()]
                result["message"] = f"已找到 {target_law.title} 第{article_num}条内容"
            else:
                result["message"] = f"已找到相关法律：{target_law.title}（点击链接在官网查看全文）"
        else:
            result["message"] = f"共找到 {total} 条相关法律，显示前 {min(num_results, len(laws_sorted))} 条"

        return result

    # ------ 内部方法 ------

    def _parse_query(self, query: str) -> Tuple[str, Optional[str]]:
        """解析查询，返回 (法律关键词, 法条编号)"""
        # 常见法律名称关键词
        law_names = [
            "民法典", "民法总则", "民法通则", "刑法", "刑事诉讼法",
            "民事诉讼法", "行政诉讼法", "行政复议法",
            "劳动合同法", "劳动法", "社会保险法",
            "公司法", "合伙企业法", "个人独资企业法",
            "合同法", "物权法", "担保法", "侵权责任法",
            "婚姻法", "继承法", "收养法",
            "专利法", "商标法", "著作权法",
            "土地管理法", "城市房地产管理法",
            "消费者权益保护法", "食品安全法", "产品质量法",
            "环境保护法", "道路交通安全法",
            "宪法", "立法法",
            "个人所得税法", "企业所得税法", "税收征收管理法",
        ]

        # 匹配最常见的法律名
        law_keyword = None
        for name in law_names:
            if name in query:
                law_keyword = name
                break

        # 匹配法条编号：第X条 / 第XX条 / 第XXX条 / 数字+条
        article_num = None

        # 优先匹配中文数字
        m = re.search(r'第([一二三四五六七八九十百千两零〇]{1,15})条', query)
        if m:
            article_num = str(cn_to_arabic(m.group(1)))
        else:
            m = re.search(r'第\s*(\d{1,5})\s*条', query)
            if m:
                article_num = m.group(1)

        return law_keyword, article_num

    def _sort_laws(self, laws: List[LawSearchResult]) -> List[LawSearchResult]:
        """排序：优先现行有效，再按类型（法律>行政法规>地方法规），同类型短标题优先"""
        # 类型优先级
        type_priority = {'法律': 0, '行政法规': 1, '部门规章': 2, '监察法规': 3, '司法解释': 4}

        def _type_score(flxz: str) -> int:
            for key, val in type_priority.items():
                if key in flxz:
                    return val
            return 99

        return sorted(
            laws,
            key=lambda l: (
                {3: 0, 2: 1, 4: 2, 1: 3}.get(l.sxx, 99),  # 状态
                _type_score(l.flxz),  # 法律类型
                len(l.title),  # 短标题优先
            )
        )

    def _fetch_article_content(
        self, law_name: str, article_num: str, bbbs: str = ""
    ) -> Optional[ArticleContent]:
        """通过搜索获取具体法条内容（使用百度搜索，对中文法律内容效果更佳）"""
        try:
            cn_num = ""
            try:
                cn_num = self._arabic_to_cn(int(article_num))
            except:
                pass

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'zh-CN,zh;q=0.9',
            }

            # 尝试多个搜索查询
            queries = [
                f"{law_name} 第{article_num}条",
                f"{law_name} 第{article_num}条 原文",
            ]
            if cn_num:
                queries.insert(0, f"{law_name} 第{cn_num}条")

            for query in queries:
                try:
                    # 使用百度搜索
                    url = f"https://www.baidu.com/s?wd={requests.utils.quote(query, encoding='utf-8')}"
                    resp = self.flk_client.session.get(url, headers=headers, timeout=15)
                    if resp.status_code != 200:
                        continue

                    text = resp.text
                    # 先剥离脚本/样式
                    text = re.sub(r'<script[\s\S]*?</script>', ' ', text, flags=re.IGNORECASE)
                    text = re.sub(r'<style[\s\S]*?</style>', ' ', text, flags=re.IGNORECASE)
                    text = re.sub(r'&[a-z#0-9]+;', ' ', text)
                    text = re.sub(r'<[^>]+>', ' ', text)
                    text = re.sub(r'\s+', ' ', text)

                    if len(text) < 200:
                        continue

                    # 方法1: 找包含 "第X条" 后接 "..." 的模式 (百度精选摘要)
                    article_markers = []
                    if cn_num:
                        article_markers.append(f"第{cn_num}条")
                    article_markers.append(f"第{article_num}条")

                    best_content = ""
                    for marker in article_markers:
                        # 在文本中找到所有 marker 的位置
                        idx = 0
                        while True:
                            idx = text.find(marker, idx)
                            if idx < 0:
                                break
                            # 取 marker 后的内容，直到遇到下一条 / 段落结束
                            start = idx
                            end = min(len(text), start + 600)
                            fragment = text[start:end]
                            idx = start + len(marker)

                            # 清理：去掉 marker 本身，取后续内容
                            after_marker = fragment[len(marker):].strip()

                            # 过滤掉明显是UI垃圾的内容（含"搜索"、"百度"等词在前30字）
                            if len(after_marker) < 30:
                                continue
                            # 检查前30字是否是垃圾
                            leading = after_marker[:30]
                            if any(ui in leading for ui in ['搜索', '百度', '_', 'http', 'png', 'jpg']):
                                continue

                            # 找到下一个"第X条"的位置作为边界
                            next_article = re.search(r'第[一二三四五六七八九十百千\d]{2,8}条', after_marker[20:])
                            if next_article:
                                after_marker = after_marker[:20 + next_article.start()]

                            # 找到最后一个句号（。）来截断，避免尾部的UI垃圾
                            last_period = after_marker.rfind('。')
                            if last_period > 40:
                                after_marker = after_marker[:last_period + 1]

                            # 过滤条件
                            if (40 < len(after_marker) < 600
                                    and not any(ui in after_marker for ui in ['换一换', '热搜榜', '百度', '点击', '页面'])
                                    and any(term in after_marker for term in ['，', '；', '。', '：', '（一）', '（二）'])):
                                # 优先选择更长的合法内容
                                if len(after_marker) > len(best_content):
                                    best_content = after_marker

                    # 方法2: 找中文长句（百度AI摘要格式）
                    if not best_content:
                        cn_sentences = re.findall(r'[\u4e00-\u9fa5（）()《》，。；：\-、\d\s]{100,800}', text)
                        qualified = []
                        for s in cn_sentences:
                            s = s.strip()
                            if (len(s) > 80
                                    and not any(ui in s for ui in ['换一换', '热搜榜', '百度', '搜索', '点击'])
                                    and any(term in s for term in ['，', '。', '；'])):
                                qualified.append(s)
                        if qualified:
                            # 取第一条高质量的
                            best_content = max(qualified, key=len)

                    if best_content:
                        # 统一格式
                        best_content = best_content.strip()
                        best_content = re.sub(r'\s+', ' ', best_content)

                        article_title = f"第{article_num}条"
                        if cn_num:
                            article_title = f"第{cn_num}条（第{article_num}条）"

                        return ArticleContent(
                            article_title=article_title,
                            article_number=article_num,
                            law_name=law_name,
                            content=best_content,
                            source="网络搜索（仅供参考，以官方原文为准）",
                            confidence=0.6,
                        )

                except Exception as inner_e:
                    print(f"[LawSearch] 搜索 '{query}' 失败: {inner_e}")
                    continue

            return None

        except Exception as e:
            print(f"[LawSearch] 获取法条内容失败: {e}")
            return None

    def _arabic_to_cn(self, num: int) -> str:
        """阿拉伯数字转中文数字（简化，用于 1-9999）"""
        if num == 0:
            return "零"
        digits = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']
        units = ['', '十', '百', '千']
        parts = []
        # 处理万以上
        if num >= 10000:
            wan = num // 10000
            rest = num % 10000
            return self._arabic_to_cn(wan) + "万" + (self._arabic_to_cn(rest) if rest else "")
        # 处理千以内
        s = str(num)
        result = ""
        n = len(s)
        for i, ch in enumerate(s):
            digit = int(ch)
            unit_idx = n - i - 1
            if digit == 0:
                if result and not result.endswith('零'):
                    result += '零'
            else:
                result += digits[digit] + units[unit_idx]
        return result.rstrip('零')


# ------ 全局单例 ------

law_search_tool = LawSearchTool()


# ------ 便捷函数 ------

def search_law(query: str, num_results: int = 5) -> Dict:
    return law_search_tool.search(query, num_results)


def get_suggestions(query: str) -> List[str]:
    return law_search_tool.flk_client.search_suggest(query)
