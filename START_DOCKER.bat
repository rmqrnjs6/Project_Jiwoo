@echo off
cd /d "%~dp0"
echo [AI Judgment System] Docker Compose start

docker compose up -d --build
if errorlevel 1 (
  echo.
  echo Docker start failed. Make sure Docker Desktop is running.
  pause
  exit /b 1
)

echo.
docker compose ps
echo.
echo Open: http://localhost:8000
pause
