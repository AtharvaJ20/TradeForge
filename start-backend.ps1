cd D:\TradeForge\backend
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
    }
}
$env:ALLOWED_ORIGINS = "http://localhost:5173,http://localhost:5174"
uvicorn tradeforge.main:app --reload --port 8000
