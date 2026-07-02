#!/bin/bash -e
# Install Python dependencies into the venv the service actually runs
# (ExecStart=/opt/openavc/venv/bin/python, Restart=always). The install must
# succeed into THAT venv or the build must fail: any fallback that lands the
# packages elsewhere (e.g. system site-packages) leaves the isolated venv
# empty and ships an image whose server crash-loops on import at first boot.

OPENAVC_DIR="/opt/openavc"
VENV_DIR="$OPENAVC_DIR/venv"

if [ ! -f "$OPENAVC_DIR/requirements.txt" ]; then
    echo "FATAL: no requirements.txt at $OPENAVC_DIR — server archive incomplete"
    exit 1
fi

echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --no-cache-dir -r "$OPENAVC_DIR/requirements.txt"
echo "Python dependencies installed."
