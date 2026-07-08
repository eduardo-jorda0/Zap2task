@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\streamlit.exe" (
    echo [ERRO] Ambiente virtual nao encontrado em .venv\
    echo Rode primeiro: python -m venv .venv
    echo Depois: .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

REM O Streamlit pergunta um e-mail de onboarding no terminal na primeira vez
REM que roda, e essa pergunta fica travando o processo antes do servidor
REM subir (a pagina nunca abre). Criar este arquivo antes evita a pergunta.
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    (
        echo [general]
        echo email = ""
    ) > "%USERPROFILE%\.streamlit\credentials.toml"
)

echo Iniciando Zap2Task Audio Engine...
echo O navegador vai abrir automaticamente em http://localhost:8501
echo Para encerrar, feche esta janela ou pressione Ctrl+C.
echo.

".venv\Scripts\streamlit.exe" run app.py

pause
