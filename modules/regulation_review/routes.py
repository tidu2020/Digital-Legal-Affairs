from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.llm_client import LLMClient
from shared.file_processor import extract_text_from_file, extract_info_with_llm

router = APIRouter()
llm = LLMClient()

uploaded_files_store = {}

class ReviewRequest(BaseModel):
    regulation_name: str = ""
    content: str = ""
    focus: str = ""
    attachments: Optional[List[str]] = None

@router.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """上传待审核制度文件"""
    try:
        results = []
        for file in files:
            content = await file.read()
            text = extract_text_from_file(content, file.filename)
            
            info = extract_info_with_llm(llm, text, "制度文件")
            
            file_id = f"regulation_{hash(file.filename)}_{len(uploaded_files_store)}"
            uploaded_files_store[file_id] = {
                "filename": file.filename,
                "text": text,
                "info": info,
                "size": len(content)
            }
            
            results.append({
                "success": True,
                "file_id": file_id,
                "filename": file.filename,
                "text_preview": text[:300] + "..." if len(text) > 300 else text,
                "info": info
            })
        
        return {"success": True, "files": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/api/review")
async def review_regulation(request: ReviewRequest):
    """审核制度文件，支持多文件"""
    try:
        texts = []
        if request.content:
            texts.append(request.content)
        
        if request.attachments:
            for file_id in request.attachments:
                if file_id in uploaded_files_store:
                    file_data = uploaded_files_store[file_id]
                    texts.append(f"【{file_data['filename']}】\n{file_data['text'][:5000]}")
        
        context = "\n\n".join(texts)
        if not context.strip():
            return JSONResponse(status_code=400, content={"error": "请提供制度内容"})
        
        system_prompt = """你是一位专业的国企制度审核专家，精通中国法律法规、行政法规、国资委规定和国企内部制度体系。

请对待审核制度进行合规性检查，重点对比以下维度：
1. 法律合规性：与现行法律、行政法规是否冲突
2. 政策合规性：与国资委最新规定、政策是否一致
3. 内部一致性：与公司现有制度是否冲突
4. 完整性：制度要素是否齐全
5. 可操作性：制度条款是否具体可执行

对于发现的问题，请标注冲突等级（严重/一般/建议），并提供修改建议。

【重要】输出要求：不要使用markdown格式符号，直接输出纯文本。"""
        
        name = request.regulation_name or "待审核制度"
        prompt = f"制度名称：{name}\n\n制度内容：\n{context}"
        if request.focus:
            prompt += f"\n\n审核重点：\n{request.focus}"
        
        response = llm.chat(system_prompt, prompt)
        return {"response": response}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
