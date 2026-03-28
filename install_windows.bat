@echo off
title PingMonitor Installer
color 0B

:: Move to the folder where this .bat file lives
cd /d "%~dp0"

echo.
echo  ============================================
echo    PING MONITOR - Windows Installer
echo  ============================================
echo  Working folder: %CD%
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found!
    echo  Please install Python 3.8+ from https://python.org
    echo  Make sure to check "Add Python to PATH"
    pause
    exit /b 1
)
echo  [OK] Python found

:: Install PyInstaller if missing
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo  Installing PyInstaller ^(first time only^)...
    pip install pyinstaller pillow --quiet
) else (
    echo  [OK] PyInstaller already installed - skipping
)

echo.
echo  Building PingMonitor.exe ...
echo.

python -m PyInstaller --onefile --windowed --icon=icon.ico --name=PingMonitor --version-file=version_info.txt --distpath=dist --workpath=build --specpath=. --noconfirm ping_monitor.py

if errorlevel 1 (
    echo.
    echo  [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo  ============================================
echo    Build complete!  dist\PingMonitor.exe
echo  ============================================
echo.

set /p INSTALL="Install to Program Files + shortcuts? (Y/N): "
if /i "%INSTALL%"=="Y" (
    set "DEST=%ProgramFiles%\PingMonitor"
    mkdir "%DEST%" 2>nul
    copy "dist\PingMonitor.exe" "%DEST%\PingMonitor.exe" >nul
    copy "icon.ico"             "%DEST%\icon.ico"        >nul

    powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\PingMonitor.lnk');$s.TargetPath='%DEST%\PingMonitor.exe';$s.IconLocation='%DEST%\icon.ico';$s.Save()"
    powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Programs')+'\PingMonitor.lnk');$s.TargetPath='%DEST%\PingMonitor.exe';$s.IconLocation='%DEST%\icon.ico';$s.Save()"

    echo  [OK] Installed  : %DEST%
    echo  [OK] Desktop shortcut created
    echo  [OK] Start Menu shortcut created
    echo.
)

echo  Launching PingMonitor...
start "" "dist\PingMonitor.exe"
