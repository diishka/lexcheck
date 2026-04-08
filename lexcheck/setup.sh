#!/bin/bash
# LexCheck UZ - Cross-platform setup script with dependency installer
set -e

# Detect OS
detect_os() {
    case "$OSTYPE" in
        darwin*)  echo "macos" ;;
        linux*)   echo "linux" ;;
        msys*|cygwin*|mingw*) echo "windows" ;;
        *)        echo "unknown" ;;
    esac
}

OS=$(detect_os)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
DB_NAME="${DB_NAME:-lexai}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

AUTO_INSTALL=false
SKIP_CHECKS=false
for arg in "$@"; do
    case $arg in
        --auto-install|-y) AUTO_INSTALL=true ;;
        --skip-checks) SKIP_CHECKS=true ;;
        --help|-h)
            echo "Usage: ./setup.sh [OPTIONS]"
            echo "  -y, --auto-install    Auto-install missing dependencies"
            echo "  --skip-checks         Skip dependency checks"
            exit 0 ;;
    esac
done

echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}   LexCheck UZ — Cross-platform Setup${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${YELLOW}Detected OS: ${OS}${NC}\n"

confirm() {
    local prompt="$1"
    local default="${2:-n}"
    if [ "$AUTO_INSTALL" = true ]; then return 0; fi
    if [ "$default" = "y" ]; then prompt="$prompt [Y/n]: "; else prompt="$prompt [y/N]: "; fi
    read -p "$prompt" -r response
    response=${response:-$default}
    [[ "$response" =~ ^[Yy] ]]
}

# PostgreSQL helpers
run_psql() {
    if [ "$OS" = "windows" ]; then
        psql "$@"
    elif [ "$OS" = "macos" ]; then
        psql "$@" 2>/dev/null || sudo -u postgres psql "$@"
    else
        sudo -u postgres psql "$@"
    fi
}
run_psql_admin() {
    if [ "$OS" = "windows" ]; then
        psql -U postgres "$@" 2>/dev/null || psql "$@"
    elif [ "$OS" = "macos" ]; then
        psql postgres "$@" 2>/dev/null || sudo -u postgres psql "$@"
    else
        sudo -u postgres psql "$@"
    fi
}

# ---------- DEPENDENCY CHECKERS & INSTALLERS ----------
check_and_install_python() {
    echo -e "${CYAN}🐍 Checking Python 3...${NC}"
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD="python3"
        echo -e "  ${GREEN}✅ $(python3 --version)${NC}"
        return 0
    elif command -v python >/dev/null 2>&1 && [[ $(python --version 2>&1) > "Python 3" ]]; then
        PYTHON_CMD="python"
        alias python3=python
        echo -e "  ${GREEN}✅ $(python --version)${NC}"
        return 0
    fi
    echo -e "  ${RED}❌ Python 3 not found${NC}"
    if confirm "Install Python 3?"; then
        case "$OS" in
            macos) brew install python@3.11 ;;
            linux)
                if command -v apt-get >/dev/null; then
                    sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
                elif command -v yum >/dev/null; then
                    sudo yum install -y python3 python3-pip
                elif command -v dnf >/dev/null; then
                    sudo dnf install -y python3 python3-pip
                elif command -v pacman >/dev/null; then
                    sudo pacman -S --noconfirm python python-pip
                else
                    echo -e "  ${RED}Unknown package manager${NC}"; return 1
                fi ;;
            windows) echo -e "  ${YELLOW}Download from https://python.org${NC}"; return 1 ;;
        esac
        PYTHON_CMD="python3"
        echo -e "  ${GREEN}✅ Installed${NC}"
        return 0
    fi
    return 1
}

check_and_install_node() {
    echo -e "${CYAN}📦 Checking Node.js...${NC}"
    if command -v node >/dev/null; then
        echo -e "  ${GREEN}✅ Node $(node --version)${NC}"
        PACKAGE_MANAGER=$(command -v yarn >/dev/null && echo "yarn" || echo "npm")
        return 0
    fi
    echo -e "  ${RED}❌ Node.js not found${NC}"
    if confirm "Install Node.js?"; then
        case "$OS" in
            macos) brew install node ;;
            linux)
                curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
                sudo apt-get install -y nodejs ;;
            windows) echo -e "  ${YELLOW}Download from https://nodejs.org${NC}"; return 1 ;;
        esac
        PACKAGE_MANAGER="npm"
        echo -e "  ${GREEN}✅ Installed${NC}"
        return 0
    fi
    return 1
}

