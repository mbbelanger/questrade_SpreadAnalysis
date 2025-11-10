@echo off
REM Build script for Questrade Trading System executable

echo ======================================================================
echo QUESTRADE TRADING SYSTEM - BUILD SCRIPT
echo ======================================================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [!] PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller
        pause
        exit /b 1
    )
)

echo [1/3] Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist QuestradeTrading.exe del /q QuestradeTrading.exe

echo [2/3] Building executable with PyInstaller...
pyinstaller --clean questrade_trading.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check the output above for errors.
    pause
    exit /b 1
)

echo [3/3] Moving executable to project root...
if exist dist\QuestradeTrading.exe (
    move dist\QuestradeTrading.exe .
    echo.
    echo ======================================================================
    echo [OK] BUILD SUCCESSFUL!
    echo ======================================================================
    echo.
    echo Executable created: QuestradeTrading.exe
    echo.
    echo IMPORTANT: Place these files in the same folder as the .exe:
    echo   - .env (with your Questrade refresh token)
    echo   - watchlist.txt (your list of tickers)
    echo.
    echo Optional: Create a 'dist' folder with the .exe and required files
    echo for easy distribution.
    echo.
) else (
    echo [ERROR] Executable not found in dist folder
    pause
    exit /b 1
)

echo Cleaning up build artifacts...
rmdir /s /q build
rmdir /s /q dist

echo.
echo Build complete!
pause
