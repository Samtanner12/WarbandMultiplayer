@echo off
setlocal
call "%~dp0..\tools\msvc-bootstrap\msvc\setup_x86.bat"
if errorlevel 1 exit /b 1
if not exist "%~dp0..\build\tests" mkdir "%~dp0..\build\tests"
cl.exe /nologo /W3 /MT /Fe:"%~dp0..\build\tests\campaign-clock.exe" /Fo:"%~dp0..\build\tests\campaign-clock.obj" "%~dp0test-campaign-clock.c"
if errorlevel 1 exit /b 1
"%~dp0..\build\tests\campaign-clock.exe"
