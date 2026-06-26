"""
批量处理器
负责整批脱敏任务的编排：
- 校验文件数量（上限 20 个）与格式支持
- 逐文件调度对应处理器（一进一出，输出文件与源文件一一对应）
- 汇总结果并触发报告生成
"""
import logging
import os
import sys
from datetime import datetime
from typing import Callable, List, Optional, Tuple

# Fix import paths
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import CONFIG
from core.llm_client import LLMClient
from core.report_generator import ReportGenerator
from processors.base import ProcessResult
from processors.factory import get_processor
from utils.file_utils import build_output_path, get_file_category, ensure_dir

logger = logging.getLogger(__name__)

# 进度回调签名：(done_count, total_count, latest_result) -> None
ProgressCallback = Callable[[int, int, Optional[ProcessResult]], None]


class BatchProcessor:
    """批量脱敏处理器"""

    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()
        self.report_generator = ReportGenerator()
        self.max_files = CONFIG.processing.max_files_per_batch

    def process_batch(
        self,
        file_paths: List[str],
        output_dir: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Tuple[List[ProcessResult], str]:
        """
        处理一批文件，返回 (各文件结果列表, 报告路径)。

        :param progress_callback: 每完成一个文件时回调一次
        """
        # 1. 校验
        valid_files, errors = self._validate(file_paths)
        if errors:
            for e in errors:
                logger.warning("校验失败: %s", e)

        if not valid_files:
            raise ValueError("没有可处理的合法文件。")

        # 2. 准备输出目录
        if output_dir:
            out_dir = output_dir
        else:
            batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = os.path.join(
                os.getcwd(), CONFIG.processing.output_dir_name, f"batch_{batch_id}"
            )
        ensure_dir(out_dir)
        report_dir = os.path.join(out_dir, CONFIG.processing.report_dir_name)

        logger.info(
            "开始处理批次，共 %d 个文件，输出目录: %s",
            len(valid_files), out_dir
        )

        # 3. 逐文件处理（一进一出）
        results: List[ProcessResult] = []
        total = len(valid_files)
        for idx, src in enumerate(valid_files, 1):
            logger.info(
                "[%d/%d] 正在处理: %s", idx, total, os.path.basename(src)
            )
            out_path = build_output_path(src, out_dir)
            processor = get_processor(src, self.llm)
            if processor is None:
                result = ProcessResult(
                    source_path=src,
                    output_path=out_path,
                    success=False,
                    error="不支持的文件格式或缺少必要转换工具",
                    file_type=os.path.splitext(src)[1].lstrip("."),
                )
            else:
                result = processor.process(src, out_path)
            results.append(result)

            if progress_callback is not None:
                try:
                    progress_callback(idx, total, result)
                except Exception:
                    logger.debug("进度回调异常", exc_info=True)

        # 4. 生成脱敏报告
        report_batch_id = os.path.basename(out_dir)
        logger.info("正在生成脱敏操作报告...")
        report_path = self.report_generator.generate(results, report_dir, report_batch_id)
        logger.info("报告已生成: %s", report_path)

        return results, report_path

    def _validate(self, file_paths: List[str]) -> Tuple[List[str], List[str]]:
        """校验文件列表，返回 (合法文件, 错误信息列表)"""
        valid: List[str] = []
        errors: List[str] = []

        # 数量上限校验
        if len(file_paths) > self.max_files:
            errors.append(
                f"文件数量 {len(file_paths)} 超过单批次上限 {self.max_files} 个，"
                f"请分批提交。"
            )
            # 截取前 max_files 个
            file_paths = file_paths[:self.max_files]

        for fp in file_paths:
            if not os.path.exists(fp):
                errors.append(f"文件不存在: {fp}")
                continue
            if os.path.isdir(fp):
                errors.append(f"路径为目录而非文件: {fp}")
                continue
            if get_file_category(fp) is None:
                errors.append(f"不支持的文件格式: {fp}")
                continue
            valid.append(fp)

        return valid, errors
