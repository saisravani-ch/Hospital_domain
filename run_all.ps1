# Start all Hospital System services in separate terminal windows
# Run from project root: .\run_all.ps1

$root = $PSScriptRoot
$venv_uvicorn = Join-Path $root ".venv\Scripts\uvicorn.exe"
$venv_python = Join-Path $root ".venv\Scripts\python.exe"

$services = @(
    @{Title="KB:8000";       Cmd="& '$venv_uvicorn' apps.kb.api.main:app --port 8000"},
    @{Title="Workflow:8001"; Cmd="& '$venv_uvicorn' apps.workflows.main:app --port 8001"},
    @{Title="Agent:8002";    Cmd="& '$venv_uvicorn' apps.agent.main:app --port 8002"},
    @{Title="UI:8501";       Cmd="& '$venv_python' -m streamlit run apps\ui\streamlit_app.py"},
    @{Title="WhatsApp:3000"; Cmd="Set-Location apps\whatsapp-ui-clone; npm start"}
)

Write-Host "Starting all Hospital System services..." -ForegroundColor Cyan

foreach ($svc in $services) {
    Write-Host "  Starting $($svc.Title)..." -ForegroundColor Yellow
    Start-Process -WindowStyle Normal -FilePath "powershell.exe" -ArgumentList @(
        "-NoExit", "-Command", "Set-Location '$root'; $($svc.Cmd)"
    )
    Start-Sleep -Milliseconds 800
}

Write-Host ""
Write-Host "All services launched." -ForegroundColor Green
Write-Host "Open http://localhost:8501 for the Streamlit UI." -ForegroundColor Green
Write-Host "Open http://localhost:3000 for the WhatsApp UI." -ForegroundColor Green
