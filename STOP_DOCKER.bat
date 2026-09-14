@echo off
cd /d "%~dp0"
echo [AI Judgment System] Docker Compose stop

docker compose stop

echo.
docker compose ps
pause
