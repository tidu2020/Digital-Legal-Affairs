
import os
import sys

# 确保在正确的目录
script_path = os.path.abspath(__file__)
backend_dir = os.path.dirname(script_path)
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

print('工作目录:', os.getcwd())
print('Python 路径:', sys.executable)
print()

print('正在导入 app...')
from app import app
print('✓ app 导入成功')
print()

print('正在导入 uvicorn...')
import uvicorn
print('✓ uvicorn 导入成功')
print()

print('='*60)
print('国企法务助手 - FastAPI 服务')
print('='*60)
print()
print('服务地址:')
print('  - 主页: http://127.0.0.1:1824')
print('  - API文档: http://127.0.0.1:1824/docs')
print('  - 健康检查: http://127.0.0.1:1824/api/health')
print()
print('正在启动服务...')
print()

uvicorn.run(
    app,
    host='0.0.0.0',
    port=1824,
    log_level='info'
)
