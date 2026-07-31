@echo off
setlocal

set "APP_DIR=%~dp0"
set "APP_FILE=%APP_DIR%app.py"
set "APP_URL=http://localhost:8501"

if not exist "%APP_FILE%" (
    echo Arquivo app.py nao encontrado em:
    echo %APP_DIR%
    pause
    exit /b 1
)

cd /d "%APP_DIR%"
py -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo Instalando as dependencias do projeto...
    py -m pip install -r requirements.txt
    if errorlevel 1 goto install_failed
)

echo Iniciando SOFI.IA PREVI...
start "SOFI.IA PREVI - Streamlit" py -m streamlit run "%APP_FILE%"
timeout /t 4 /nobreak >nul
start "" "%APP_URL%"
endlocal
exit /b 0

:install_failed
echo.
echo Nao foi possivel instalar as dependencias.
pause
endlocal
exit /b 1
