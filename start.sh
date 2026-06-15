#!/bin/bash
cd "$(dirname "$0")"

# Start Python backend (port 3001)
python3 server.py &
BACKEND_PID=$!

# Start static frontend (port 3000)
python3 -m http.server 3000 &
FRONTEND_PID=$!

echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:3001"
echo "Admin:    http://localhost:3001/admin?token=ampypay-admin-2024"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
