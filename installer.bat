@echo off
chcp 65001 >nul
echo ================================================
echo   UNION IA - Installation des dependances
echo ================================================
echo.

echo [1/3] Mise a jour de pip...
python -m pip install --upgrade pip --quiet

echo [2/3] Installation des dependances de base...
python -m pip install numpy>=1.21.0 rich>=12.0.0

echo [3/3] Installation de llama-cpp-python (GPU CUDA)...
echo       Cela peut prendre plusieurs minutes...
echo.

REM Essai avec le wheel CUDA precompile (GTX 1650 = CUDA 12.x)
python -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --upgrade

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo   GPU non disponible, installation CPU...
    python -m pip install llama-cpp-python --upgrade
)

echo.
echo ================================================
echo   Installation terminee !
echo   Lance UNION IA avec lancer.bat
echo ================================================
pause
