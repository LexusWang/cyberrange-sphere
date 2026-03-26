#!/usr/bin/env bash
# ============================================================================
# SambaCry Lab — Attacker Machine Setup
# ============================================================================
# Installs all dependencies needed to run sambacry_attack.py on a minimal
# Kali image (SPHERE cyber range).
#
# Usage:  sudo bash setup_sambacry.sh
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}[✔]${NC} $1"; }
info() { echo -e "  ${CYAN}[*]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[!]${NC} $1"; }
fail() { echo -e "  ${RED}[✘]${NC} $1"; exit 1; }

# ── Must run as root ────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    fail "This script must be run as root (use sudo)"
fi

REAL_USER="${SUDO_USER:-$(whoami)}"
REAL_HOME=$(eval echo "~${REAL_USER}")

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  SambaCry Lab — Attacker Machine Setup               ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. System packages ─────────────────────────────────────────────────────
info "Updating apt cache..."
apt-get update -qq

PACKAGES=(
    # Core tools
    python3
    python3-pip
    python3-venv
    curl
    nmap
    # SMB tools
    smbclient
    smbmap
    enum4linux
    # Netcat (reverse shell listener)
    ncat
    # fuser (to kill processes on ports)
    psmisc
    # iproute2 (ss command)
    iproute2
)

info "Installing system packages..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${PACKAGES[@]}" 2>&1 | tail -1
ok "System packages installed"

# ── 2. Python rich library ─────────────────────────────────────────────────
info "Installing Python 'rich' library..."
# Try system package first (faster, no pip issues), fall back to pip
if apt-get install -y -qq python3-rich 2>/dev/null; then
    ok "rich installed via apt (python3-rich)"
else
    # Use pip with --break-system-packages for Kali's externally-managed Python
    python3 -m pip install --break-system-packages --quiet rich 2>/dev/null \
        || python3 -m pip install --quiet rich 2>/dev/null \
        || fail "Could not install rich library"
    ok "rich installed via pip"
fi

# Verify rich is importable
python3 -c "import rich" 2>/dev/null || fail "rich library not importable"
ok "Python rich library verified"

# ── 3. Copy attack script ─────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATTACK_SCRIPT="${SCRIPT_DIR}/../sambacry_lab/sambacry_attack.py"

if [[ -f "${ATTACK_SCRIPT}" ]]; then
    info "Copying attack script to ${REAL_HOME}/sambacry_attack.py"
    cp "${ATTACK_SCRIPT}" "${REAL_HOME}/sambacry_attack.py"
    chown "${REAL_USER}:${REAL_USER}" "${REAL_HOME}/sambacry_attack.py"
    chmod +x "${REAL_HOME}/sambacry_attack.py"
    ok "Attack script copied"
else
    warn "Attack script not found at ${ATTACK_SCRIPT}"
    info "You can manually copy sambacry_lab/sambacry_attack.py to the attacker"
fi

# ── 4. Verify all tools ───────────────────────────────────────────────────
echo ""
info "Verifying all required tools..."
echo ""

TOOLS=(
    "python3:Python interpreter"
    "smbclient:SMB client operations"
    "smbmap:Share permission enumeration"
    "enum4linux:SMB enumeration"
    "nmap:Port scanner"
    "curl:HTTP client"
    "ncat:Netcat (reverse shell listener)"
    "fuser:Process port lookup"
    "ss:Socket statistics"
)

ALL_OK=true
for entry in "${TOOLS[@]}"; do
    tool="${entry%%:*}"
    desc="${entry#*:}"
    if command -v "${tool}" &>/dev/null; then
        echo -e "    ${GREEN}✔${NC}  ${tool}  ${CYAN}— ${desc}${NC}"
    else
        echo -e "    ${RED}✘${NC}  ${tool}  ${YELLOW}— ${desc} (MISSING)${NC}"
        ALL_OK=false
    fi
done

echo ""

# Check Python rich
if python3 -c "import rich" 2>/dev/null; then
    echo -e "    ${GREEN}✔${NC}  python3-rich  ${CYAN}— Terminal formatting${NC}"
else
    echo -e "    ${RED}✘${NC}  python3-rich  ${YELLOW}— Terminal formatting (MISSING)${NC}"
    ALL_OK=false
fi

echo ""

if $ALL_OK; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Setup complete! All dependencies are ready.         ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
else
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  Setup mostly complete — some items need attention.  ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════╝${NC}"
fi

echo ""
echo -e "  ${CYAN}To run the attack:${NC}"
echo -e "    ${YELLOW}cd ~ && python3 sambacry_attack.py${NC}"
echo ""
