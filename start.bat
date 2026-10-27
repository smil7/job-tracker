@echo off
rem Starts Postgres, applies migrations, then runs the API and the web app in their own windows.
cd /d "%~dp0"

echo Starting Postgres...
docker compose up -d --wait || (
  echo.
  echo Could not start Postgres. Is Docker Desktop running?
  pause
  exit /b 1
)

echo Applying database migrations...
pushd backend
uv run alembic upgrade head || (popd & pause & exit /b 1)
popd

start "Job Tracker API" cmd /k "cd /d %~dp0backend && uv run uvicorn app.main:app --reload --port 8000"

if not exist frontend\node_modules (
  echo Installing frontend packages...
  pushd frontend & call npm install & popd
)
start "Job Tracker Web" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 3 /nobreak >nul
start "" http://localhost:5173
