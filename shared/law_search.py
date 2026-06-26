"""
法条搜索和验证模块
通过国家法律法规数据库 (flk.npc.gov.cn) 的真实 API 搜索和验证法条

已验证的 API 接口：
- GET  /law-search/prompts/search?title=xxx     搜索建议
- POST /law-search/search/list                    搜索法律列表
- GET  /law-search/search/flfgDetails?bbbs=xxx    获取法律详情（含目录树）
- GET  /law-search/search/enumData                获取分类枚举
- GET  /law-search/index/aggregateData            获取统计数据
"""

import json
import re
import requests
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class LawSearchResult:
    """法律搜索结果"""
    title: str
    bbbs: str
    gbrq: str
    sxrq: str
    sxx: int
    flxz: str
    zdjg_name: str
    source: str = "国家法律法规数据库"
    detail_url: str = ""

    @property
    def is_valid(self) -> bool:
        return self.sxx == 3

    @property
    def status_text(self) -> str:
        status_map = {1: "已废止", 2: "已修改", 3: "有效", 4: "尚未生效"}
        return status_map.get(self.sxx, "未知")

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "bbbs": self.bbbs,
            "gbrq": self.gbrq,
            "sxrq": self.sxrq,
            "sxx": self.sxx,
            "status": self.status_text,
            "is_valid": self.is_valid,
            "flxz": self.flxz,
            "zdjg_name": self.zdjg_name,
            "source": self.source,
            "detail_url": self.detail_url
        }


@dataclass
class LawTreeNode:
    """法律目录树节点"""
    id: str
    title: str
    index: int
    children: List['LawTreeNode'] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "children": [c.to_dict() for c in self.children]
        }


