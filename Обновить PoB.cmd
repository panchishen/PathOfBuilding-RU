@echo off
rem Update Russian Path of Building: pull from repo, re-export game texts if the client changed
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ru\update.ps1" %*
pause
