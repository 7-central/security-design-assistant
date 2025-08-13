#!/bin/bash

# Start mypy daemon for instant type checking feedback
# This provides near-instant type checking results after the first run

echo "Starting mypy daemon for instant feedback..."
echo "==========================================="
echo ""

# Kill any existing daemon
dmypy stop 2>/dev/null || true

# Start the daemon with our project settings
dmypy start -- --strict --ignore-missing-imports --show-error-codes --pretty

echo "✅ Mypy daemon started!"
echo ""
echo "Usage:"
echo "  Quick check: dmypy check src"
echo "  Status:      dmypy status"
echo "  Stop:        dmypy stop"
echo ""
echo "The daemon will provide instant feedback after the first run."