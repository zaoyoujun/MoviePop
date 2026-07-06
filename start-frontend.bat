@echo off
echo ==============================================
echo         JMH-MoviePop Frontend Start Script
echo ==============================================
echo.

set "FRONTEND_DIR=%~dp0frontend"
set "NODE_MODULES=%FRONTEND_DIR%\node_modules"

echo [1/2] Checking dependencies...
if not exist "%NODE_MODULES%" (
    echo node_modules not found, installing dependencies...
    cd /d "%FRONTEND_DIR%"
    call npm install
    if %errorlevel% neq 0 (
        echo Installation failed, please check network connection
        pause
        exit /b 1
    )
    echo Dependencies installed successfully
) else (
    echo Dependencies already exist, skipping
)

echo.
echo [2/2] Starting frontend dev server...
cd /d "%FRONTEND_DIR%"
start cmd /k "npm run dev"

echo.
echo Frontend server started in new window
echo Press any key to exit this window...
pause
