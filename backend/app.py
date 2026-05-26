"""
国企法务助手 - FastAPI 主应用
多轮对话 + 文档上传 + 附件处理 + 私有化大模型
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import SERVER_CONFIG, UPLOAD_DIR, KNOWLEDGE_BASE_DIR
from llm_client import llm_client, build_legal_system_prompt
from retrieval import rag_retriever, legal_knowledge_base

BASE_DIR = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

MAX_HISTORY_MESSAGES = 20

# 创建FastAPI应用
app = FastAPI(
    title="国企法务助手",
    description="国企法务合规智能助手",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type"],
)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ============ 路由定义 ============

@app.get("/")
async def root():
    """首页"""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ============ 数据模型 ============

class Message(BaseModel):
    """对话消息模型"""
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    """对话请求模型"""
    messages: List[Message]
    stream: bool = True
    attachments: Optional[List[str]] = None  # 附件 file_id 列表


class ChatResponse(BaseModel):
    """对话响应模型"""
    session_id: str
    response: str
    sources: Optional[List[Dict[str, Any]]] = None


# ============ 会话管理 ============

class SessionManager:
    """会话管理器"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "created_at": datetime.now().isoformat(),
            "messages": [],
            "document_ids": []
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def add_message(self, session_id: str, role: str, content: str):
        """添加消息到会话"""
        if session_id in self.sessions:
            self.sessions[session_id]["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
    
    def get_messages(self, session_id: str) -> List[Dict]:
        """获取会话消息"""
        session = self.get_session(session_id)
        if session:
            return session["messages"]
        return []
    
    def delete_session(self, session_id: str):
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        return [
            {
                "session_id": sid,
                "created_at": data["created_at"],
                "message_count": len(data["messages"])
            }
            for sid, data in self.sessions.items()
        ]


# 全局会话管理器
session_manager = SessionManager()


# ============ 路由定义 ============

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    print("正在初始化国企法务助手系统...")
    
    # 确保目录存在
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 知识库功能暂时关闭，使用内置法务体系
    print("知识库功能已关闭，使用内置法务合规体系")
    print("国企法务助手系统启动完成！")


# ============ 对话接口 ============

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    对话接口 - 非流式版本
    """
    # 创建新会话
    session_id = session_manager.create_session()
    
    # 构建消息历史（限制最大条数控制 token 消耗）
    messages_history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.messages[:-1]
    ][-MAX_HISTORY_MESSAGES:]
    
    # 获取当前用户消息
    current_message = request.messages[-1].content if request.messages else ""
    
    # 如果有附件，附加到用户消息中
    if request.attachments:
        attachment_texts = []
        for att_id in request.attachments:
            if att_id in attachments_store:
                att = attachments_store[att_id]
                att_text = att.get("text", "")
                if att_text:
                    attachment_texts.append(f"\n--- 附件: {att['filename']} ---\n{att_text}\n--- 附件结束 ---\n")
        
        if attachment_texts:
            current_message = "\n".join(attachment_texts) + f"\n\n用户指令：{current_message}"
    
    # 知识库已关闭，不检索上下文
    context = ""
    
    # 构建系统提示词
    system_prompt = build_legal_system_prompt(context)
    
    # 构建完整消息列表
    full_messages = [
        {"role": "system", "content": system_prompt}
    ] + messages_history + [
        {"role": "user", "content": current_message}
    ]
    
    # 调用大模型
    print(f"[Chat] 调用大模型, 消息数: {len(full_messages)}")
    try:
        response_text = await llm_client.chat(full_messages, stream=False)
        print(f"[Chat] 大模型回复成功, 长度: {len(response_text)}")
    except Exception as e:
        print(f"[Chat] 大模型调用失败: {e}")
        response_text = f"⚠️ AI服务调用失败：{str(e)}"
    
    # 保存对话历史
    session_manager.add_message(session_id, "user", current_message)
    session_manager.add_message(session_id, "assistant", response_text)
    
    # 整理来源信息
    sources = []
    if context:
        for line in context.split("---"):
            if "来源:" in line:
                sources.append({"source": line.strip()})
    
    return ChatResponse(
        session_id=session_id,
        response=response_text,
        sources=sources if sources else None
    )


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    对话接口 - 流式版本
    """
    # 创建新会话
    session_id = session_manager.create_session()
    
    # 构建消息历史（限制最大条数控制 token 消耗）
    messages_history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.messages[:-1]
    ][-MAX_HISTORY_MESSAGES:]
    
    # 获取当前用户消息
    current_message = request.messages[-1].content if request.messages else ""
    
    # 如果有附件，附加到用户消息中
    if request.attachments:
        attachment_texts = []
        for att_id in request.attachments:
            if att_id in attachments_store:
                att = attachments_store[att_id]
                att_text = att.get("text", "")
                if att_text:
                    attachment_texts.append(f"\n--- 附件: {att['filename']} ---\n{att_text}\n--- 附件结束 ---\n")
        
        if attachment_texts:
            current_message = "\n".join(attachment_texts) + f"\n\n用户指令：{current_message}"
    
    # 知识库已关闭，不检索上下文
    context = ""
    
    # 构建系统提示词
    system_prompt = build_legal_system_prompt(context)
    
    # 构建完整消息列表
    full_messages = [
        {"role": "system", "content": system_prompt}
    ] + messages_history + [
        {"role": "user", "content": current_message}
    ]
    
    # 流式返回
    async def generate():
        full_response = ""
        try:
            print(f"[Stream] 开始流式响应, 消息数: {len(full_messages)}")
            async for chunk in llm_client.chat_stream(full_messages):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            
            if not full_response:
                print("[Stream] 警告: LLM 返回了空响应")
                yield f"data: {json.dumps({'content': '抱歉，我未能生成回复。请检查大模型API配置是否正确。'}, ensure_ascii=False)}\n\n"
            
            # 保存对话历史
            session_manager.add_message(session_id, "user", current_message)
            session_manager.add_message(session_id, "assistant", full_response)
            
            print(f"[Stream] 响应完成, 总长度: {len(full_response)}")
        except Exception as e:
            print(f"[Stream] 流式响应错误: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'content': f'⚠️ AI服务调用失败：{str(e)}'}, ensure_ascii=False)}\n\n"
        
        yield f"data: {json.dumps({'done': True, 'session_id': session_id}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


# ============ 会话管理接口 ============

@app.post("/api/session")
async def create_session():
    """创建新会话"""
    session_id = session_manager.create_session()
    return {"session_id": session_id}


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@app.get("/api/sessions")
async def list_sessions():
    """列出所有会话"""
    return {"sessions": session_manager.list_sessions()}


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    session_manager.delete_session(session_id)
    return {"success": True}


# ============ 附件上传接口（不自动审核，等待用户指令） ============

# 全局附件存储：{file_id: {filename, content, uploaded_at}}
attachments_store: Dict[str, dict] = {}

@app.post("/api/attachments")
async def upload_attachment(
    file: UploadFile = File(...)
):
    """
    上传文档作为附件（不自动处理，等待用户后续指令）
    支持格式: txt, md, pdf, docx, doc
    """
    from embeddings import doc_processor
    
    # 检查文件格式
    allowed_extensions = {'.txt', '.md', '.pdf', '.docx', '.doc'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}。支持的格式: {', '.join(allowed_extensions)}"
        )
    
    # 检查文件大小（限制 10MB）
    content = await file.read()
    if not content or len(content) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")
    
    file_size = len(content)
    if file_size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小超过10MB限制")
    
    # 保存文件
    file_id = str(uuid.uuid4())[:8]
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    
    with open(file_path, 'wb') as f:
        f.write(content)
    
    # 提取文本内容（异步预提取，不做任何处理）
    text = ""
    try:
        text = doc_processor.extract_text_from_file(file_path) or ""
    except Exception as e:
        print(f"文件文本提取警告: {e}")
    
    if len(text) > 20000:
        text = text[:20000]
    
    # 存储到内存
    attachments_store[file_id] = {
        "filename": file.filename,
        "text": text,
        "text_length": len(text),
        "file_size": file_size,
        "uploaded_at": datetime.now().isoformat()
    }
    
    print(f"附件已保存: {file.filename} ({file_size} 字节, 文本 {len(text)} 字符)")
    
    return {
        "success": True,
        "file_id": file_id,
        "filename": file.filename,
        "file_size": file_size,
        "message": f"文件已保存为附件，您可以在输入框中输入指令（如：审核、整理、参考写文档等）"
    }

