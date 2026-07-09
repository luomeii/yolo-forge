#!/usr/bin/env bash
#
# YOLO-Forge SP — Development Setup & Validation Script
#
# Usage: chmod +x scripts/setup.sh && ./scripts/setup.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "═══════════════════════════════════════"
echo "  YOLO-Forge SP — Setup & Validation"
echo "═══════════════════════════════════════"
echo ""

# ─── 1. Check Node.js ───
echo "📋 Checking Node.js..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "   ${GREEN}✓ Node.js ${NODE_VERSION}${NC}"
else
    echo "   ${RED}✗ Node.js not found. Install from https://nodejs.org/${NC}"
    exit 1
fi

# ─── 2. Check Python ───
echo "📋 Checking Python..."
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version)
    echo "   ${GREEN}✓ ${PY_VERSION}${NC}"
elif command -v python &> /dev/null; then
    PY_VERSION=$(python --version)
    echo "   ${GREEN}✓ ${PY_VERSION}${NC}"
else
    echo "   ${YELLOW}⚠ Python not found. YOLO features will use mock mode.${NC}"
fi

# ─── 3. Install Node.js dependencies ───
echo "📦 Installing Node.js dependencies..."
npm install
echo "   ${GREEN}✓ npm install complete${NC}"

# ─── 4. Install Python dependencies ───
echo "📦 Installing Python dependencies..."
if command -v pip3 &> /dev/null; then
    pip3 install -r electron/python/requirements.txt 2>/dev/null && \
        echo "   ${GREEN}✓ Python dependencies installed${NC}" || \
        echo "   ${YELLOW}⚠ Some Python dependencies failed (optional)${NC}"
elif command -v pip &> /dev/null; then
    pip install -r electron/python/requirements.txt 2>/dev/null && \
        echo "   ${GREEN}✓ Python dependencies installed${NC}" || \
        echo "   ${YELLOW}⚠ Some Python dependencies failed (optional)${NC}"
else
    echo "   ${YELLOW}⚠ pip not found. Install manually: pip install -r electron/python/requirements.txt${NC}"
fi

# ─── 5. Validate Python worker ───
echo "🔍 Validating Python worker..."
if command -v python3 &> /dev/null; then
    python3 -c "
import sys
sys.path.insert(0, 'electron/python')
from worker import handle_inspect, handle_convert, HANDLERS
print(f'  Worker OK: {len(HANDLERS)} handlers registered')
" 2>/dev/null && echo "   ${GREEN}✓ Python worker validated${NC}" || \
    echo "   ${YELLOW}⚠ Python worker has import issues (some deps missing)${NC}"
fi

# ─── 6. Build test ───
echo "🔨 Testing Vite build..."
npx vite build 2>/dev/null && \
    echo "   ${GREEN}✓ Vite build successful${NC}" || \
    echo "   ${RED}✗ Vite build failed${NC}"

echo ""
echo "═══════════════════════════════════════"
echo "  Setup Complete!"
echo ""
echo "  To start development:"
echo "    npm run electron:dev"
echo ""
echo "  To build for production:"
echo "    npm run electron:build"
echo "═══════════════════════════════════════"
