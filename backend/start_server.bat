
@echo off
cd /d "c:\Users\Administrator\Desktop\jingtou-digital-legal\backend"
echo Starting FastAPI server...
echo Python version:
python --version
echo.
echo Testing imports...
python simple_test.py
echo.
echo Starting uvicorn server on 0.0.0.0:1824...
python -m uvicorn app:app --host 0.0.0.0 --port 1824
pause
