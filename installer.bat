@echo off
chcp 65001 >nul
echo ================================================
echo   UNION IA 2.1 - Installation
echo ================================================
echo.

echo [1/3] Mise a jour de pip...
python -m pip install --upgrade pip --quiet

echo [2/3] Installation des dependances...
python -m pip install numpy>=1.21.0 rich>=12.0.0 flask>=2.3.0 openai>=1.0.0 google-generativeai>=0.8.0

echo.
echo [3/3] Configuration de la cle API...
echo.
IF NOT EXIST ".env" (
    IF EXIST ".env.exemple" (
        copy ".env.exemple" ".env" >nul
        echo   Fichier .env cree a partir du modele.
        echo   IMPORTANT : ouvre .env et colle ta cle DeepSeek
        echo   ^(obtenue sur https://platform.deepseek.com^)
    )
) ELSE (
    echo   .env deja present, on le garde.
)

echo.
echo ================================================
echo   Installation terminee !
echo.
echo   Etapes suivantes :
echo     1. Ouvre .env et mets ta cle DEEPSEEK_API_KEY
echo     2. Lance UNION IA avec lancer.bat
echo ================================================
echo.
echo   ^(Optionnel^) Modeles locaux GPU :
echo     python -m pip install llama-cpp-python
echo.
pause
