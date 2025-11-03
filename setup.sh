#!/usr/bin/env bash
set -euo pipefail

echo "Upgrading pip..."
python -m pip install --upgrade pip --quiet

echo "Installing Poetry..."
python -m pip install poetry --quiet

echo "Installing dependencies (no-root)..."
poetry install --no-root \
    --only main \
    --quiet \
    --no-interaction \
    --no-ansi \
    --sync

# Activate venv so streamlit is on PATH
source "$(poetry env info --path)/bin/activate"

echo "Setup complete! streamlit path: $(which streamlit)"