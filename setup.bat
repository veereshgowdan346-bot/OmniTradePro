@echo off
setlocal EnableDelayedExpansion

title OmniTradePro - Institutional Environment Setup
cd /d "%~dp0"

echo ===============================================================================
echo   OmniTradePro - Institutional Algorithmic Trading Platform (NSE, BSE, MCX)
echo   Phase 1 Foundation Setup ^& Verification Installer
echo   Platform: Windows 10/11 64-bit ^| Python 3.10+
echo ===============================================================================
echo.

:: 1. Verify Python availability in PATH
echo [*] Checking Python installation in system PATH...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Python is not installed or not accessible via system PATH.
    echo -------------------------------------------------------------------------------
    echo Please install Python 3.10 or higher from:
    echo   https://www.python.org/downloads/
    echo.
    echo CRITICAL: Ensure you select the checkbox:
    echo   [X] "Add python.exe to PATH" during installation.
    echo -------------------------------------------------------------------------------
    echo.
    pause
    exit /b 1
)

:: Verify Python version >= 3.10
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Incompatible Python version detected.
    echo -------------------------------------------------------------------------------
    for /f "tokens=*" %%V in ('python --version 2^>^&1') do echo Current version: %%V
    echo OmniTradePro requires Python 3.10 or higher.
    echo Please install a compatible Python runtime before proceeding.
    echo -------------------------------------------------------------------------------
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%V in ('python --version 2^>^&1') do echo [OK] Found %%V

:: 2. Create isolated virtual environment (.venv) if missing
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo [*] Creating isolated virtual environment in .venv...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo.
        echo [ERROR] Failed to create virtual environment (.venv).
        echo Please ensure you have sufficient filesystem permissions and disk space.
        echo.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully at .venv\
) else (
    echo [OK] Existing virtual environment found at .venv\
)

:: 3. Activate virtual environment
echo.
echo [*] Activating isolated virtual environment...
call ".venv\Scripts\activate.bat"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Unable to activate .venv\Scripts\activate.bat.
    echo.
    pause
    exit /b 1
)
echo [OK] Virtual environment activated.

:: 4. Silently upgrade pip, setuptools, and wheel
echo.
echo [*] Upgrading pip, setuptools, and wheel to latest production builds...
python -m pip install --quiet --upgrade pip setuptools wheel
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Non-fatal notice: pip/setuptools/wheel upgrade returned error code %ERRORLEVEL%.
) else (
    echo [OK] Core packaging toolchains upgraded.
)

:: 5. Install all dependencies strictly from requirements.txt
echo.
if not exist "requirements.txt" (
    echo [ERROR] File 'requirements.txt' was not found in %cd%.
    echo Please ensure requirements.txt exists in the project root.
    echo.
    pause
    exit /b 1
)

echo [*] Installing production dependencies from requirements.txt...
echo     (This may take a few moments depending on network speed)
python -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Dependency installation encountered a failure.
    echo Review pip diagnostics above. Check your internet connection and retry.
    echo.
    pause
    exit /b 1
)
echo [OK] All dependencies installed successfully.

:: 6. Create necessary institutional directory structure
echo.
echo [*] Constructing institutional directory architecture...
for %%D in (database core brokers ui logs) do (
    if not exist "%%D" (
        mkdir "%%D"
        echo [OK] Created directory: %%D\
    ) else (
        echo [OK] Directory exists: %%D\
    )
)

:: 7. Create __init__.py in package subdirectories
echo.
echo [*] Initializing package namespace modules...
for %%D in (database core brokers ui) do (
    if not exist "%%D\__init__.py" (
        type nul > "%%D\__init__.py"
        echo [OK] Initialized package module: %%D\__init__.py
    ) else (
        echo [OK] Package module present: %%D\__init__.py
    )
)

:: 8. Execute validation suite
echo.
echo [*] Launching Phase 1 Verification Suite...
echo.
python verify_setup.py
set VERIFY_STATUS=%ERRORLEVEL%

echo.
echo ===============================================================================
if %VERIFY_STATUS% equ 0 (
    echo [SUCCESS] OmniTradePro Phase 1 Foundation successfully deployed and certified!
) else (
    echo [STATUS] Verification completed with diagnostics (Exit code: %VERIFY_STATUS%).
    echo Please review the diagnostic log above to address any missing components.
)
echo ===============================================================================
echo.
pause
exit /b %VERIFY_STATUS%

