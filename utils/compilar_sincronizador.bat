@echo off
title Compilador del Sincronizador FTP - Pasina
cd /d "%~dp0"
echo ====================================================
echo  Compilacion windows_sync.exe (spec fijo en repo)
echo ====================================================
echo.

echo [*] Instalando dependencias...
pip install pyinstaller dbf supabase requests
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] No se pudieron instalar las dependencias.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [*] PyInstaller usando windows_sync.spec ...
python -m PyInstaller --clean --noconfirm windows_sync.spec
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] La compilacion fallo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [*] Copiando ejecutable...
if exist dist\windows_sync.exe move /y dist\windows_sync.exe .\windows_sync.exe
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo ====================================================
echo  LISTO: windows_sync.exe en esta carpeta (utils)
echo  Llevar al servidor: solo windows_sync.exe
echo  (La 1ra corrida crea windows_sync_config.json)
echo  Ver DEPLOY_SINCRONIZADOR.md
echo ====================================================
pause
