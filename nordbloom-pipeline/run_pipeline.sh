#!/bin/bash
# Thin wrapper: source config.env, activate venv, run pipeline.py.
# All actual logic lives in scripts/pipeline.py.

set -eu

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ ! -f "$SCRIPT_DIR/config.env" ]; then
    echo "Error: $SCRIPT_DIR/config.env not found."
    echo "Run ./setup.sh first."
    exit 1
fi

# shellcheck disable=SC1091
source "$SCRIPT_DIR/config.env"

# Expand env vars so Python sees resolved paths.
export NORDBLOOM_ROOT UPSCAYL_BIN UPSCAYL_MODELS_DIR UPSCAYL_MODEL_NAME \
       UPSCAYL_SCALE PHOTOSHOP_APP_NAME BATCH_SIZE PS_RESTART_SLEEP \
       MIN_MOCKUPS_OK JPEG_QUALITY

NORDBLOOM_ROOT="${NORDBLOOM_ROOT:-$HOME/nordbloom_pipeline}"
VENV="$NORDBLOOM_ROOT/.venv"

if [ ! -x "$VENV/bin/python" ]; then
    echo "Error: venv not found at $VENV. Run ./setup.sh first."
    exit 1
fi

exec "$VENV/bin/python" "$SCRIPT_DIR/scripts/pipeline.py" "$@"
