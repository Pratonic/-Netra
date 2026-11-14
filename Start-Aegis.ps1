Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath backend/public/index.html)) {
    Write-Host 'First run: npm install; npm run build'
    exit 1
}
Write-Host 'त्रिNetra: open http://127.0.0.1:8770 in Chrome or Edge.'
Write-Host 'Local data is temporary. AWS liveness is disabled locally.'
Write-Host 'Press Ctrl+C to stop the service.'
python backend/dev.py
