@echo off
chcp 65001 >nul
REM Se place dans le dossier du script, où qu'il soit installe
cd /d "%~dp0"
echo Lancement de UNION IA (terminal)...
python union_ia.py
pause