check_and_install_postgres() {
    echo -e "${CYAN}🐘 Checking PostgreSQL...${NC}"
    if command -v psql >/dev/null; then
        echo -e "  ${GREEN}✅ $(psql --version | head -1)${NC}"
        if check_postgres_running; then
            echo -e "  ${GREEN}✅ Server running${NC}"
        else
            echo -e "  ${YELLOW}⚠️ Server not running${NC}"
            start_postgres_server
        fi
        return 0
    fi
    echo -e "  ${RED}❌ PostgreSQL not found${NC}"
    if confirm "Install PostgreSQL?"; then
        case "$OS" in
            macos) brew install postgresql@15 && brew services start postgresql@15 ;;
            linux)
                if command -v apt-get >/dev/null; then
                    sudo apt-get update && sudo apt-get install -y postgresql postgresql-contrib
                    sudo systemctl start postgresql && sudo systemctl enable postgresql
                elif command -v yum >/dev/null; then
                    sudo yum install -y postgresql-server postgresql-contrib
                    sudo postgresql-setup initdb
                    sudo systemctl start postgresql && sudo systemctl enable postgresql
                elif command -v dnf >/dev/null; then
                    sudo dnf install -y postgresql-server postgresql-contrib
                    sudo postgresql-setup --initdb
                    sudo systemctl start postgresql && sudo systemctl enable postgresql
                elif command -v pacman >/dev/null; then
                    sudo pacman -S --noconfirm postgresql
                    sudo -u postgres initdb -D /var/lib/postgres/data
                    sudo systemctl start postgresql && sudo systemctl enable postgresql
                else
                    echo -e "  ${RED}Unknown package manager${NC}"; return 1
                fi ;;
            windows) echo -e "  ${YELLOW}Download from https://postgresql.org${NC}"; return 1 ;;
        esac
        sleep 3
        echo -e "  ${GREEN}✅ Installed${NC}"
        return 0
    fi
    return 1
}

check_postgres_running() {
    case "$OS" in
        windows) pg_isready -q 2>/dev/null ;;
        macos) pg_isready -q 2>/dev/null || brew services list 2>/dev/null | grep postgresql | grep started >/dev/null ;;
        linux) systemctl is-active --quiet postgresql 2>/dev/null || pg_isready -q 2>/dev/null ;;
    esac
}

start_postgres_server() {
    echo -e "  ${YELLOW}Starting PostgreSQL...${NC}"
    case "$OS" in
        windows) net start postgresql-x64-15 2>/dev/null || net start postgresql 2>/dev/null ;;
        macos) brew services start postgresql 2>/dev/null || brew services start postgresql@15 2>/dev/null || pg_ctl -D /usr/local/var/postgres start 2>/dev/null ;;
        linux) sudo systemctl start postgresql 2>/dev/null || sudo service postgresql start 2>/dev/null ;;
    esac
    sleep 2
    check_postgres_running && echo -e "  ${GREEN}✅ Started${NC}" || echo -e "  ${RED}Failed to start${NC}"
}

check_and_install_ollama() {
    echo -e "${CYAN}🤖 Checking Ollama...${NC}"
    if command -v ollama >/dev/null; then
        echo -e "  ${GREEN}✅ $(ollama --version)${NC}"
        if curl -s http://localhost:11434/api/tags >/dev/null; then
            echo -e "  ${GREEN}✅ Service running${NC}"
            if ! curl -s http://localhost:11434/api/tags | grep -q "qwen2.5"; then
                if confirm "Pull qwen2.5:7b model (~4.4GB)?"; then
                    ollama pull qwen2.5:7b
                fi
            fi
        else
            start_ollama_service
        fi
        return 0
    fi
    echo -e "  ${YELLOW}⚠️ Ollama not found (optional)${NC}"
    if confirm "Install Ollama?"; then
        case "$OS" in
            macos|linux) curl -fsSL https://ollama.com/install.sh | sh ;;
            windows) echo -e "  ${YELLOW}Download from https://ollama.com${NC}"; return 0 ;;
        esac
        start_ollama_service
        if confirm "Pull qwen2.5:7b?"; then ollama pull qwen2.5:7b; fi
        return 0
    fi
    return 0
}

