#!/bin/bash
# ── MedCrypt Frontend Startup Script ─────────────────────────────────────────

set -e
cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       MedCrypt — Frontend (React)        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check Node.js
NODE=$(node --version 2>&1 || echo "NOT FOUND")
echo "[INFO] Node.js: $NODE"

if [[ "$NODE" == "NOT FOUND" ]]; then
  echo "[ERROR] Node.js is not installed."
  echo "        Download from: https://nodejs.org"
  exit 1
fi

# Install dependencies
echo "[SETUP] Installing npm packages..."
npm install --legacy-peer-deps

echo ""
echo "[START] Starting React dev server on http://localhost:3000"
echo "[INFO]  Make sure the backend is running on port 5000."
echo "[INFO]  Press Ctrl+C to stop."
echo ""

npm start