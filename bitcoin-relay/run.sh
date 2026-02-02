#!/bin/bash

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              Bitcoin Relay - Privacy Tool                     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required. Install from https://www.python.org/"
    exit 1
fi
echo "✓ Python 3 found"

# Create venv if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate
echo "✓ Virtual environment activated"

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Initialize database
python3 -c "from src.database import init_database; init_database()"
echo "✓ Database initialized"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "  Starting Bitcoin Relay..."
echo ""
echo "  ➜  Open http://localhost:5000 in your browser"
echo ""
echo "  ⚠️  Always start on TESTNET first!"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""

python3 -m src.app
