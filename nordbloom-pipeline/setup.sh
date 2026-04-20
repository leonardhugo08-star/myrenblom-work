#!/bin/bash
# One-time setup for Nordbloom pipeline on macOS.
# - Creates ~/nordbloom_pipeline/ structure
# - Moves Desktop test folders into input/
# - Creates .venv and installs Python deps
# - Detects Upscayl CLI and Photoshop version
# - Writes config.env

set -eu

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
NORDBLOOM_ROOT="$HOME/nordbloom_pipeline"

echo "==> Nordbloom pipeline setup"
echo "    Pipeline scripts in: $SCRIPT_DIR"
echo "    Runtime data in:     $NORDBLOOM_ROOT"
echo

# -------------------------------------------------------------------
# 1. Create directory structure
# -------------------------------------------------------------------
echo "==> Creating directory structure"
mkdir -p "$NORDBLOOM_ROOT/input/posters"
mkdir -p "$NORDBLOOM_ROOT/input/mockups"
mkdir -p "$NORDBLOOM_ROOT/working"
mkdir -p "$NORDBLOOM_ROOT/output/upscaled_for_print"
mkdir -p "$NORDBLOOM_ROOT/output/mockups"
mkdir -p "$NORDBLOOM_ROOT/logs"
mkdir -p "$NORDBLOOM_ROOT/state"

# -------------------------------------------------------------------
# 2. Move Desktop folders into input/ (if present and input is empty)
# -------------------------------------------------------------------
move_desktop_content() {
    local src="$1"
    local dest="$2"
    local pattern="$3"

    if [ ! -d "$src" ]; then
        echo "    [skip] Desktop folder not found: $src"
        return 0
    fi

    # If dest already has files matching the pattern, don't touch anything.
    if compgen -G "$dest"/$pattern > /dev/null; then
        echo "    [skip] $dest already has $pattern files, leaving Desktop folder alone"
        return 0
    fi

    echo "    Moving $pattern files from:"
    echo "      $src"
    echo "    into:"
    echo "      $dest"
    # Use find to handle spaces / åäö safely
    find "$src" -maxdepth 1 -type f \( -iname "$pattern" \) -print0 | \
        xargs -0 -I {} mv "{}" "$dest/"

    # Remove the Desktop dir only if it ended up empty (avoid touching user's stuff).
    if [ -z "$(ls -A "$src" 2>/dev/null)" ]; then
        rmdir "$src" 2>/dev/null || true
        echo "    Removed empty source: $src"
    else
        echo "    Source still has non-matching files, leaving it."
    fi
}

echo "==> Moving Desktop files into input/"
move_desktop_content "$HOME/Desktop/Nya bilder test 4st" "$NORDBLOOM_ROOT/input/posters" "*.png"
move_desktop_content "$HOME/Desktop/Nya bilder"         "$NORDBLOOM_ROOT/input/posters" "*.png"
move_desktop_content "$HOME/Desktop/Mockups"            "$NORDBLOOM_ROOT/input/mockups" "*.psd"

POSTER_COUNT=$(find "$NORDBLOOM_ROOT/input/posters" -maxdepth 1 -type f -iname "*.png" | wc -l | tr -d ' ')
MOCKUP_COUNT=$(find "$NORDBLOOM_ROOT/input/mockups" -maxdepth 1 -type f -iname "*.psd" | wc -l | tr -d ' ')
echo "    Posters in input/:  $POSTER_COUNT"
echo "    Mockups in input/:  $MOCKUP_COUNT"

# -------------------------------------------------------------------
# 3. Python venv
# -------------------------------------------------------------------
echo "==> Python venv"
if [ ! -d "$NORDBLOOM_ROOT/.venv" ]; then
    python3 -m venv "$NORDBLOOM_ROOT/.venv"
    echo "    Created $NORDBLOOM_ROOT/.venv"
fi
"$NORDBLOOM_ROOT/.venv/bin/pip" install --quiet --upgrade pip
"$NORDBLOOM_ROOT/.venv/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "    Installed: $( "$NORDBLOOM_ROOT/.venv/bin/pip" freeze | tr '\n' ' ' )"

# -------------------------------------------------------------------
# 4. Detect Upscayl CLI
# -------------------------------------------------------------------
echo "==> Detecting Upscayl CLI"
UPSCAYL_BIN=""
UPSCAYL_MODELS_DIR=""

