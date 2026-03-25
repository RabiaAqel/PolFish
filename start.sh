#!/bin/bash
# Start PolFish (MiroFish + Polymarket Predictor)
# Usage: ./start.sh

echo "🐟 Starting PolFish..."

# Kill any existing processes on these ports
lsof -i :5001 -t 2>/dev/null | xargs kill 2>/dev/null
lsof -i :3000 -t 2>/dev/null | xargs kill 2>/dev/null
sleep 1

DIR="$(cd "$(dirname "$0")" && pwd)"

# Start backend
cd "$DIR/MiroFish/backend"
.venv/bin/python -c "
from app import create_app
app = create_app()
app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
" &
BE_PID=$!

# Start frontend
cd "$DIR/MiroFish/frontend"
npx vite --port 3000 &
FE_PID=$!

echo ""
echo "  Backend:  http://localhost:5001  (PID $BE_PID)"
echo "  Frontend: http://localhost:3000  (PID $FE_PID)"
echo ""
echo "  Press Ctrl+C to stop both."
echo ""

# Trap Ctrl+C to kill both
trap "kill $BE_PID $FE_PID 2>/dev/null; echo ''; echo 'Stopped.'; exit 0" INT TERM

# Wait for either to exit
wait
