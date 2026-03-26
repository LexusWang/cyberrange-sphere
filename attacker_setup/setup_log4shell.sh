#!/usr/bin/env bash
# ============================================================================
# Log4Shell Lab — Attacker Machine Setup
# ============================================================================
# Installs all dependencies needed to run log4shell_attack.py on a minimal
# Kali image (SPHERE cyber range).
#
# Usage:  sudo bash setup_log4shell.sh
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
echo -e "${CYAN}║  Log4Shell Lab — Attacker Machine Setup              ║${NC}"
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
    git
    nmap
    # Java (for marshalsec + Exploit.class compilation)
    default-jdk
    # Maven (for building marshalsec)
    maven
    # Netcat (reverse shell listener)
    ncat
    # SSH with password (post-exploitation fallback)
    sshpass
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

# ── 3. Clone and build marshalsec ──────────────────────────────────────────
MARSHALSEC_DIR="${REAL_HOME}/marshalsec"
MARSHALSEC_JAR="${MARSHALSEC_DIR}/target/marshalsec-0.0.3-SNAPSHOT-all.jar"

if [[ -f "${MARSHALSEC_JAR}" ]]; then
    ok "marshalsec already built: ${MARSHALSEC_JAR}"
else
    info "Building marshalsec (LDAP referral server for Log4Shell)..."

    if [[ ! -d "${MARSHALSEC_DIR}" ]]; then
        info "Cloning marshalsec repository..."
        sudo -u "${REAL_USER}" git clone --depth 1 https://github.com/mbechler/marshalsec "${MARSHALSEC_DIR}" \
            || fail "Failed to clone marshalsec"
        ok "marshalsec cloned"
    fi

    info "Building marshalsec with Maven (this may take a few minutes)..."
    cd "${MARSHALSEC_DIR}"
    sudo -u "${REAL_USER}" mvn clean package -DskipTests -q 2>&1 | tail -5

    if [[ -f "${MARSHALSEC_JAR}" ]]; then
        ok "marshalsec built: ${MARSHALSEC_JAR}"
    else
        warn "Maven build may have failed — checking for jar..."
        # Try to find the jar anywhere in target/
        JAR_FOUND=$(find "${MARSHALSEC_DIR}/target" -name "*.jar" -type f 2>/dev/null | head -1)
        if [[ -n "${JAR_FOUND}" ]]; then
            ok "Found jar: ${JAR_FOUND}"
        else
            warn "marshalsec build failed. You can try manually:"
            warn "  cd ~/marshalsec && mvn clean package -DskipTests"
            warn "Continuing setup..."
        fi
    fi
fi

# ── 4. Copy attack script ─────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATTACK_SCRIPT="${SCRIPT_DIR}/../log4shell_lab/log4shell_attack.py"

if [[ -f "${ATTACK_SCRIPT}" ]]; then
    info "Copying attack script to ${REAL_HOME}/log4shell_attack.py"
    cp "${ATTACK_SCRIPT}" "${REAL_HOME}/log4shell_attack.py"
    chown "${REAL_USER}:${REAL_USER}" "${REAL_HOME}/log4shell_attack.py"
    chmod +x "${REAL_HOME}/log4shell_attack.py"
    ok "Attack script copied"
else
    warn "Attack script not found at ${ATTACK_SCRIPT}"
    info "You can manually copy log4shell_lab/log4shell_attack.py to the attacker"
fi

# ── 5. Verify all tools ───────────────────────────────────────────────────
echo ""
info "Verifying all required tools..."
echo ""

TOOLS=(
    "python3:Python interpreter"
    "curl:HTTP client"
    "nmap:Port scanner"
    "javac:Java compiler"
    "java:JVM runtime"
    "mvn:Maven build tool"
    "ncat:Netcat (reverse shell listener)"
    "git:Version control"
    "sshpass:SSH with password"
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

# Check marshalsec jar
if [[ -f "${MARSHALSEC_JAR}" ]]; then
    echo -e "    ${GREEN}✔${NC}  marshalsec.jar  ${CYAN}— LDAP referral server${NC}"
else
    echo -e "    ${RED}✘${NC}  marshalsec.jar  ${YELLOW}— LDAP referral server (NOT BUILT)${NC}"
    ALL_OK=false
fi

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
echo -e "    ${YELLOW}cd ~ && python3 log4shell_attack.py${NC}"
echo ""
