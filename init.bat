@echo off
chcp 936 >nul 2>&1
title YOLO-Forge SP - Windows Setup

echo.
echo =========================================
echo   YOLO-Forge SP - Windows Init
echo =========================================
echo.

echo [1/5] Check Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo   X Node.js not found!
    echo   Install from: https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do echo   OK Node.js %%i

echo.
echo [2/5] Check Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   WARN Python not found, YOLO features will use mock mode
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   OK %%i
)

echo.
echo [3/5] Install Node.js dependencies...
echo   This takes 2-5 minutes, please wait...
echo.
call npm install
if %errorlevel% neq 0 (
    echo.
    echo   FAILED! Try with mirror:
    echo   npm install --registry=https://registry.npmmirror.com
    pause
    exit /b 1
)
echo   OK Node.js dependencies installed

echo.
echo [4/5] Install Python dependencies...
where pip >nul 2>&1
if %errorlevel% equ 0 (
    pip install -r electron\python\requirements.txt
    if %errorlevel% neq 0 (
        echo   WARN Some Python deps failed, try mirror:
        echo   pip install -r electron\python\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    ) else (
        echo   OK Python dependencies installed
    )
) else (
    echo   WARN pip not found, install manually:
    echo   pip install -r electron\python\requirements.txt
)

echo.
echo [5/5] Build Electron main process...
call npx tsc -p tsconfig.electron.json
if %errorlevel% neq 0 (
    echo   WARN TypeScript had errors but continuing...
) else (
    echo   OK Electron main process compiled
)

echo.
echo =========================================
echo   DONE! Now run:
echo     npm run electron:dev
echo.
echo   If that fails, try:
echo     1. Open terminal 1: npm run dev
echo     2. Open terminal 2: npx tsc -p tsconfig.electron.json && npx cross-env NODE_ENV=development electron .
echo =========================================
echo.
pause