class FLKApiClient:
    """
    国家法律法规数据库 API 客户端
    基于 flk.npc.gov.cn 的真实 API 接口
    """

    BASE_URL = "https://flk.npc.gov.cn"

    def __init__(self, timeout: int = 15):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://flk.npc.gov.cn/',
            'Content-Type': 'application/json;charset=utf-8'
        })
        self.timeout = timeout

    def _clean_html(self, text: str) -> str:
        return re.sub(r'<[^>]+>', '', text)

    def search_suggest(self, title: str) -> List[str]:
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/law-search/prompts/search",
                params={"title": title},
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == 200:
                return [
                    self._clean_html(item["title"])
                    for item in data.get("data", [])
                ]
            return []
        except Exception as e:
            print(f"搜索建议请求失败: {e}")
            return []

    def search_laws(
        self,
        keyword: str,
        search_type: int = 2,
        page: int = 1,
        page_size: int = 10,
        flfg_code_id: Optional[List] = None,
        zdjg_code_id: Optional[List] = None,
        sxx: Optional[List] = None,
        gbrq_year: Optional[List] = None
    ) -> Tuple[List[LawSearchResult], int]:
        try:
            payload = {
                "searchRange": 1,
                "sxrq": [],
                "gbrq": [],
                "searchType": search_type,
                "sxx": sxx or [],
                "gbrqYear": gbrq_year or [],
                "flfgCodeId": flfg_code_id or [],
                "zdjgCodeId": zdjg_code_id or [],
                "searchContent": keyword,
                "page": page,
                "pageSize": page_size
            }

            resp = self.session.post(
                f"{self.BASE_URL}/law-search/search/list",
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 200 and "rows" not in data:
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
                    detail_url=f"{self.BASE_URL}/detail2?id={row.get('bbbs', '')}"
                ))

            total = data.get("total", 0)
            return results, total

        except Exception as e:
            print(f"搜索法律法规请求失败: {e}")
            return [], 0

    def get_law_detail(self, bbbs: str) -> Optional[Dict]:
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/law-search/search/flfgDetails",
                params={"bbbs": bbbs},
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == 200:
                return data.get("data")
            return None

        except Exception as e:
            print(f"获取法律详情失败: {e}")
            return None

    def get_law_toc(self, bbbs: str) -> Optional[LawTreeNode]:
        detail = self.get_law_detail(bbbs)
        if not detail or not detail.get("content"):
            return None

        content = detail["content"]
        return self._parse_toc(content)

    def _parse_toc(self, node_data: Dict) -> LawTreeNode:
        children = []
        for child in node_data.get("children", []):
            children.append(self._parse_toc(child))

        return LawTreeNode(
            id=node_data.get("id", ""),
            title=node_data.get("title", ""),
            index=node_data.get("index", 0),
            children=children
        )

    def get_article_text(self, law_name: str, article_num: str) -> List[Dict]:
        try:
            keyword = f"{law_name} {article_num}"
            search_url = f"https://cn.bing.com/search?q={requests.utils.quote(keyword)}"

            resp = self.session.get(
                search_url,
                timeout=15,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )

            from html import unescape
            text = resp.text

            results = []

            article_patterns = [
                r'第[一二三四五六七八九十百千万\d]+条[^<。]{0,200}?',
                r'第一百[一二三四五六七八九十\d]+[款项][^<。]{0,100}?',
            ]

            for pattern in article_patterns:
                matches = re.findall(pattern, text)
                for match in matches[:5]:
                    clean = re.sub(r'<[^>]+>', '', unescape(match)).strip()
                    clean = re.sub(r'\s+', ' ', clean)
                    if len(clean) > 30 and len(clean) < 500:
                        results.append({
                            "text": clean,
                            "source": "Bing Search"
                        })

            snippets = re.findall(r'<p[^>]*>([^<]{100,})', text)
            for snippet in snippets[:20]:
                clean = re.sub(r'<[^>]+>', '', unescape(snippet)).strip()
                clean = re.sub(r'\s+', ' ', clean)

                if ('第' in clean and '条' in clean and
                    len(clean) > 50 and len(clean) < 600 and
                    not clean.startswith('http') and
                    not any(x in clean for x in ['百度百科', '百度知道', '视频', '图片'])):
                    results.append({
                        "text": clean[:500],
                        "source": "Bing Search"
                    })

            seen = set()
            unique_results = []
            for r in results:
                text = r['text']
                key = text[:80]
                if key not in seen and len(text) > 50:
                    seen.add(key)
                    unique_results.append(r)

            return unique_results[:5]

        except Exception as e:
            print(f"获取法条文本失败: {e}")
            return []


