#!/bin/bash
# Run the cheap E2E smoke test
# Cost: ~$0.02-0.05 on DeepSeek
# Time: ~3-5 minutes

set -e
cd "$(dirname "$0")/.."

echo "Running E2E smoke test (cheapest preset, 5 rounds)..."
echo "Estimated cost: ~$0.02-0.05"
echo ""

# Source .env if exists
if [ -f MiroFish/.env ]; then
    export $(grep -v '^#' MiroFish/.env | xargs)
fi

# Override to cheapest config
export PIPELINE_PRESET=cheapest
export MAX_SIMULATION_ROUNDS=5

cd MiroFish/backend
PYTHONPATH=../.. .venv/bin/python -m pytest \
    ../../polymarket_predictor/tests/test_e2e_smoke.py \
    -m e2e -v --tb=short --log-cli-level=INFO \
    "$@"
