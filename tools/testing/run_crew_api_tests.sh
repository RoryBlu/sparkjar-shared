#!/bin/bash
# Run crew-api tests from any directory.
#
# Usage:
#   ./run_crew_api_tests.sh [pytest options]
#
# The script loads environment variables from `.env` at the repository root,
# adds the crew-api service to PYTHONPATH, and then runs the test suite.
#
# Example:
#   ./run_crew_api_tests.sh -k some_test

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"

# Load environment variables if .env exists
if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  source "$REPO_ROOT/.env"
  set +a
fi

export PYTHONPATH="$REPO_ROOT/services/crew-api:$PYTHONPATH"

cd "$REPO_ROOT"
echo "🧪 Running crew-api tests..."
"$REPO_ROOT/.venv/bin/python" -m pytest tests/ -v "$@"