if [ -d "/Applications/Upscayl.app" ]; then
    # Try known paths inside the .app bundle.
    CANDIDATES=(
        "/Applications/Upscayl.app/Contents/Resources/bin/upscayl-bin"
        "/Applications/Upscayl.app/Contents/Resources/bin/upscayl"
        "/Applications/Upscayl.app/Contents/MacOS/upscayl-bin"
    )
    for c in "${CANDIDATES[@]}"; do
        if [ -x "$c" ]; then
            UPSCAYL_BIN="$c"
            break
        fi
    done
    # Fallback: search inside the bundle.
    if [ -z "$UPSCAYL_BIN" ]; then
        UPSCAYL_BIN=$(find "/Applications/Upscayl.app" -type f \( -name "upscayl-bin" -o -name "upscayl" \) -perm -u+x 2>/dev/null | head -1 || true)
    fi

    # Models dir inside the bundle.
    MODEL_CANDIDATES=(
        "/Applications/Upscayl.app/Contents/Resources/models"
        "/Applications/Upscayl.app/Contents/Resources/resources/models"
    )
    for c in "${MODEL_CANDIDATES[@]}"; do
        if [ -d "$c" ]; then
            UPSCAYL_MODELS_DIR="$c"
            break
        fi
    done
    if [ -z "$UPSCAYL_MODELS_DIR" ]; then
        UPSCAYL_MODELS_DIR=$(find "/Applications/Upscayl.app" -type d -name "models" 2>/dev/null | head -1 || true)
    fi
fi

# Fallback: Real-ESRGAN standalone (Homebrew)
if [ -z "$UPSCAYL_BIN" ]; then
    for c in \
        "/opt/homebrew/bin/realesrgan-ncnn-vulkan" \
        "/usr/local/bin/realesrgan-ncnn-vulkan" \
        "$(command -v realesrgan-ncnn-vulkan 2>/dev/null || true)" \
    ; do
        if [ -n "$c" ] && [ -x "$c" ]; then
            UPSCAYL_BIN="$c"
            break
        fi
    done
    if [ -n "$UPSCAYL_BIN" ] && [ -z "$UPSCAYL_MODELS_DIR" ]; then
        for c in \
            "/opt/homebrew/share/realesrgan-ncnn-vulkan/models" \
            "/usr/local/share/realesrgan-ncnn-vulkan/models" \
        ; do
            [ -d "$c" ] && UPSCAYL_MODELS_DIR="$c" && break
        done
    fi
fi

if [ -z "$UPSCAYL_BIN" ]; then
    echo "    [WARN] Upscayl CLI not found."
    echo "           Install Upscayl.app (https://upscayl.org) OR:"
    echo "             brew install realesrgan"
    echo "           Then re-run ./setup.sh"
else
    echo "    Binary:       $UPSCAYL_BIN"
    echo "    Models dir:   ${UPSCAYL_MODELS_DIR:-<none — binary may use a default>}"
fi

# -------------------------------------------------------------------
# 5. Detect Photoshop
# -------------------------------------------------------------------
echo "==> Detecting Photoshop"
PHOTOSHOP_APP_NAME=""
PHOTOSHOP_APP_PATH=""

# Prefer currently-running PS (user asked for "den som finns öppen")
RUNNING=$(osascript -e 'tell application "System Events" to get name of (processes whose name contains "Photoshop")' 2>/dev/null || true)
if [ -n "$RUNNING" ]; then
    # Pick first running PS name
    PHOTOSHOP_APP_NAME=$(echo "$RUNNING" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | grep -i "photoshop" | head -1)
    echo "    Found running: $PHOTOSHOP_APP_NAME"
fi

# If none running, scan /Applications for newest version.
if [ -z "$PHOTOSHOP_APP_NAME" ]; then
    # List all /Applications/Adobe Photoshop*.app by mtime, newest first.
    APPS=$(ls -dt /Applications/Adobe\ Photoshop*.app 2>/dev/null || true)
    if [ -n "$APPS" ]; then
        PHOTOSHOP_APP_PATH=$(echo "$APPS" | head -1)
        PHOTOSHOP_APP_NAME=$(basename "$PHOTOSHOP_APP_PATH" .app)
        echo "    Found installed: $PHOTOSHOP_APP_NAME  ($PHOTOSHOP_APP_PATH)"
    fi
fi

if [ -z "$PHOTOSHOP_APP_NAME" ]; then
    echo "    [WARN] Photoshop not found in /Applications/ and none currently running."
    echo "           Edit config.env manually and set PHOTOSHOP_APP_NAME."
fi

# -------------------------------------------------------------------
# 6. Write config.env
# -------------------------------------------------------------------
CONFIG_FILE="$SCRIPT_DIR/config.env"
echo "==> Writing $CONFIG_FILE"
cat > "$CONFIG_FILE" <<EOF
# Generated by setup.sh on $(date)
# Edit manually to override detected values.

NORDBLOOM_ROOT="$NORDBLOOM_ROOT"

UPSCAYL_BIN="$UPSCAYL_BIN"
UPSCAYL_MODELS_DIR="$UPSCAYL_MODELS_DIR"
UPSCAYL_MODEL_NAME="realesrgan-x4plus"
UPSCAYL_SCALE=4

PHOTOSHOP_APP_NAME="$PHOTOSHOP_APP_NAME"

BATCH_SIZE=3
PS_RESTART_SLEEP=10
MIN_MOCKUPS_OK=8
JPEG_QUALITY=95
EOF

echo
echo "==> Setup done."
echo "    Review $CONFIG_FILE and edit if needed."
echo "    Then run: ./run_pipeline.sh"
