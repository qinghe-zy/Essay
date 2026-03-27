@echo off
cd /d D:\Project\blog\blog-new\blog-frontend
call npm.cmd run dev -- --host 127.0.0.1 --port 5173 > "D:\Essay\essay\04_测试材料\前端运行日志.log" 2>&1
