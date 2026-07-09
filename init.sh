#!/bin/bash
#
# YOLO-Forge SP — 一键初始化脚本
# 从解压到可运行的完整流程
#
# 使用方法:
#   chmod +x init.sh
#   ./init.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

STEP=0

step() {
    STEP=$((STEP + 1))
    echo ""
    echo "${CYAN}━━━ 步骤 ${STEP}: $1 ━━━${NC}"
    echo ""
}

ok() {
    echo "  ${GREEN}✓ $1${NC}"
}

warn() {
    echo "  ${YELLOW}⚠ $1${NC}"
}

fail() {
    echo "  ${RED}✗ $1${NC}"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "╔══════════════════════════════════════╗"
echo "║   YOLO-Forge SP  一键初始化         ║"
echo "║   v1.0.0-sp                         ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ─── Step 1: 检查 Node.js ───
step "检查 Node.js"
if command -v node &> /dev/null; then
    NODE_VER=$(node --version)
    ok "Node.js ${NODE_VER} 已安装"
    NPM_VER=$(npm --version)
    ok "npm ${NPM_VER}"
else
    fail "Node.js 未安装!"
    echo ""
    echo "  请先安装 Node.js 20.x LTS:"
    echo "  → https://nodejs.org/"
    echo "  → 或使用 nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
    echo "  → 然后: nvm install 20 && nvm use 20"
    exit 1
fi

# ─── Step 2: 检查 Python ───
step "检查 Python"
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    ok "python3 $(python3 --version | cut -d' ' -f2)"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    ok "python $(python --version | cut -d' ' -f2)"
else
    warn "Python 未安装，YOLO功能将使用Mock模式"
    echo "  建议安装 Python 3.11+:"
    echo "  → https://www.python.org/downloads/"
fi

# ─── Step 3: 安装 Node.js 依赖 ───
step "安装 Node.js 依赖 (npm install)"
npm install
ok "Node.js 依赖安装完成"

# ─── Step 4: 安装 Python 依赖 ───
step "安装 Python 依赖"
if [ -n "$PYTHON_CMD" ]; then
    PIP_CMD=""
    if command -v pip3 &> /dev/null; then
        PIP_CMD="pip3"
    elif command -v pip &> /dev/null; then
        PIP_CMD="pip"
    fi

    if [ -n "$PIP_CMD" ]; then
        echo "  正在安装 Python 依赖 (可能需要几分钟)..."
        $PIP_CMD install -r electron/python/requirements.txt 2>&1 | tail -3
        ok "Python 依赖安装完成"
    else
        warn "pip 未找到，请手动安装:"
        echo "  pip install -r electron/python/requirements.txt"
    fi
else
    warn "跳过 Python 依赖安装"
fi

# ─── Step 5: 验证 Python Worker ───
step "验证 Python Worker"
if [ -n "$PYTHON_CMD" ]; then
    WORKER_RESULT=$($PYTHON_CMD -c "
import sys, json
sys.path.insert(0, 'electron/python')
from worker import HANDLERS
print(json.dumps({'handlers': list(HANDLERS.keys()), 'count': len(HANDLERS)}))
" 2>&1)

    if echo "$WORKER_RESULT" | grep -q '"count"'; then
        ok "Python Worker 正常: $(echo $WORKER_RESULT | $PYTHON_CMD -c 'import sys,json; d=json.load(sys.stdin); print(f"{d[\"count\"]}个处理器: {\", \".join(d[\"handlers\"])}")' 2>/dev/null || echo "$WORKER_RESULT")"
    else
        warn "Python Worker 部分功能不可用 (缺少依赖)"
        echo "  输出: $WORKER_RESULT"
    fi
else
    warn "跳过 Python Worker 验证"
fi

# ─── Step 6: 构建 Vite 前端 ───
step "构建前端 (vite build)"
npx vite build 2>&1 | tail -5
if [ -d "dist/renderer" ]; then
    ok "前端构建成功: dist/renderer/"
else
    fail "前端构建失败"
    echo "  尝试手动运行: npx vite build"
fi

# ─── Step 7: 构建 Electron 主进程 ───
step "构建 Electron 主进程"
npx tsc -p tsconfig.electron.json 2>&1 | head -20
if [ -d "dist/electron" ]; then
    ok "主进程构建成功: dist/electron/"
else
    warn "主进程构建有错误 (可能需要修复TypeScript问题)"
    echo "  不影响开发模式运行"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "╔══════════════════════════════════════╗"
echo "║   🎉 初始化完成！                    ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  接下来运行:"
echo ""
echo "  ${GREEN}开发模式:${NC}"
echo "    npm run electron:dev"
echo ""
echo "  ${GREEN}生产构建:${NC}"
echo "    npm run electron:build"
echo ""
echo "  ${GREEN}仅前端开发:${NC}"
echo "    npm run dev"
echo "    → 然后浏览器打开 http://localhost:5173"
echo ""
