"""
国企法务助手 - 文档向量化处理模块
"""
import gc
import os
import re
import json
import sys
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

import faiss

from config import EMBEDDING_CONFIG, KNOWLEDGE_BASE_DIR, UPLOAD_DIR


class SimpleEmbedding:
    """简单的关键词嵌入（当SentenceTransformer不可用时使用）"""
    
    def __init__(self):
        self.vocab = {}
        self.dimension = 100
        self._initialized = False
    
    def initialize(self):
        """初始化词汇表"""
        if self._initialized:
            return
        
        # 常见法律词汇
        legal_terms = [
            '法律', '法规', '合规', '合同', '诉讼', '仲裁', '案件', '风险', '审核',
            '制度', '管理', '决策', '审批', '流程', '责任', '义务', '权利', '证据',
            '判决', '裁定', '调解', '律师', '法务', '知识产权', '保密', '违约', '赔偿',
            '董事会', '党委', '总经理', '三层', '三张清单', '四个全面', '三道防线'
        ]
        
        for i, term in enumerate(legal_terms):
            self.vocab[term] = np.random.randn(self.dimension)
            # 让法律相关词有相似的向量
            if '法' in term or '规' in term or '合' in term:
                self.vocab[term] = np.random.randn(self.dimension) * 0.5 + 0.5
        
        self._initialized = True
        print("使用简单嵌入模式")
    
    def encode(self, texts: List[str], show_progress_bar: bool = False) -> np.ndarray:
        """将文本编码为向量"""
        self.initialize()
        
        embeddings = []
        for text in texts:
            text_vec = np.zeros(self.dimension)
            words = list(self.vocab.keys())
            
            for word in words:
                if word in text:
                    text_vec += self.vocab[word]
            
            # 添加基于字符的简单特征
            for char in text[:20]:
                text_vec[int(ord(char) % self.dimension)] += 1
            
            # 归一化
            norm = np.linalg.norm(text_vec)
            if norm > 0:
                text_vec = text_vec / norm
            
            embeddings.append(text_vec)
        
        return np.array(embeddings).astype('float32')


