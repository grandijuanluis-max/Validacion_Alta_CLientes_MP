@echo off
title Programar windows_sync.exe - Pasina
setlocal

REM Ejecutar como Administrador si falla "Acceso denegado".
REM Ajustá EXE_DIR a la carpeta donde está windows_sync.exe en el servidor.

set "EXE_DIR=%~dp0"
set "EXE=%EXE_DIR%windows_sync.exe"
set "TASK_NAME=Pasina_Validador_windows_sync"

if not exist "%EXE%" (
    echo [ERROR] No se encuentra: %EXE%
    echo Copiá windows_sync.exe en esta carpeta o editá EXE_DIR en este .bat
    pause
    exit /b 1
)

echo Programando tarea: %TASK_NAME%
echo Ejecutable: %EXE%
echo Horarios: Lun-Vie 09:00, 13:00, 17:00
echo.

schtasks /Delete /TN "%TASK_NAME%_0900" /F 2>nul
schtasks /Delete /TN "%TASK_NAME%_1300" /F 2>nul
schtasks /Delete /TN "%TASK_NAME%_1700" /F 2>nul

schtasks /Create /TN "%TASK_NAME%_0900" /TR "\"%EXE%\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:00 /RL HIGHEST /F
schtasks /Create /TN "%TASK_NAME%_1300" /TR "\"%EXE%\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 13:00 /RL HIGHEST /F
schtasks /Create /TN "%TASK_NAME%_1700" /TR "\"%EXE%\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 17:00 /RL HIGHEST /F

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] schtasks falló. Probá "Ejecutar como administrador".
    pause
    exit /b 1
)

echo.
echo Listo. Verificá en Programador de tareas o con:
echo   schtasks /Query /TN %TASK_NAME%_0900
echo.
pause
