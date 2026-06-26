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
    contract_text: str = ""
    user_stance: str = "auto"
    special_focus: str = ""
    attachments: Optional[List[str]] = None

@router.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """上传合同文件，自动提取信息"""
    try:
        results = []
        for file in files:
            content = await file.read()
            text = extract_text_from_file(content, file.filename)
            
            info = extract_info_with_llm(llm, text, "合同文档")
            
            file_id = f"contract_{hash(file.filename)}_{len(uploaded_files_store)}"
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
                "text": text,
                "info": info
            })
        
        return {"success": True, "files": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/api/review")
async def review_contract(request: ReviewRequest):
    """审核合同，支持多文件"""
    try:
        # 合并所有合同文本
        all_texts = []
        if request.contract_text:
            all_texts.append(request.contract_text)
        
        if request.attachments:
            for file_id in request.attachments:
                if file_id in uploaded_files_store:
                    all_texts.append(uploaded_files_store[file_id]["text"])
        
        contract_text = "\n\n".join(all_texts)
        if not contract_text.strip():
            return JSONResponse(status_code=400, content={"error": "请提供合同文本"})
        
        system_prompt = """你是一位专业的合同审核专家，精通《民法典》合同编及相关司法解释。

请对合同进行法律效力与业务可行性的双重深度审查。

审核报告应包含：
1. 合同概要（合同类型、双方主体、标的、价款等）
2. 法律风险分析（逐条审查，标注风险等级）
3. 修改建议（具体可落地的修改方案）
4. 行动清单

【重要】输出要求：不要使用markdown格式符号（#、*、```等），直接输出纯文本，用自然换行和缩进排版。"""
        
        user_prompt = f"""请审核以下合同：

审核立场：{request.user_stance}
特别关注：{request.special_focus or '无'}

合同全文：
{contract_text}"""
        
        report = llm.chat(system_prompt, user_prompt)
        return {"success": True, "report": report}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
