
import subprocess
import sys
import os
import time
import threading

# 设置工作目录
backend_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(backend_dir)

print("=" * 60)
print("国企法务助手 - FastAPI 服务")
print("=" * 60)
print()

# 命令
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

print(f"启动命令: {' '.join(cmd)}")
print()
print("服务地址:")
print("  - 主页: http://127.0.0.1:1824")
print("  - API文档: http://127.0.0.1:1824/docs")
print("  - 健康检查: http://127.0.0.1:1824/api/health")
print()
print("正在启动服务...")
print()

# 启动进程
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    universal_newlines=True
)

# 定义输出读取函数
def read_output():
    try:
        for line in process.stdout:
            print(line, end='')
    except:
        pass

# 启动输出读取线程
output_thread = threading.Thread(target=read_output, daemon=True)
output_thread.start()

try:
    # 等待服务启动
    time.sleep(5)
    
    # 检查进程是否还在运行
    if process.poll() is None:
        print()
        print("=" * 60)
        print("✓ 服务启动成功！")
        print("=" * 60)
        print()
        print("访问地址:")
        print("  - 主页: http://127.0.0.1:1824")
        print("  - API文档: http://127.0.0.1:1824/docs")
        print()
        print("按 Ctrl+C 停止服务")
        print()
        
        # 等待用户中断
        while process.poll() is None:
            time.sleep(1)
    else:
        print()
        print("✗ 服务启动失败")
        print(f"退出代码: {process.returncode}")
        
except KeyboardInterrupt:
    print()
    print("正在停止服务...")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    print("服务已停止")
