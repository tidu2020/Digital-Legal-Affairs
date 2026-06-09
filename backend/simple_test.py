
import sys
print(f"Python 版本: {sys.version}")
print(f"当前目录: {sys.path}")

try:
    import fastapi
    print("✓ FastAPI 已安装")
except ImportError as e:
    print(f"✗ FastAPI 未安装: {e}")

try:
    import uvicorn
    print("✓ Uvicorn 已安装")
except ImportError as e:
    print(f"✗ Uvicorn 未安装: {e}")

try:
    from app import app
    print("✓ app:app 可以正常导入")
except Exception as e:
    print(f"✗ app:app 导入失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
