@echo off
REM ============================================================
REM  Sussurros com IA LOCAL (Ollama): gratis, sem limites, offline.
REM  Duplo clique neste ficheiro em vez do iniciar.bat.
REM
REM  O que faz:
REM   1. Confirma que o Ollama esta instalado e ligado
REM   2. Descarrega o modelo (so na 1a vez, ~4.7 GB)
REM   3. Cria o modelo "sussurros": o mesmo modelo, mas com mais memoria
REM      de conversa (por defeito o Ollama so guarda ~4000 tokens)
REM   4. Arranca o servidor normal (iniciar.bat) a usar o Ollama
REM
REM  Para experimentar outro modelo, muda a linha MODELO_BASE abaixo
REM  (lista em https://ollama.com/library). Ex: qwen2.5:3b se o PC for lento,
REM  qwen2.5:14b se tiveres uma placa grafica com 12 GB ou mais.
REM ============================================================
set MODELO_BASE=qwen2.5:7b

echo [Ollama 1/3] A procurar o Ollama...
ollama --version >nul 2>&1
if errorlevel 1 goto sem_ollama

REM Se o Ollama nao estiver a correr em segundo plano, liga-o.
ollama list >nul 2>&1
if not errorlevel 1 goto ollama_ligado
echo       A ligar o Ollama...
start "Ollama" /min ollama serve
timeout /t 5 /nobreak >nul
:ollama_ligado

echo [Ollama 2/3] A preparar o modelo %MODELO_BASE% (a 1a vez demora: ~4.7 GB)...
ollama pull %MODELO_BASE%
if errorlevel 1 goto erro

echo [Ollama 3/3] A criar o modelo "sussurros" com mais memoria de conversa...
cd /d "%~dp0servidor"
> Modelfile echo FROM %MODELO_BASE%
>> Modelfile echo PARAMETER num_ctx 8192
ollama create sussurros -f Modelfile
if errorlevel 1 goto erro

REM A partir daqui e o arranque normal, mas a usar o Ollama.
set PROVEDOR=ollama
set PROVEDOR_FICHA=ollama
call "%~dp0iniciar.bat"
exit /b

:sem_ollama
echo.
echo O Ollama nao esta instalado.
echo Instala-o em https://ollama.com/download (versao Windows), abre-o uma vez
echo e depois volta a dar duplo clique neste ficheiro.
pause
exit /b

:erro
echo.
echo Algo correu mal (ve a mensagem acima). Copia-a e manda-ma no chat.
pause
