# Run from the repository root. Python loads .env literally and preserves process overrides.
python -m scripts.setup_local
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m backend.server --seed