class DocumentProcessor:
    """文档处理器 - 支持多种文档格式"""
    
    SUPPORTED_EXTENSIONS = {'.txt', '.md', '.pdf', '.docx', '.doc'}
    
    def __init__(self):
        self.chunk_size = 500  # 每块文本的字符数
        self.chunk_overlap = 50  # 块之间的重叠字符数
    
    def extract_text_from_file(self, file_path: Path) -> str:
        """从文件中提取文本"""
        suffix = file_path.suffix.lower()
        
        if suffix == '.txt' or suffix == '.md':
            return self._read_text_file(file_path)
        elif suffix == '.pdf':
            return self._read_pdf(file_path)
        elif suffix in ['.docx', '.doc']:
            return self._read_docx(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")
    
    def _read_text_file(self, file_path: Path) -> str:
        """读取纯文本或Markdown文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _read_pdf(self, file_path: Path) -> str:
        """读取PDF文件"""
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(file_path))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return '\n'.join(text_parts)
        except ImportError:
            return f"[PDF文件: {file_path.name}]"
    
    def _read_docx(self, file_path: Path) -> str:
        """读取Word文档"""
        try:
            from docx import Document
            doc = Document(str(file_path))
            result = '\n'.join(paragraph.text for paragraph in doc.paragraphs)

            if sys.version_info >= (3, 14):
                del doc
                gc.collect()

            return result
        except ImportError:
            return f"[Word文档: {file_path.name}]"
    
    def chunk_text(self, text: str, source: str = "") -> List[Dict[str, Any]]:
        """
        将文本分割成块
        
        Args:
            text: 原始文本
            source: 文档来源名称
        
        Returns:
            文本块列表，每个块包含文本内容和元数据
        """
        # 清理文本
        text = self._clean_text(text)
        
        # 如果文本较短，直接返回
        if len(text) <= self.chunk_size:
            if text.strip():
                return [{
                    "text": text.strip(),
                    "source": source,
                    "chunk_id": self._generate_chunk_id(source, 0, text)
                }]
            return []
        
        chunks = []
        start = 0
        chunk_num = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            
            # 尝试在句子边界处分割
            if end < len(text):
                last_period = max(
                    chunk_text.rfind('。'),
                    chunk_text.rfind('.'),
                    chunk_text.rfind('！'),
                    chunk_text.rfind('？'),
                    chunk_text.rfind('\n')
                )
                if last_period > self.chunk_size // 2:
                    chunk_text = chunk_text[:last_period + 1]
                    end = start + len(chunk_text)
            
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text.strip(),
                    "source": source,
                    "chunk_id": self._generate_chunk_id(source, chunk_num, chunk_text)
                })
                chunk_num += 1
            
            start = end - self.chunk_overlap
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊字符
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)
        return text.strip()
    
    def _generate_chunk_id(self, source: str, chunk_num: int, content: str) -> str:
        """生成唯一的块ID"""
        unique_str = f"{source}_{chunk_num}_{content[:50]}"
        return hashlib.md5(unique_str.encode()).hexdigest()
    
    def process_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """处理单个文件"""
        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return []
        
        try:
            text = self.extract_text_from_file(file_path)
            return self.chunk_text(text, source=file_path.name)
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
            return []


class EmbeddingManager:
    """向量化管理器"""
    
    def __init__(self, dimension: int = None):
        self.dimension = dimension or EMBEDDING_CONFIG["dimension"]
        self.model_name = EMBEDDING_CONFIG["model_name"]
        self._model = None
        self._index = None
        self._chunks = []
        self._use_simple = False
    
    def _get_encoder(self):
        """获取编码器（支持fallback）"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                print(f"正在加载向量化模型: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                self.dimension = self._model.get_sentence_embedding_dimension()
                print("向量化模型加载完成")
            except Exception as e:
                print(f"无法加载SentenceTransformer模型: {e}")
                print("使用简单嵌入模式")
                self._model = SimpleEmbedding()
                self._use_simple = True
                self.dimension = 100
        
        return self._model
    
    def create_index(self):
        """创建FAISS索引"""
        # 确保获取正确的维度
        self._get_encoder()
        self._index = faiss.IndexFlatIP(self.dimension)
        self._chunks = []
    
    def add_documents(self, chunks: List[Dict[str, Any]]):
        """添加文档块到索引"""
        if not chunks:
            return
        
        encoder = self._get_encoder()
        texts = [chunk["text"] for chunk in chunks]
        embeddings = encoder.encode(texts)
        
        # 归一化向量（用于余弦相似度）
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)  # 避免除零
        normalized_embeddings = embeddings / norms
        
        # 添加到索引
        self._index.add(normalized_embeddings.astype('float32'))
        self._chunks.extend(chunks)
        
        print(f"已添加 {len(chunks)} 个文档块到索引")
    
    def search(self, query: str, top_k: int = 5, threshold: float = 0.1) -> List[Dict[str, Any]]:
        """
        检索相似文档
        
        Args:
            query: 查询文本
            top_k: 返回的最大结果数
            threshold: 相似度阈值
        
        Returns:
            相似文档块列表
        """
        if self._index is None or self._index.ntotal == 0:
            return []
        
        # 编码查询
        encoder = self._get_encoder()
        query_embedding = encoder.encode([query])
        query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=1, keepdims=True)
        
        # 搜索
        scores, indices = self._index.search(query_embedding.astype('float32'), min(top_k, self._index.ntotal))
        
        # 整理结果
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and score >= threshold:
                result = self._chunks[idx].copy()
                result["score"] = float(score)
                results.append(result)
        
        return results
    
    def save_index(self, index_path: Path):
        """保存索引到磁盘"""
        if self._index is not None:
            try:
                faiss.write_index(
                    faiss.index_gpu_to_cpu(self._index) if hasattr(self._index, 'gpu_index') else self._index,
                    str(index_path)
                )
            except Exception as e:
                print(f"保存索引失败: {e}")
                return
        
        chunks_path = index_path.with_suffix('.chunks.json')
        try:
            with open(chunks_path, 'w', encoding='utf-8') as f:
                json.dump(self._chunks, f, ensure_ascii=False, indent=2)
            print(f"索引已保存到: {index_path}")
        except Exception as e:
            print(f"保存chunks失败: {e}")
    
    def load_index(self, index_path: Path) -> bool:
        """从磁盘加载索引"""
        if not index_path.exists():
            return False
        
        try:
            self._index = faiss.read_index(str(index_path))
            
            chunks_path = index_path.with_suffix('.chunks.json')
            if chunks_path.exists():
                with open(chunks_path, 'r', encoding='utf-8') as f:
                    self._chunks = json.load(f)
            
            print(f"索引已加载: {self._index.ntotal} 个文档块")
            return True
        except Exception as e:
            print(f"加载索引失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        return {
            "total_chunks": len(self._chunks),
            "dimension": self.dimension,
            "indexed": self._index is not None and self._index.ntotal > 0
        }


# 全局实例
doc_processor = DocumentProcessor()
embedding_manager = EmbeddingManager()
