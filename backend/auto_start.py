
import sys
import os
import subprocess
import time

# 切换到 backend 目录
backend_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(backend_dir)

print(f"当前目录: {os.getcwd()}")
print(f"Python 路径: {sys.executable}")
print()

# 测试导入
print("测试导入...")
try:
    import fastapi
    print("✓ FastAPI 已安装")
except Exception as e:
    print(f"✗ FastAPI 未安装: {e}")

try:
    import uvicorn
    print("✓ Uvicorn 已安装")
except Exception as e:
    print(f"✗ Uvicorn 未安装: {e}")

print()

# 启动服务
print("正在启动 FastAPI 服务...")
print("访问地址: http://127.0.0.1:1824")
print()

# 使用 uvicorn 启动
cmd = [
    sys.executable,
    "-m",
    "uvicorn",
    "app:app",
    "--host",
    "0.0.0.0",
    "--port",
    "1824"
]

try:
    process = subprocess.Popen(cmd, cwd=backend_dir)
    print(f"服务已启动，进程 ID: {process.pid}")
    print()
    print("服务正在运行中...")
    print("按 Ctrl+C 停止服务")
    
    # 保持脚本运行
    while True:
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\n正在停止服务...")
    process.terminate()
    process.wait()
    print("服务已停止")
except Exception as e:
    print(f"\n启动失败: {e}")
    import traceback
    traceback.print_exc()
