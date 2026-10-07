#!/usr/bin/env bash
set -euo pipefail
# Requires user-owned gh CLI login. Source only; no runtime records.
cd "$(dirname "$0")/.."
command -v gh >/dev/null || { echo 'Install GitHub CLI and run gh auth login first.'; exit 1; }
gh auth status
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init -b main
  git add .
  git commit -m 'Build synthetic InBody ingestion and review proof of concept'
fi
gh repo create InBodyStage1 --private --source=. --remote=origin --push
