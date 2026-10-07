# Run from the repository root after installing Python, requirements and Tesseract.
if (Test-Path '.env') {
    Get-Content '.env' | ForEach-Object {
        if ($_ -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
        }
    }
}
python -m backend.server --seed