start_ollama_service() {
    if curl -s http://localhost:11434/api/tags >/dev/null; then return; fi
    echo -e "  ${YELLOW}Starting Ollama...${NC}"
    if [ "$OS" = "windows" ]; then
        start ollama serve
    else
        nohup ollama serve > /tmp/ollama.log 2>&1 &
    fi
    sleep 3
    curl -s http://localhost:11434/api/tags >/dev/null && echo -e "  ${GREEN}✅ Started${NC}" || echo -e "  ${YELLOW}Start manually: ollama serve${NC}"
}

check_and_install_git() {
    echo -e "${CYAN}📂 Checking Git...${NC}"
    if command -v git >/dev/null; then
        echo -e "  ${GREEN}✅ $(git --version)${NC}"
        return 0
    fi
    echo -e "  ${YELLOW}Git not found${NC}"
    if confirm "Install Git?"; then
        case "$OS" in
            macos) brew install git ;;
            linux) sudo apt-get update && sudo apt-get install -y git ;;
            windows) echo -e "  ${YELLOW}Download from https://git-scm.com${NC}" ;;
        esac
    fi
    return 0
}

# ---------- SETUP STEPS ----------
setup_database() {
    echo -e "\n${BLUE}1️⃣  PostgreSQL database${NC}"
    if run_psql_admin -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
        echo -e "   ${GREEN}✅ Database '$DB_NAME' exists${NC}"
    else
        echo -e "   Creating '$DB_NAME'..."
        run_psql_admin -c "CREATE DATABASE $DB_NAME;" 2>/dev/null && echo -e "   ${GREEN}✅ Created${NC}" || echo -e "   ${RED}❌ Failed${NC}"
    fi
    if run_psql -d "$DB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name = 'laws'" 2>/dev/null | grep -q 1; then
        echo -e "   ${GREEN}✅ Tables exist${NC}"
    else
        echo -e "   ${YELLOW}ℹ️  No tables – import backup: ${CYAN}./scripts/db_import.sh backups/<file>.dump${NC}"
    fi
}

setup_backend() {
    echo -e "\n${BLUE}2️⃣  Python backend${NC}"
    cd "$BACKEND_DIR"
    if [ ! -d "venv" ]; then
        $PYTHON_CMD -m venv venv
        echo -e "   ${GREEN}✅ venv created${NC}"
    else
        echo -e "   ${YELLOW}ℹ️  venv exists${NC}"
    fi
    if [ "$OS" = "windows" ]; then source venv/Scripts/activate; else source venv/bin/activate; fi
    echo -e "   Installing packages..."
    pip install --upgrade pip -q
    if [ -f "$ROOT_DIR/requirements.txt" ]; then
        pip install -r "$ROOT_DIR/requirements.txt" -q
    else
        pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic python-dotenv -q
    fi
    echo -e "   ${GREEN}✅ Packages installed${NC}"

    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}|" .env
            rm -f .env.bak
            echo -e "   ${GREEN}✅ .env from .env.example${NC}"
        else
            cat > .env <<EOF
# Database
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
ACTIVE_DOCUMENT_LIMIT=20

# LLM Provider
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# Chat & Context
CHAT_TOP_K=2
CHAT_HISTORY_LIMIT=2
CHAT_CONTEXT_SUMMARY_CHARS=50
CHAT_CONTEXT_ARTICLE_CHARS=60
CHAT_CONTEXT_ARTICLES_PER_LAW=1
CHAT_LAW_CONTEXT_MAX_CHARS=900
CHAT_REPLY_CACHE_TTL=120
CHAT_REPLY_CACHE_MAX=200
PERSISTENT_CACHE_ENABLED=true
PERSISTENT_CACHE_MAX_ROWS=2000
PERSISTENT_CHAT_CACHE_TTL=43200
PERSISTENT_ANALYZE_CACHE_TTL=43200
PERSISTENT_TRANSLATE_CACHE_TTL=2592000
CHAT_CACHE_VERSION=11
ANALYZE_CACHE_VERSION=3

# Analyze
ANALYZE_TOP_K=2
ANALYZE_REPLY_CACHE_TTL=300
ANALYZE_REPLY_CACHE_MAX=100

