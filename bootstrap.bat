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
cd backend
start uv run server.py
cd ../web
start pnpm start
GOTO END

:DEV
echo Starting Cobalt Multiagent in [DEVELOPMENT] mode...
cd backend
start uv run server.py --reload
cd ../web
start pnpm dev
pause

:END
ENDLOCAL
