#!/usr/bin/env bash
set -euo pipefail

# 1. Upgrade pip (quietly)
python -m pip install --upgrade pip --quiet

# 2. Install Poetry itself (if not already present)
python -m pip install poetry --quiet

# 3. Run Poetry install – only the main group, completely silent
poetry install --only main \
    --quiet \
    --no-interaction \
    --no-ansi \
    --no-cache \
    --sync

# 4. (optional) make sure the virtual-env bin is on PATH for Streamlit
export PATH="$(poetry env info --path)/bin:$PATH"