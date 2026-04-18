#!/usr/bin/env bash
set -euo pipefail

export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"

pip install --upgrade pip
pip install -r requirements.txt

# Install all default browsers metadata; this avoids missing headless-shell cases.
python -m playwright install
