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

class AnalyzeRequest(BaseModel):
    case_info: str = ""
    attachments: Optional[List[str]] = None

class DocumentRequest(BaseModel):
    doc_type: str
    case_info: str = ""
    requirements: str = ""
    attachments: Optional[List[str]] = None

@router.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """上传案件相关文件"""
    try:
        results = []
        for file in files:
            content = await file.read()
            text = extract_text_from_file(content, file.filename)
            
            info = extract_info_with_llm(llm, text, "案件材料")
            
            file_id = f"case_{hash(file.filename)}_{len(uploaded_files_store)}"
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

def _build_context(case_info: str, attachments: Optional[List[str]]) -> str:
    """构建上下文"""
    texts = []
    if case_info:
        texts.append(case_info)
    
    if attachments:
        for file_id in attachments:
            if file_id in uploaded_files_store:
                file_data = uploaded_files_store[file_id]
                texts.append(f"【{file_data['filename']}】\n{file_data['text'][:3000]}")
    
    return "\n\n".join(texts)

@router.post("/api/analyze")
async def analyze_case(request: AnalyzeRequest):
    """分析案情，支持多文件"""
    try:
        context = _build_context(request.case_info, request.attachments)
        if not context.strip():
            return JSONResponse(status_code=400, content={"error": "请提供案件信息"})
        
        system_prompt = """你是一位专业的诉讼律师，精通中国民事、刑事、行政诉讼程序。

请对案件情况进行分析，包括：
1. 案件性质和案由
2. 争议焦点
3. 法律依据
4. 诉讼策略建议
5. 风险提示

【重要】输出要求：不要使用markdown格式符号，直接输出纯文本。"""
        
        response = llm.chat(system_prompt, f"请分析以下案件情况：\n\n{context}")
        return {"response": response}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/api/document")
async def generate_document(request: DocumentRequest):
    """生成法律文书，支持多文件"""
    try:
        context = _build_context(request.case_info, request.attachments)
        if not context.strip():
            return JSONResponse(status_code=400, content={"error": "请提供案件信息"})
        
        system_prompt = f"""你是一位专业的法律文书撰写专家，精通各类法律文书的格式和写作规范。

请根据提供的案件信息，生成一份标准的{request.doc_type}。

要求：
1. 格式规范，符合法律文书写作标准
2. 事实清楚，理由充分
3. 法律依据准确
4. 语言严谨规范

【重要】输出要求：不要使用markdown格式符号，直接输出纯文本格式的法律文书。"""
        
        prompt = f"案件信息：\n{context}"
        if request.requirements:
            prompt += f"\n\n特殊要求：\n{request.requirements}"
        
        response = llm.chat(system_prompt, prompt)
        return {"response": response}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
