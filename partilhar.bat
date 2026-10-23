@echo off
REM ============================================================
REM  Cria um LINK publico (https://....trycloudflare.com) para a app,
REM  para outra pessoa a usar a partir de qualquer sitio.
REM
REM  Como funciona: o "cloudflared" (programa gratuito da Cloudflare) abre um
REM  tunel seguro entre a internet e o servidor no teu PC. Nao precisa de conta.
REM
REM  Atencao:
REM   - O PC tem de ficar ligado, com esta janela e a do servidor abertas.
REM   - O link muda sempre que corres isto de novo.
REM   - A app fica protegida por uma palavra-passe (SENHA no servidor\.env).
REM ============================================================
cd /d "%~dp0servidor"

echo [1/3] A procurar o cloudflared...
where cloudflared >nul 2>&1
if not errorlevel 1 goto tem_cloudflared
echo.
echo O cloudflared nao esta instalado. Posso instala-lo com o winget
echo (o instalador oficial do Windows). Pacote: Cloudflare.cloudflared
set /p RESP=Instalar agora? (s/n): 
if /i not "%RESP%"=="s" goto sem_cloudflared
winget install --id Cloudflare.cloudflared -e --accept-source-agreements
if errorlevel 1 goto sem_cloudflared
echo.
echo Instalado. Fecha esta janela e volta a abrir o partilhar.bat
echo (o Windows so encontra o programa novo numa janela nova).
pause
exit /b
:tem_cloudflared

echo [2/3] A verificar a palavra-passe...
if not exist .env type nul > .env
findstr /b /c:"SENHA=" .env >nul
if not errorlevel 1 goto tem_senha
echo.
echo Para a app ficar protegida, escolhe uma palavra-passe de acesso.
echo E esta que vais dar a quem quiseres que use a app.
set /p NOVA=Palavra-passe: 
if "%NOVA%"=="" goto sem_senha
>> .env echo.
>> .env echo SENHA=%NOVA%
set NOVA=
echo       Guardada no servidor\.env
:tem_senha

echo [3/3] A ligar o servidor e o tunel...
echo.
echo IMPORTANTE: fecha primeiro a janela preta do servidor se estiver aberta
echo (para ele ler a palavra-passe). Vai abrir uma janela nova do servidor.
pause
start "Servidor Sussurros" cmd /c "%~dp0iniciar.bat"
timeout /t 8 /nobreak >nul
echo.
echo ============================================================
echo  Procura abaixo uma linha com  https://....trycloudflare.com
echo  Esse e o link para enviar (com a palavra-passe).
echo  Para desligar o link: fecha esta janela.
echo ============================================================
echo.
cloudflared tunnel --url http://localhost:8000
pause
exit /b

:sem_cloudflared
echo.
echo Instala o cloudflared a mao em:
echo https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
pause
exit /b

:sem_senha
echo Sem palavra-passe nao crio o link (qualquer pessoa podia usar a app).
pause
