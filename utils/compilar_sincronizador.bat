@echo off
title Compilador del Sincronizador FTP - Pasina
echo ====================================================
echo Iniciando proceso de compilacion a ejecutable (.exe)
echo ====================================================
echo.

echo [*] Instalando/Actualizando librerias necesarias y PyInstaller...
pip install pyinstaller dbf supabase requests
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] No se pudieron instalar las dependencias de Python.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [*] Compilando windows_sync.py a windows_sync.exe...
python -m PyInstaller --onefile --clean --hidden-import ventas_importer --hidden-import dbi_clientes windows_sync.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] La compilacion fallo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [*] Limpiando archivos temporales y ordenando...
if exist dist\windows_sync.exe move /y dist\windows_sync.exe .\windows_sync.exe
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist windows_sync.spec del /q windows_sync.spec

echo.
echo ====================================================
echo  COMPILACION FINALIZADA CON EXITO
echo ====================================================
pause
