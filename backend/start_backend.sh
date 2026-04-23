#!/bin/bash
# ── MedCrypt Backend Startup Script ──────────────────────────────────────────

set -e
cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       MedCrypt — Backend Server          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check Python version
PY=$(python3 --version 2>&1)
echo "[INFO] Using: $PY"

# Create and activate virtual environment if not present
if [ ! -d "venv" ]; then
  echo "[SETUP] Creating virtual environment..."
  python3 -m venv venv
fi

echo "[SETUP] Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "[SETUP] Installing dependencies (this may take a few minutes)..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "[START] Starting Flask server on http://localhost:5000"
echo "[INFO]  Press Ctrl+C to stop."
echo ""

python app.py