Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    AI Reel Maker - Local AI Video Studio" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan

$backendProcess = Start-Process -FilePath "python" -ArgumentList "run_backend.py" -PassThru -NoNewWindow
Set-Location -Path "frontend"
$frontendProcess = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -PassThru -NoNewWindow

Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"

Write-Host "`nAI Reel Maker is running at http://localhost:5173" -ForegroundColor Green
Write-Host "Backend API docs: http://127.0.0.1:8000/docs" -ForegroundColor Yellow