@app.get("/api/attachments")
async def list_attachments():
    """获取当前已上传的附件列表"""
    attachments = []
    for fid, info in attachments_store.items():
        attachments.append({
            "file_id": fid,
            "filename": info["filename"],
            "file_size": info["file_size"],
            "text_length": info["text_length"],
            "uploaded_at": info["uploaded_at"]
        })
    return {"attachments": attachments}

@app.delete("/api/attachments/{file_id}")
async def remove_attachment(file_id: str):
    """删除指定附件"""
    if file_id in attachments_store:
        del attachments_store[file_id]
        return {"success": True, "message": "附件已删除"}
    raise HTTPException(status_code=404, detail="附件不存在")


@app.post("/api/upload/batch")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """批量上传文档"""
    results = []
    
    for file in files:
        try:
            # 检查文件格式
            file_ext = Path(file.filename).suffix.lower()
            allowed_extensions = {'.txt', '.md', '.pdf', '.docx', '.doc'}
            
            if file_ext not in allowed_extensions:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": f"不支持的格式: {file_ext}"
                })
                continue
            
            # 保存文件
            file_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
            content = await file.read()
            
            with open(file_path, 'wb') as f:
                f.write(content)
            
            # 后台处理
            background_tasks.add_task(
                legal_knowledge_base.add_document,
                file_path
            )
            
            results.append({
                "filename": file.filename,
                "success": True,
                "file_id": file_path.stem
            })
            
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
    
    return {"results": results}


