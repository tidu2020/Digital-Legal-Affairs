
import os
import sys

# 确保当前目录在路径中
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

os.chdir(script_dir)

print("正在启动 FastAPI 服务...")
print()

# 直接导入并运行
try:
    from app import app
    print("✓ 应用加载成功")
    
    import uvicorn
    
    print()
    print("=" * 60)
    print("国企法务助手 - FastAPI 服务")
    print("=" * 60)
    print()
    print("服务地址:")
    print("  - 本地访问: http://127.0.0.1:1824")
    print("  - 局域网访问: http://0.0.0.0:1824")
    print()
    print("API 文档:")
    print("  - Swagger UI: http://127.0.0.1:1824/docs")
    print("  - ReDoc: http://127.0.0.1:1824/redoc")
    print()
    print("健康检查: http://127.0.0.1:1824/api/health")
    print()
    print("=" * 60)
    print()
    print("服务正在启动...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=1824,
        log_level="info"
    )
    
except Exception as e:
    print(f"\n✗ 错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
