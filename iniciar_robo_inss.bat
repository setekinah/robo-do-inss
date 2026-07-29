@echo off
setlocal

set "APP_DIR=C:\Users\bruno\OneDrive\Desktop\Robo do INSS"
set "APP_FILE=%APP_DIR%\app.py"
set "PYTHON_EXE=C:\Users\bruno\AppData\Local\Python\pythoncore-3.14-64\python.exe"

if not exist "%APP_FILE%" (
    echo Arquivo nao encontrado:
    echo %APP_FILE%
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" -c "import streamlit" >nul 2>&1
    if errorlevel 1 goto missing_streamlit_python
    "%PYTHON_EXE%" -m streamlit run "%APP_FILE%"
) else (
    py -c "import streamlit" >nul 2>&1
    if errorlevel 1 goto missing_streamlit_py
    py -m streamlit run "%APP_FILE%"
)

if errorlevel 1 (
    echo.
    echo Nao foi possivel iniciar o aplicativo.
    echo Verifique se o Python e o Streamlit estao instalados corretamente.
    pause
)

endlocal
exit /b 0

:missing_streamlit_python
echo.
echo O modulo Streamlit nao esta instalado para:
echo %PYTHON_EXE%
echo.
echo Rode este comando para instalar as dependencias:
echo "%PYTHON_EXE%" -m pip install -r "%APP_DIR%\requirements.txt"
pause
endlocal
exit /b 1

:missing_streamlit_py
echo.
echo O modulo Streamlit nao esta instalado no Python padrao ^(py^).
echo.
echo Rode este comando para instalar as dependencias:
echo py -m pip install -r "%APP_DIR%\requirements.txt"
pause
endlocal
exit /b 1
