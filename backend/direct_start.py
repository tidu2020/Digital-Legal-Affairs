
import os
import sys

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
os.chdir(current_dir)

print("=" * 60)
print("国企法务助手 - FastAPI 服务")
print("=" * 60)
print()

try:
    # 导入应用
    from app import app
    print("✓ 应用加载成功")
    
    import uvicorn
    print("✓ Uvicorn 已加载")
    print()
    
    print("服务信息:")
    print(f"  - 监听地址: 0.0.0.0:1824")
    print(f"  - 本地访问: http://127.0.0.1:1824")
    print(f"  - API 文档: http://127.0.0.1:1824/docs")
    print(f"  - 健康检查: http://127.0.0.1:1824/api/health")
    print()
    print("=" * 60)
    print("正在启动服务...")
    print()
    
    # 直接运行
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=1824,
        log_level="info"
    )
    
except ImportError as e:
    print(f"✗ 导入错误: {e}")
    print()
    print("请安装依赖: pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"✗ 错误: {type(e).__name__}: {e}")
    print()
    import traceback
    traceback.print_exc()
    sys.exit(1)
