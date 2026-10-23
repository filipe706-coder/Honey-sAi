@echo off
REM ============================================================
REM  Sussurros - arranca o servidor e abre o chat no browser.
REM  Basta dar duplo clique neste ficheiro.
REM
REM  O que faz, por ordem:
REM   1. Confirma que o Python esta instalado
REM   2. Cria um "ambiente virtual" (pasta venv) so para este projeto,
REM      para os pacotes nao se misturarem com outros projetos
REM   3. Instala os pacotes de requirements.txt (so demora a 1a vez)
REM   4. Se o .env ainda nao tiver a chave do Groq, pede-ta
REM   5. Abre o browser no chat e liga o servidor
REM  Para desligar o servidor: fecha esta janela (ou Ctrl+C).
REM ============================================================

cd /d "%~dp0servidor"

echo [1/5] A procurar o Python...
python --version >nul 2>&1
if errorlevel 1 goto sem_python
python --version

if exist venv\Scripts\activate.bat goto ja_tem_venv
echo [2/5] A criar o ambiente virtual (so na primeira vez)...
python -m venv venv
if errorlevel 1 goto erro
:ja_tem_venv
call venv\Scripts\activate.bat

echo [3/5] A instalar/verificar os pacotes...
python -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto erro

REM O .env guarda as chaves. Se ainda nao tiver a do Groq, pedimo-la e
REM acrescentamos ao fim do ficheiro (as linhas novas ganham as antigas).
REM Se o PROVEDOR ja vem definido (ex: pelo iniciar-ollama.bat), nao e preciso.
if defined PROVEDOR goto ja_tem_chave
if not exist .env type nul > .env
findstr /b /c:"GROQ_API_KEY=" .env >nul
if not errorlevel 1 goto ja_tem_chave
echo.
echo [4/5] Falta a chave do Groq (gratis).
echo       Cria-a em https://console.groq.com/keys
echo       Para colar aqui: clique direito na janela, depois Enter.
echo.
set /p CHAVE=Chave: 
if "%CHAVE%"=="" goto sem_chave
>> .env echo.
>> .env echo # Groq (acrescentado pelo iniciar.bat)
>> .env echo PROVEDOR=groq
>> .env echo PROVEDOR_FICHA=groq
>> .env echo GROQ_API_KEY=%CHAVE%
set CHAVE=
echo       Chave guardada no ficheiro servidor\.env
:ja_tem_chave

echo [5/5] A ligar o servidor... (o chat abre no browser daqui a pouco)
echo.
start "" cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8000/conversa"
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
exit /b

:sem_python
echo.
echo O Python nao esta instalado (ou nao esta no PATH).
echo Instala-o em https://www.python.org/downloads/
echo IMPORTANTE: no primeiro ecra do instalador marca "Add python.exe to PATH".
echo Depois fecha esta janela e volta a dar duplo clique no iniciar.bat.
pause
exit /b

:sem_chave
echo Nao colaste nenhuma chave. Volta a correr o iniciar.bat quando a tiveres.
pause
exit /b

:erro
echo.
echo Algo correu mal (ve a mensagem acima). Copia-a e manda-ma no chat.
pause
