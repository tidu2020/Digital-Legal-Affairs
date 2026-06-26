"""
国企数字法务平台 - 综合入口
集成六大模块 + 小工具
"""
import os
import sys
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

sys.path.insert(0, os.path.dirname(__file__))

from shared.llm_client import LLMClient

app = FastAPI(title="国企数字法务平台")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = LLMClient()

# ============ Module Routes ============

from modules.consulting.routes import router as consulting_router
from modules.contract_review.routes import router as contract_review_router
from modules.case_management.routes import router as case_management_router
from modules.report_writing.routes import router as report_writing_router
from modules.decision_review.routes import router as decision_review_router
from modules.regulation_review.routes import router as regulation_review_router

app.include_router(consulting_router, prefix="/modules/consulting")
app.include_router(contract_review_router, prefix="/modules/contract_review")
app.include_router(case_management_router, prefix="/modules/case_management")
app.include_router(report_writing_router, prefix="/modules/report_writing")
app.include_router(decision_review_router, prefix="/modules/decision_review")
app.include_router(regulation_review_router, prefix="/modules/regulation_review")

# ============ Tool Routes ============

from tools.desensitization.routes import router as desensitization_router
from tools.law_search.routes import router as law_search_router
app.include_router(desensitization_router, prefix="/tools/desensitization")
app.include_router(law_search_router, prefix="/tools/law_search")

# ============ Static Files ============

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

# Mount module frontends
for module_name in ["consulting", "contract_review", "case_management", "report_writing", "decision_review", "regulation_review"]:
    module_frontend = os.path.join(os.path.dirname(__file__), "modules", module_name, "frontend")
    if os.path.exists(module_frontend):
        app.mount(f"/modules/{module_name}/frontend", StaticFiles(directory=module_frontend), name=f"{module_name}_frontend")

# Mount tool frontends
desensitization_frontend = os.path.join(os.path.dirname(__file__), "tools", "desensitization", "frontend")
if os.path.exists(desensitization_frontend):
    app.mount("/tools/desensitization/frontend", StaticFiles(directory=desensitization_frontend), name="desensitization_frontend")

# ============ Main Page ============

@app.get("/")
async def index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

# ============ Module & Tool Pages ============

@app.get("/modules/{module_name}")
async def module_page(module_name: str):
    module_frontend = os.path.join(os.path.dirname(__file__), "modules", module_name, "frontend", "index.html")
    if os.path.exists(module_frontend):
        return FileResponse(module_frontend)
    return JSONResponse(status_code=404, content={"error": f"模块 {module_name} 不存在"})

@app.get("/tools/{tool_name}")
async def tool_page(tool_name: str):
    tool_frontend = os.path.join(os.path.dirname(__file__), "tools", tool_name, "frontend", "index.html")
    if os.path.exists(tool_frontend):
        return FileResponse(tool_frontend)
    return JSONResponse(status_code=404, content={"error": f"工具 {tool_name} 不存在"})

# ============ Smart Chat API ============

MODULE_KEYWORDS = {
    "consulting": ["咨询", "问题", "法律", "合规", "规定", "函件", "复函", "回函"],
    "contract_review": ["合同", "协议", "签约", "甲方", "乙方", "条款"],
    "case_management": ["案件", "诉讼", "仲裁", "起诉", "答辩", "证据", "判决"],
    "report_writing": ["报告", "总结", "法治建设", "合规管理", "内控", "风险报告"],
    "decision_review": ["上会", "议题", "请示", "签报", "决策"],
    "regulation_review": ["制度", "规章", "管理办法", "规定", "规范"]
}

class SmartChatRequest(BaseModel):
    messages: List[dict]

def detect_module(message: str) -> str:
    best_module = "consulting"
    best_score = 0
    for module, keywords in MODULE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in message)
        if score > best_score:
            best_score = score
            best_module = module
    return best_module

MODULE_NAMES = {
    "consulting": "法律合规咨询",
    "contract_review": "合同审核",
    "case_management": "案件应对",
    "report_writing": "报告撰写",
    "decision_review": "经营决策审核",
    "regulation_review": "制度审核"
}

@app.post("/api/smart-chat")
async def smart_chat(request: SmartChatRequest):
    try:
        last_msg = request.messages[-1]["content"] if request.messages else ""
        detected_module = detect_module(last_msg)
        module_name = MODULE_NAMES.get(detected_module, "法律合规咨询")
        
        system_prompt = f"""你是国企数字法务平台的智能助手。
用户的问题被识别为【{module_name}】模块的范畴。

请用专业、简洁的语言回答用户的问题。
如果问题需要更深入的分析，建议用户进入相应的模块页面进行详细操作。

【重要】输出要求：不要使用markdown格式符号（#、*、```等），直接输出纯文本。"""
        
        messages = [{"role": "system", "content": system_prompt}]
        for msg in request.messages:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        response = llm.chat_messages(messages)
        return {"response": response, "module": detected_module}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ============ Run ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=1824)
