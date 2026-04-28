@echo off
REM PlumA - entorno Windows para localizar Docker Desktop aunque no este en PATH.
if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
if exist "%LOCALAPPDATA%\Docker\Docker\resources\bin\docker.exe" set "PATH=%LOCALAPPDATA%\Docker\Docker\resources\bin;%PATH%"
if exist "%ProgramFiles(x86)%\Docker\Docker\resources\bin\docker.exe" set "PATH=%ProgramFiles(x86)%\Docker\Docker\resources\bin;%PATH%"
exit /b 0
