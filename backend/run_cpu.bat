@echo off
call .venv\Scripts\activate.bat
set FW_MODEL=small
set FW_DEVICE=cpu
set FW_CTYPE=int8
uvicorn app:app --reload --port 8000