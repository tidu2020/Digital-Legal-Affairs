"""
国企法务助手 - RAG检索模块
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import KNOWLEDGE_BASE_DIR, RAG_CONFIG, UPLOAD_DIR
from embeddings import doc_processor, embedding_manager


class LegalKnowledgeBase:
    """国企法务知识库"""
    
    def __init__(self):
        self.index_path = KNOWLEDGE_BASE_DIR / "faiss_index.bin"
        self._initialized = False
    
    def initialize(self):
        """初始化知识库"""
        if self._initialized:
            return
        
        # 尝试加载已有索引
        if not embedding_manager.load_index(self.index_path):
            print("正在构建知识库索引...")
            self._build_index()
        
        self._initialized = True
    
    def _build_index(self):
        """构建知识库索引"""
        embedding_manager.create_index()
        
        # 加载内置知识库文档
        self._index_documents(KNOWLEDGE_BASE_DIR)
        
        # 加载用户上传的文档
        if UPLOAD_DIR.exists():
            self._index_documents(UPLOAD_DIR)
        
        # 保存索引
        if embedding_manager.get_stats()["total_chunks"] > 0:
            embedding_manager.save_index(self.index_path)
    
    def _index_documents(self, directory: Path):
        """为目录中的所有文档建立索引"""
        if not directory.exists():
            return
        
        all_chunks = []
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in doc_processor.SUPPORTED_EXTENSIONS:
                chunks = doc_processor.process_file(file_path)
                all_chunks.extend(chunks)
        
        if all_chunks:
            embedding_manager.add_documents(all_chunks)
    
    def add_document(self, file_path: Path) -> Dict[str, Any]:
        """添加单个文档到知识库"""
        chunks = doc_processor.process_file(file_path)
        
        if chunks:
            embedding_manager.add_documents(chunks)
            embedding_manager.save_index(self.index_path)
            return {
                "success": True,
                "chunks": len(chunks),
                "source": file_path.name
            }
        
        return {
            "success": False,
            "error": "未能从文档中提取有效内容"
        }
    
    def retrieve(self, query: str, top_k: int = None) -> str:
        """
        检索相关文档内容
        
        Args:
            query: 查询文本
            top_k: 返回的最大结果数
        
        Returns:
            格式化的相关文档内容
        """
        if not self._initialized:
            self.initialize()
        
        top_k = top_k or RAG_CONFIG["top_k"]
        threshold = RAG_CONFIG["similarity_threshold"]
        
        results = embedding_manager.search(query, top_k=top_k, threshold=threshold)
        
        if not results:
            return ""
        
        # 格式化结果
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"【文档{i}】来源: {result['source']}\n"
                f"相似度: {result['score']:.4f}\n"
                f"内容: {result['text']}\n"
            )
        
        return "\n---\n".join(context_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        return embedding_manager.get_stats()
    
    def rebuild_index(self):
        """重建索引"""
        self._initialized = False
        if self.index_path.exists():
            os.remove(self.index_path)
            chunks_path = self.index_path.with_suffix('.chunks.json')
            if chunks_path.exists():
                os.remove(chunks_path)
        self.initialize()


class RAGRetriever:
    """RAG检索器"""
    
    def __init__(self):
        self.knowledge_base = LegalKnowledgeBase()
        self.max_context_length = RAG_CONFIG["max_context_length"]
    
    def retrieve_and_build_context(self, query: str) -> str:
        """
        检索相关文档并构建上下文
        
        Args:
            query: 用户查询
        
        Returns:
            格式化的上下文字符串
        """
        context = self.knowledge_base.retrieve(query)
        
        # 如果上下文过长，截断
        if context and len(context) > self.max_context_length:
            context = context[:self.max_context_length] + "\n\n[内容已截断...]"
        
        return context
    
    def initialize(self):
        """初始化RAG系统"""
        self.knowledge_base.initialize()


# 全局实例
rag_retriever = RAGRetriever()
legal_knowledge_base = LegalKnowledgeBase()
