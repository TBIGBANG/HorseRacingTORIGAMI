#!/usr/bin/env bash
set -euo pipefail

export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"

streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
