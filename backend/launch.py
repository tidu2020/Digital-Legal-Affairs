
import sys
import os

# 确保当前目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("国企法务助手 FastAPI 服务启动器")
print("=" * 50)
print()

try:
    from app import app
    print("✓ 成功导入 app:app")
except Exception as e:
    print(f"✗ 导入 app:app 失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    import uvicorn
    print("✓ Uvicorn 已安装")
except ImportError as e:
    print(f"✗ Uvicorn 未安装: {e}")
    print("请运行: pip install -r requirements.txt")
    sys.exit(1)

print()
print("启动服务...")
print("访问地址:")
print("  - 主页: http://127.0.0.1:1824")
print("  - API文档: http://127.0.0.1:1824/docs")
print("  - 健康检查: http://127.0.0.1:1824/api/health")
print()

try:
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=1824,
        reload=False
    )
except KeyboardInterrupt:
    print("\n服务已停止")
except Exception as e:
    print(f"\n✗ 服务启动失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
