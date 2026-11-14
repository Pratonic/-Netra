Set-Location -LiteralPath $PSScriptRoot
Write-Host 'Aegis: open http://127.0.0.1:8766 in Chrome or Edge.'
Write-Host 'Press Ctrl+C to stop the server.'
python -m http.server 8766 --bind 127.0.0.1 --directory dist
