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
    doc_type: str
    content: str = ""
    focus: str = ""
    attachments: Optional[List[str]] = None

@router.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """上传决策文件"""
    try:
        results = []
        for file in files:
            content = await file.read()
            text = extract_text_from_file(content, file.filename)
            
            info = extract_info_with_llm(llm, text, "决策文件")
            
            file_id = f"decision_{hash(file.filename)}_{len(uploaded_files_store)}"
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
async def review_decision(request: ReviewRequest):
    """审核决策文件，支持多文件"""
    try:
        texts = []
        if request.content:
            texts.append(request.content)
        
        if request.attachments:
            for file_id in request.attachments:
                if file_id in uploaded_files_store:
                    file_data = uploaded_files_store[file_id]
                    texts.append(f"【{file_data['filename']}】\n{file_data['text'][:3000]}")
        
        context = "\n\n".join(texts)
        if not context.strip():
            return JSONResponse(status_code=400, content={"error": "请提供文件内容"})
        
        system_prompt = f"""你是一位专业的国企法务合规审核专家，负责审核经营决策文件。

请对以下{request.doc_type}进行法律合规审核，重点关注：
1. 法律合规性：是否符合现行法律法规
2. 程序合规性：决策程序是否规范
3. 风险识别：潜在的法律风险和合规风险
4. 修改建议：具体可操作的修改意见

【重要】输出要求：不要使用markdown格式符号，直接输出纯文本。"""
        
        prompt = f"文件内容：\n{context}"
        if request.focus:
            prompt += f"\n\n审核重点：\n{request.focus}"
        
        response = llm.chat(system_prompt, prompt)
        return {"response": response}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
