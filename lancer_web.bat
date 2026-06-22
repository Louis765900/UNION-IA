@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Lancement de UNION IA (interface web)...
echo Ouvre http://127.0.0.1:5000 dans ton navigateur.
echo.
start "" http://127.0.0.1:5000
python web\server.py
pause
