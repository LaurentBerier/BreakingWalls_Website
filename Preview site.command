#!/bin/bash
# Double-click to preview the Breaking Walls site locally. Close this window to stop.
cd "$(dirname "$0")/site" || exit 1
PORT=8000
while lsof -i :$PORT >/dev/null 2>&1; do PORT=$((PORT+1)); done
echo "Breaking Walls site running at http://localhost:$PORT/home/"
echo "Close this window (or press Ctrl+C) to stop it."
( sleep 1; open "http://localhost:$PORT/home/" ) &
python3 -m http.server $PORT
