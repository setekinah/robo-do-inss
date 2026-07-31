@echo off
setlocal

set "APP_DIR=%~dp0"
set "APP_FILE=%APP_DIR%app.py"

if not exist "%APP_FILE%" (
    echo Arquivo app.py nao encontrado em:
    echo %APP_DIR%
    pause
    exit /b 1
)

cd /d "%APP_DIR%"
py -m streamlit run "%APP_FILE%"

if errorlevel 1 (
    echo.
    echo Nao foi possivel iniciar o aplicativo.
    echo Instale as dependencias com: py -m pip install -r requirements.txt
    pause
)

endlocal
