#!/usr/bin/env bash
# Mac / Linux: serve the app to phones on the same Wi-Fi.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r backend/requirements.txt
echo "Open on the phone (same Wi-Fi): http://$(hostname -I 2>/dev/null | awk '{print $1}' || ipconfig getifaddr en0):8000"
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
