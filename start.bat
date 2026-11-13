@echo off
title AI Reel Maker - Intelligent Video to Shorts Platform
echo ===================================================
echo     AI Reel Maker - Local AI Video Studio
echo ===================================================
echo.
echo Starting FastAPI Backend (Port 8000)...
start "AI Reel Maker - Backend" cmd /k "python run_backend.py"

echo Starting Vite React Frontend (Port 5173)...
cd frontend
start "AI Reel Maker - Frontend" cmd /k "npm run dev"

echo Opening browser...
timeout /t 3 >nul
start http://localhost:5173

echo.
echo AI Reel Maker is now running at: http://localhost:5173
echo Backend API Docs available at:  http://127.0.0.1:8000/docs
echo.
pause
