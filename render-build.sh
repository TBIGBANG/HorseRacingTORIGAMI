#!/usr/bin/env bash
set -euo pipefail

export PLAYWRIGHT_BROWSERS_PATH=0

pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