# ============ 知识库管理接口 ============

@app.get("/api/knowledge/stats")
async def get_knowledge_stats():
    """获取知识库统计信息（知识库功能已关闭，返回内置信息）"""
    return {
        "total_chunks": 0,
        "dimension": 0,
        "indexed": False,
        "message": "知识库功能已关闭，系统使用内置法务合规体系"
    }


@app.post("/api/knowledge/rebuild")
async def rebuild_knowledge_index():
    """重建知识库索引"""
    try:
        legal_knowledge_base.rebuild_index()
        return {"success": True, "message": "知识库索引重建完成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge/documents")
async def list_knowledge_documents():
    """列出知识库中的文档"""
    docs = []
    
    # 内置文档
    for path in KNOWLEDGE_BASE_DIR.rglob('*'):
        if path.is_file() and path.suffix.lower() in {'.txt', '.md', '.pdf', '.docx', '.doc'}:
            docs.append({
                "name": path.name,
                "path": str(path.relative_to(KNOWLEDGE_BASE_DIR)),
                "type": "builtin"
            })
    
    # 用户上传文档
    for path in UPLOAD_DIR.rglob('*'):
        if path.is_file() and path.suffix.lower() in {'.txt', '.md', '.pdf', '.docx', '.doc'}:
            docs.append({
                "name": path.name,
                "path": str(path.relative_to(UPLOAD_DIR)),
                "type": "uploaded"
            })
    
    return {"documents": docs}


# ============ 健康检查 ============

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "knowledge_base": legal_knowledge_base.get_stats()
    }


# ============ 启动服务器 ============

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host=SERVER_CONFIG["host"],
        port=SERVER_CONFIG["port"],
        reload=SERVER_CONFIG["debug"]
    )
