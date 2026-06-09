
#!/usr/bin/env python3
import sys
import os

# 设置工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 尝试直接运行 uvicorn
try:
    import uvicorn
    print("启动服务...")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=1824,
        log_level="info"
    )
except ImportError as e:
    print(f"错误: {e}")
    print("请确保已安装所需依赖: pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"启动失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
