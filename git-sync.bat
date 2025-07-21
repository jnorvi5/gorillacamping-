@echo off
set /p msg=Commit message: 
git add .
git commit -m "%msg%"
git pull origin main
git push origin main
pause
