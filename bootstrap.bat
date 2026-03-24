@echo off
SETLOCAL ENABLEEXTENSIONS

REM Check if argument is dev mode
SET MODE=%1
IF "%MODE%"=="--dev" GOTO DEV
IF "%MODE%"=="-d" GOTO DEV
IF "%MODE%"=="dev" GOTO DEV
IF "%MODE%"=="development" GOTO DEV

:PROD
echo Starting Cobalt Multiagent in [PRODUCTION] mode...
start .\.venv\Scripts\python.exe server.py
cd web
start C:\Users\rende\AppData\Local\pnpm\pnpm.CMD start
REM Wait for user to close
GOTO END

:DEV
echo Starting Cobalt Multiagent in [DEVELOPMENT] mode...
start .\.venv\Scripts\python.exe server.py --reload
cd web
start C:\Users\rende\AppData\Local\pnpm\pnpm.CMD dev
REM Wait for user to close
pause

:END
ENDLOCAL