# Law context
LAW_CONTEXT_TITLE_CHARS=180
CANDIDATE_CACHE_TTL=120
CANDIDATE_CACHE_MAX=500
CANDIDATE_ARTICLES_PER_LAW=4
UI_TITLE_MAX_CHARS=220
UI_SUMMARY_MAX_CHARS=420
CHAT_MAX_TOKENS=96
ANALYZE_MAX_TOKENS=520
OLLAMA_NUM_CTX=2048
OLLAMA_CHAT_NUM_CTX=768
OLLAMA_ANALYZE_NUM_CTX=2048
OLLAMA_READ_TIMEOUT=420
OLLAMA_WRITE_TIMEOUT=60
OLLAMA_RETRY_NUM_CTX=512
OLLAMA_RETRY_MAX_TOKENS=160
OLLAMA_KEEP_ALIVE=15m

# Server
HOST=0.0.0.0
PORT=8000
RELOAD=true
SECRET_KEY=dev-secret-key-change-in-production
EOF
            echo -e "   ${GREEN}✅ .env created with defaults${NC}"
        fi
    else
        echo -e "   ${YELLOW}ℹ️  .env already exists${NC}"
    fi
    cd "$SCRIPT_DIR"
    echo -e "   ${GREEN}✅ Backend ready${NC}"
}

setup_frontend() {
    echo -e "\n${BLUE}3️⃣  React frontend${NC}"
    cd "$FRONTEND_DIR"
    if [ ! -f "package.json" ]; then
        echo -e "   ${RED}❌ package.json not found${NC}"
        return 1
    fi
    $PACKAGE_MANAGER install --silent 2>/dev/null || $PACKAGE_MANAGER install
    [ -f .env.example ] && [ ! -f .env ] && cp .env.example .env
    cd "$SCRIPT_DIR"
    echo -e "   ${GREEN}✅ Frontend ready${NC}"
}

fix_permissions() {
    echo -e "\n${BLUE}🔧 Setting execute permissions...${NC}"
    chmod +x "$ROOT_DIR/run.sh" 2>/dev/null || true
    chmod +x "$SCRIPT_DIR"/../scripts/*.sh 2>/dev/null || true
    echo -e "   ${GREEN}✅ Scripts are executable${NC}"
}

# ---------- MAIN ----------
main() {
    if [ "$SKIP_CHECKS" = false ]; then
        echo -e "${BLUE}═══════════════════════════════════════════${NC}"
        echo -e "${BLUE}   Checking Dependencies${NC}"
        echo -e "${BLUE}═══════════════════════════════════════════${NC}\n"
        check_and_install_python || exit 1
        check_and_install_node || exit 1
        check_and_install_postgres || exit 1
        check_and_install_ollama
        check_and_install_git
        echo -e "\n${GREEN}✅ Dependencies satisfied${NC}"
    fi

    echo -e "\n${BLUE}═══════════════════════════════════════════${NC}"
    echo -e "${BLUE}   Setting Up LexCheck UZ${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════${NC}"
    setup_database
    setup_backend
    setup_frontend
    fix_permissions

    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    echo -e "${GREEN}   ✅ Setup Complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BLUE}🚀 Start: ${CYAN}./run.sh${NC}"
    echo -e "${BLUE}📝 Access:${NC}"
    echo -e "   • Frontend: ${CYAN}http://localhost:3000${NC}"
    echo -e "   • Backend:  ${CYAN}http://localhost:8000${NC}"
    echo -e "   • API Docs: ${CYAN}http://localhost:8000/docs${NC}"
    echo ""
    echo -e "${BLUE}📦 Database:${NC}"
    echo -e "   • Export: ${CYAN}./scripts/db_export.sh${NC}"
    echo -e "   • Import: ${CYAN}./scripts/db_import.sh backups/lexai_YYYYMMDD_HHMMSS.dump${NC}"
    echo ""
    if command -v ollama >/dev/null; then
        if curl -s http://localhost:11434/api/tags | grep -q "qwen2.5"; then
            echo -e "${GREEN}✅ Ollama ready with qwen2.5:7b${NC}"
        else
            echo -e "${YELLOW}⚠️  Run: ollama pull qwen2.5:7b${NC}"
        fi
    fi
    echo -e "\n${BLUE}📖 Full docs: README.md${NC}"
}

main