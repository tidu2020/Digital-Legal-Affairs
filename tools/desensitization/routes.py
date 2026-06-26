"""
文件脱敏工具 - FastAPI 路由
"""
import os
import uuid
import shutil
import threading
import zipfile
import traceback
from datetime import datetime
from typing import Optional
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Simple task storage
tasks = {}
tasks_lock = threading.Lock()


def process_files_background(file_paths, batch_id, output_dir):
    """后台处理文件"""
    try:
        from tools.desensitization.core.batch_processor import BatchProcessor
        processor = BatchProcessor()
        
        with tasks_lock:
            tasks[batch_id]["status"] = "processing"
        
        results, report_path = processor.process_batch(file_paths, output_dir)
        
        with tasks_lock:
            tasks[batch_id]["status"] = "done"
            tasks[batch_id]["progress"] = 100
            tasks[batch_id]["results"] = []
            tasks[batch_id]["report_path"] = report_path
            tasks[batch_id]["output_dir"] = output_dir
            
            for r in results:
                tasks[batch_id]["results"].append({
                    "source_filename": os.path.basename(r.source_path),
                    "output_filename": os.path.basename(r.output_path) if r.output_path else "",
                    "success": r.success,
                    "error": r.error or "",
                    "replacement_count": len(r.replacements) if hasattr(r, 'replacements') else 0,
                })
        
        print(f"[脱敏] 任务 {batch_id} 完成，共 {len(results)} 个文件")
        
    except Exception as e:
        print(f"[脱敏] 任务 {batch_id} 失败: {e}")
        traceback.print_exc()
        with tasks_lock:
            tasks[batch_id]["status"] = "error"
            tasks[batch_id]["error"] = str(e)


@router.post("/api/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    """上传文件进行脱敏"""
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    upload_dir = os.path.join(UPLOAD_DIR, batch_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    saved_paths = []
    filenames = []
    for f in files:
        if not f.filename:
            continue
        path = os.path.join(upload_dir, f.filename)
        content = await f.read()
        with open(path, "wb") as fp:
            fp.write(content)
        saved_paths.append(path)
        filenames.append(f.filename)
    
    if not saved_paths:
        shutil.rmtree(upload_dir, ignore_errors=True)
        return JSONResponse(status_code=400, content={"error": "没有可处理的文件"})
    
    output_dir = os.path.join(OUTPUT_DIR, f"batch_{batch_id}")
    os.makedirs(output_dir, exist_ok=True)
    
    with tasks_lock:
        tasks[batch_id] = {
            "batch_id": batch_id,
            "status": "pending",
            "progress": 0,
            "total_files": len(saved_paths),
            "done_files": 0,
            "results": [],
            "error": "",
            "report_path": "",
            "output_dir": output_dir,
            "filenames": filenames,
        }
    
    thread = threading.Thread(
        target=process_files_background,
        args=(saved_paths, batch_id, output_dir),
        daemon=True,
    )
    thread.start()
    
    return {
        "success": True,
        "batch_id": batch_id,
        "total_files": len(saved_paths),
        "filenames": filenames
    }


@router.get("/api/status/{batch_id}")
async def get_status(batch_id: str):
    """获取脱敏任务状态"""
    with tasks_lock:
        task = tasks.get(batch_id)
    
    if not task:
        return JSONResponse(status_code=404, content={"error": "任务不存在"})
    
    return {
        "batch_id": task["batch_id"],
        "status": task["status"],
        "progress": task["progress"],
        "total_files": task["total_files"],
        "done_files": task["done_files"],
        "results": task["results"],
        "error": task["error"],
    }


@router.get("/api/download/{batch_id}/files")
async def download_files(batch_id: str):
    """下载脱敏后的文件"""
    with tasks_lock:
        task = tasks.get(batch_id)
    
    if not task or task["status"] != "done":
        return JSONResponse(status_code=400, content={"error": "任务未完成"})
    
    output_dir = task["output_dir"]
    if not os.path.exists(output_dir):
        return JSONResponse(status_code=404, content={"error": "输出目录不存在"})
    
    # Create zip file
    zip_path = os.path.join(UPLOAD_DIR, f"{batch_id}_result.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(output_dir):
            # Skip report directory
            if "reports" in root:
                continue
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_dir)
                zf.write(file_path, arcname)
    
    if os.path.getsize(zip_path) == 0:
        return JSONResponse(status_code=404, content={"error": "没有脱敏后的文件"})
    
    return FileResponse(zip_path, filename=f"脱敏文件_{batch_id}.zip")


@router.get("/api/download/{batch_id}/report")
async def download_report(batch_id: str):
    """下载脱敏报告"""
    with tasks_lock:
        task = tasks.get(batch_id)
    
    if not task or not task.get("report_path"):
        return JSONResponse(status_code=404, content={"error": "报告不存在"})
    
    report_path = task["report_path"]
    if os.path.exists(report_path):
        return FileResponse(report_path, filename=os.path.basename(report_path))
    return JSONResponse(status_code=404, content={"error": "报告文件丢失"})
