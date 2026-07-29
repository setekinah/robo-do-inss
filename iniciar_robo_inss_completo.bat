@echo off
setlocal

set "APP_DIR=C:\Users\bruno\OneDrive\Desktop\Robo do INSS"
set "APP_FILE=%APP_DIR%\app.py"
set "PYTHON_EXE=C:\Users\bruno\AppData\Local\Python\pythoncore-3.14-64\python.exe"
set "APP_URL=http://localhost:8501"

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
) else (
    py -c "import streamlit" >nul 2>&1
    if errorlevel 1 goto missing_streamlit_py
)

echo Encerrando instancias antigas do Streamlit/Python...
taskkill /F /IM streamlit.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Iniciando SOFI.IA PREVI...
if exist "%PYTHON_EXE%" (
    start "SOFI.IA PREVI - Streamlit" "%PYTHON_EXE%" -m streamlit run "%APP_FILE%"
) else (
    start "SOFI.IA PREVI - Streamlit" py -m streamlit run "%APP_FILE%"
)

echo Aguardando a aplicacao subir...
timeout /t 6 /nobreak >nul

echo Abrindo navegador...
start "" "%APP_URL%"

echo.
echo SOFI.IA PREVI iniciada.
echo Se a pagina nao abrir de imediato, acesse:
echo %APP_URL%

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