class LawSearchTool:
    """
    法条搜索工具类
    统一接口，供大模型 Function Calling 使用
    """

    def __init__(self, web_search_tool=None):
        self.flk_client = FLKApiClient()
        self.web_search = web_search_tool

    def search(
        self,
        query: str,
        num_results: int = 5,
        verify: bool = True
    ) -> Tuple[List[Dict], str]:
        if verify:
            return self._search_with_verification(query, num_results)
        else:
            return self._search_without_verification(query, num_results)

    def _search_with_verification(self, query: str, num_results: int) -> Tuple[List[Dict], str]:
        results, total = self.flk_client.search_laws(
            keyword=query,
            page_size=num_results
        )

        if results:
            output = self._format_results(query, results, total, verified=True)
            return [r.to_dict() for r in results], output

        if self.web_search:
            web_results = self.web_search.search_json(
                query=f"{query} site:flk.npc.gov.cn OR site:gov.cn 法律",
                num_results=num_results
            )
            if web_results:
                output = f"法条搜索结果：{query}\n"
                output += "=" * 50 + "\n"
                output += "⚠️ 以下结果来自网页搜索，未在国家法律法规库中直接验证\n\n"
                for i, r in enumerate(web_results, 1):
                    output += f"【{i}】{r.get('title', '')}\n"
                    output += f"    摘要：{r.get('snippet', '')}\n"
                    output += f"    链接：{r.get('url', '')}\n\n"
                output += f"建议访问 {FLKApiClient.BASE_URL} 进行确认\n"
                return [], output

        return [], f"未找到关于 '{query}' 的相关法条。"

    def _search_without_verification(self, query: str, num_results: int) -> Tuple[List[Dict], str]:
        results, total = self.flk_client.search_laws(
            keyword=query,
            page_size=num_results
        )
        if results:
            return [r.to_dict() for r in results], self._format_results(query, results, total, verified=False)
        return [], f"未找到关于 '{query}' 的相关法条。"

    def _format_results(
        self,
        query: str,
        results: List[LawSearchResult],
        total: int,
        verified: bool
    ) -> str:
        output = f"法条搜索结果：{query}\n"
        output += "=" * 60 + "\n\n"

        for i, r in enumerate(results, 1):
            if r.is_valid:
                status = "✅ 有效"
            elif r.sxx == 1:
                status = "❌ 已废止"
            elif r.sxx == 2:
                status = "⚠️ 已修改"
            elif r.sxx == 4:
                status = "🕐 尚未生效"
            else:
                status = "❓ 未知"

            output += f"【{i}】{r.title} {status}\n"
            output += f"    性质：{r.flxz}\n"
            output += f"    机关：{r.zdjg_name}\n"
            output += f"    公布：{r.gbrq}  施行：{r.sxrq}\n"

            if verified:
                output += f"    来源：{r.source}\n"

            output += f"    链接：{r.detail_url}\n\n"

        output += f"- 共找到 {total} 条相关法律法规\n"
        output += f"- 显示前 {len(results)} 条\n"

        valid_count = sum(1 for r in results if r.is_valid)
        deprecated_count = sum(1 for r in results if r.sxx == 1)
        if deprecated_count > 0:
            output += f"- ⚠️ 其中有 {deprecated_count} 条已废止，请注意\n"

        return output

    def validate_law_article(self, law_name: str, article_num: str = "") -> Dict:
        try:
            keyword = f"{law_name} {article_num}".strip()
            results, total = self.flk_client.search_laws(keyword=keyword, page_size=3)

            if not results:
                return {
                    "found": False,
                    "message": f"在国家法律法规数据库中未找到 '{keyword}' 的相关法律"
                }

            law = results[0]
            result = {
                "found": True,
                "title": law.title,
                "status": law.status_text,
                "is_valid": law.is_valid,
                "flxz": law.flxz,
                "zdjg_name": law.zdjg_name,
                "gbrq": law.gbrq,
                "sxrq": law.sxrq,
                "detail_url": law.detail_url,
                "source": law.source,
                "total_results": total
            }

            if results[0].sxx == 1:
                result["warning"] = "⚠️ 该法律已被废止，引用时请注意时效性"
            elif results[0].sxx == 2:
                result["warning"] = "⚠️ 该法律已被修改，引用时请确认最新版本"

            return result

        except Exception as e:
            return {
                "found": False,
                "error": f"验证请求失败: {str(e)}"
            }

    def get_tool_definition(self) -> Dict:
        return {
            "type": "function",
            "function": {
                "name": "law_search",
                "description": (
                    "法条搜索工具，通过国家法律法规数据库（flk.npc.gov.cn）搜索中国法律法规。"
                    "当用户询问法律条款、法律解释、法律责任、权利义务、法律程序等问题时使用。"
                    "返回结果包含法律的时效性状态（有效/已废止/已修改），并提供官方链接。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "搜索查询，应包含法律名称或关键词。"
                                "例如：'民法典'、'劳动合同法 试用期'、'刑法 盗窃罪'、'消费者权益保护法'"
                            )
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "返回的搜索结果数量，默认为5",
                            "default": 5
                        },
                        "verify": {
                            "type": "boolean",
                            "description": "是否通过国家法律法规库验证，默认为true",
                            "default": True
                        }
                    },
                    "required": ["query"]
                }
            }
        }


law_search_tool = LawSearchTool()