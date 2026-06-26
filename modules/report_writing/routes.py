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

class ReportRequest(BaseModel):
    report_type: str
    period: str = ""
    content: str = ""
    requirements: str = ""
    attachments: Optional[List[str]] = None

@router.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """上传报告相关文件"""
    try:
        results = []
        for file in files:
            content = await file.read()
            text = extract_text_from_file(content, file.filename)
            
            info = extract_info_with_llm(llm, text, "报告资料")
            
            file_id = f"report_{hash(file.filename)}_{len(uploaded_files_store)}"
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

@router.post("/api/generate")
async def generate_report(request: ReportRequest):
    """生成报告，支持多文件"""
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
            return JSONResponse(status_code=400, content={"error": "请提供报告内容"})
        
        system_prompt = f"""你是一位专业的国企法务合规报告撰写专家。

请根据提供的信息，撰写一份{request.report_type}。

要求：
1. 格式规范，符合国企公文写作标准
2. 内容完整，逻辑清晰
3. 数据准确，分析深入
4. 语言严谨，用词规范

【重要】输出要求：不要使用markdown格式符号，直接输出纯文本格式的报告。"""
        
        prompt = f"报告期间：{request.period}\n\n报告内容：\n{context}"
        if request.requirements:
            prompt += f"\n\n特殊要求：\n{request.requirements}"
        
        response = llm.chat(system_prompt, prompt)
        return {"response": response}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
