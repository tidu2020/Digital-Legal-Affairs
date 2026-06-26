from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.llm_client import LLMClient
from shared.file_processor import extract_text_from_file, extract_info_with_llm

router = APIRouter()
llm = LLMClient()

# 法条检索工具
try:
    from shared.law_search import law_search_tool
    from shared.law_validator import extract_law_references, validate_law_references, should_auto_validate
    LAW_SEARCH_AVAILABLE = True
except ImportError:
    LAW_SEARCH_AVAILABLE = False
    print("[警告] 法条检索模块未安装，将使用LLM内置知识")

SYSTEM_PROMPT = """你是一位专业的国企法务合规顾问，精通中国法律法规、国资委规定和国企合规管理体系。

你的职责包括：
1. 解答法律合规问题
2. 审核规章制度的合法性和合规性
3. 提供合规管理建议
4. 审核往来函件
5. 解读法律法规

请用专业、准确的语言回答问题，必要时引用具体法条。对于复杂问题，建议咨询专业律师。

【重要】输出要求：
- 不要使用任何markdown格式符号（如 #、*、**、-、``` 等）
- 直接输出纯文本，用自然的换行和缩进排版
- 列表用 1. 2. 3. 或 一、二、三 等方式编号
- 强调内容直接用文字说明，不要加星号"""

uploaded_files_store = {}

class ChatRequest(BaseModel):
    messages: List[dict]
    attachments: Optional[List[str]] = None
    stream: bool = True

@router.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    try:
        results = []
        for file in files:
            content = await file.read()
            text = extract_text_from_file(content, file.filename)
            info = extract_info_with_llm(llm, text, "法务文档")
            file_id = f"file_{hash(file.filename)}_{len(uploaded_files_store)}"
            uploaded_files_store[file_id] = {
                "filename": file.filename, "text": text, "info": info, "size": len(content)
            }
            results.append({
                "success": True, "file_id": file_id, "filename": file.filename,
                "text_preview": text[:200] + "..." if len(text) > 200 else text, "info": info
            })
        return {"success": True, "files": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


def _search_laws_for_query(query: str) -> str:
    """搜索法条并返回文本，只返回现行有效的法律"""
    if not LAW_SEARCH_AVAILABLE:
        return ""
    try:
        # 使用 flk_client 直接调用，传入 sxx=[3] 只获取现行有效的法律
        results, total = law_search_tool.flk_client.search_laws(
            keyword=query, 
            page_size=3, 
            sxx=[3]  # 3=现行有效
        )
        if not results:
            return ""
        
        output = f"检索到 {total} 条相关法律（仅显示现行有效）：\n"
        for i, r in enumerate(results, 1):
            output += f"\n【{i}】{r.title}\n"
            output += f"    性质：{r.flxz} | 机关：{r.zdjg_name}\n"
            output += f"    公布：{r.gbrq} | 施行：{r.sxrq}\n"
            output += f"    链接：{r.detail_url}\n"
        return output
    except Exception as e:
        print(f"[法条检索] 检索失败: {e}")
        return ""


def _build_law_context(user_message: str) -> str:
    """根据用户消息构建法条上下文"""
    if not LAW_SEARCH_AVAILABLE:
        return ""
    
    LAW_KEYWORDS = [
        '民法典', '刑法', '合同法', '劳动法', '劳动合同法', '公司法',
        '民事诉讼法', '刑事诉讼法', '行政诉讼法', '消费者权益保护法',
        '知识产权法', '著作权法', '商标法', '专利法', '反垄断法',
        '证券法', '保险法', '仲裁法', '律师法', '网络安全法', '数据安全法',
        '个人信息保护法', '环境保护法', '安全生产法', '食品安全法',
    ]
    
    detected = [kw for kw in LAW_KEYWORDS if kw in user_message]
    if not detected:
        return ""
    
    contexts = []
    for kw in detected[:3]:
        result = _search_laws_for_query(kw)
        if result and "未找到" not in result:
            contexts.append(result)
    
    if contexts:
        return "\n\n【法条检索结果 - 来自国家法律法规数据库 flk.npc.gov.cn】\n" + "\n".join(contexts)
    return ""


def _build_messages(request_messages, attachments):
    """构建真正的多轮对话messages数组"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 如果有附件，先注入附件信息
    if attachments:
        attachment_text = ""
        for file_id in attachments:
            if file_id in uploaded_files_store:
                fd = uploaded_files_store[file_id]
                attachment_text += f"\n【附件：{fd['filename']}】\n{fd['text'][:3000]}\n"
                if fd.get("info"):
                    attachment_text += f"提取的关键信息：{fd['info'].get('summary', '')}\n"
        if attachment_text:
            messages.append({"role": "user", "content": f"以下是用户上传的附件内容：\n{attachment_text}"})
            messages.append({"role": "assistant", "content": "已收到附件内容，请问有什么需要我帮忙的？"})

    # 添加对话历史
    for msg in request_messages:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # 如果最后一条是用户消息，尝试检索相关法条
    if request_messages and request_messages[-1]["role"] == "user":
        law_context = _build_law_context(request_messages[-1]["content"])
        if law_context:
            # 将法条上下文追加到用户消息中
            messages[-1] = {
                "role": "user",
                "content": request_messages[-1]["content"] + law_context
            }

    return messages


@router.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        messages = _build_messages(request.messages, request.attachments)
        response = llm.chat_messages(messages)
        return {"response": response}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    try:
        messages = _build_messages(request.messages, request.attachments)

        def generate():
            for chunk in llm.chat_messages_stream(messages):
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/law-search")
async def law_search(query: str, num_results: int = 5):
    """法条检索接口"""
    if not LAW_SEARCH_AVAILABLE:
        return JSONResponse(status_code=503, content={"error": "法条检索模块未启用"})
    try:
        results, text = law_search_tool.search(query, num_results=num_results, verify=True)
        return {"query": query, "results": results, "text": text}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
