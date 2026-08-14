@echo off
title SOFI.IA PREVI - Servidor Web Revolucionario
echo ============================================================
echo   SOFI.IA PREVI - Plataforma de Advocacia Previdenciaria
echo ============================================================
echo.
echo Iniciando o servidor web REST HTTP...
start http://localhost:8000
py api_server.py
pause
