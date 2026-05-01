@echo off
SETLOCAL ENABLEEXTENSIONS

REM Check if argument is dev mode
SET MODE=%1
IF "%MODE%"=="--dev" GOTO DEV
IF "%MODE%"=="-d" GOTO DEV
IF "%MODE%"=="dev" GOTO DEV
IF "%MODE%"=="development" GOTO DEV

:PROD
echo Starting VLI Desktop in [PRODUCTION] mode...
cd desktop
start npm start
GOTO END

:DEV
echo Starting VLI Desktop in [DEVELOPMENT] mode...
cd desktop
start npm run dev
GOTO END

:END
ENDLOCAL
