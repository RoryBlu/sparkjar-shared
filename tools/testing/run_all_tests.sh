#!/bin/bash

# Script to run all tests with proper Python path configuration

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Export Python path - order matters!
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/services/crew-api:$PROJECT_ROOT/services/memory-service:$PROJECT_ROOT/services/mcp-registry:$PROJECT_ROOT/shared:$PYTHONPATH"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Change to project root
cd "$PROJECT_ROOT"

echo "Running all tests with proper Python paths"
echo "=========================================="
echo "PROJECT_ROOT: $PROJECT_ROOT"
echo "PYTHONPATH: $PYTHONPATH"
echo ""

# Install test requirements if needed
if [ ! -d ".venv" ] && [ ! -d "venv" ]; then
    echo "⚠️  No virtual environment found. Please create one first."
    exit 1
fi

# Run pytest with configuration
if [ -f ".venv/bin/pytest" ]; then
    .venv/bin/pytest -v --tb=short "$@"
elif [ -f "venv/bin/pytest" ]; then
    venv/bin/pytest -v --tb=short "$@"
else
    pytest -v --tb=short "$@"
fi