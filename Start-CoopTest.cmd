@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-CoopTest.ps1" %*
if errorlevel 1 pause
