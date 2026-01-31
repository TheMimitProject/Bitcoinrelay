#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════════
# Bitcoin Relay - Startup Script
# ═══════════════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${YELLOW}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║    ██████╗ ██╗████████╗ ██████╗ ██████╗ ██╗███╗   ██╗                        ║
║    ██╔══██╗██║╚══██╔══╝██╔════╝██╔═══██╗██║████╗  ██║                        ║
║    ██████╔╝██║   ██║   ██║     ██║   ██║██║██╔██╗ ██║                        ║
║    ██╔══██╗██║   ██║   ██║     ██║   ██║██║██║╚██╗██║                        ║
║    ██████╔╝██║   ██║   ╚██████╗╚██████╔╝██║██║ ╚████║                        ║
║    ╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝                        ║
║                                                                               ║
║    ██████╗ ███████╗██╗      █████╗ ██╗   ██╗                                 ║
║    ██╔══██╗██╔════╝██║     ██╔══██╗╚██╗ ██╔╝                                 ║
║    ██████╔╝█████╗  ██║     ███████║ ╚████╔╝                                  ║
║    ██╔══██╗██╔══╝  ██║     ██╔══██║  ╚██╔╝                                   ║
║    ██║  ██║███████╗███████╗██║  ██║   ██║                                    ║
║    ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝   ╚═╝                                    ║
║                                                                               ║
║                    Personal Bitcoin Privacy Tool                              ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check for Python
echo -e "${BLUE}Checking requirements...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    echo "Please install Python 3.8 or higher from https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "  ✓ Python $PYTHON_VERSION found"

# Check for pip
if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
    echo -e "${RED}Error: pip is required but not installed.${NC}"
    exit 1
fi
echo -e "  ✓ pip found"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "\n${BLUE}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "  ✓ Virtual environment created"
fi

# Activate virtual environment
echo -e "\n${BLUE}Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "  ✓ Virtual environment activated"

# Install/update dependencies
echo -e "\n${BLUE}Installing dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "  ✓ Dependencies installed"

# Initialize database
echo -e "\n${BLUE}Initializing database...${NC}"
python3 -c "from src.database import init_database; init_database()"
echo -e "  ✓ Database initialized"

# Start message
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${GREEN}Starting Bitcoin Relay...${NC}"
echo ""
echo -e "  ${CYAN}Access the web interface at:${NC}"
echo -e "  ${YELLOW}➜  http://localhost:5000${NC}"
echo ""
echo -e "  ${RED}⚠️  WARNING: Always start on TESTNET first!${NC}"
echo -e "  ${RED}⚠️  Test with small amounts before using mainnet.${NC}"
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo ""

# Run the application
python3 -m src.app
