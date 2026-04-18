#!/usr/bin/env bash
set -euo pipefail

export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"

pip install --upgrade pip
pip install -r requirements.txt

python -m playwright install chromium
