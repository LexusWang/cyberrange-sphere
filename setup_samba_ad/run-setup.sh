#!/bin/bash
# Samba4 AD Environment Automated Deployment Script
# Usage: ./run-setup.sh [dc|members|all|check]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# --- Parse inventory.ini dynamically ---
INVENTORY="inventory.ini"

if [ ! -f "$INVENTORY" ]; then
    echo -e "${RED}Error: $INVENTORY not found in $(pwd)${NC}"
    exit 1
fi

DC_HOST=$(python3 - "$INVENTORY" <<'PYEOF'
import sys
section = None
for line in open(sys.argv[1]):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    if line.startswith('['):
        section = line[1:line.index(']')]
        continue
    if section == 'dc':
        print(line.split()[0])
        sys.exit()
PYEOF
)

MEMBER_LIST=$(python3 - "$INVENTORY" <<'PYEOF'
import sys
section = None
for line in open(sys.argv[1]):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    if line.startswith('['):
        section = line[1:line.index(']')]
        continue
    if section == 'domain_members':
        print(line.split()[0])
PYEOF
)

DOMAIN_NAME=$(python3 - "$INVENTORY" <<'PYEOF'
import sys
section = None
for line in open(sys.argv[1]):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    if line.startswith('['):
        section = line[1:line.index(']')]
        continue
    if section == 'samba_ad:vars' and line.startswith('domain_name='):
        print(line.split('=', 1)[1])
        break
PYEOF
)

MEMBER_COUNT=$(echo "$MEMBER_LIST" | grep -c .)
MEMBERS_INLINE=$(echo "$MEMBER_LIST" | tr '\n' ' ')

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Samba4 AD Lab Environment Deployer${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Loaded from $INVENTORY:"
echo "  DC:      ${DC_HOST:-<not found>}"
echo "  Members: ${MEMBERS_INLINE}(${MEMBER_COUNT} hosts)"
echo "  Domain:  ${DOMAIN_NAME:-<not found>}"
echo ""

# Check if ansible is installed
if ! command -v ansible-playbook &> /dev/null; then
    echo -e "${RED}Error: ansible is not installed${NC}"
    echo "Please run: pip install ansible"
    exit 1
fi

# Parse arguments
TARGET="${1:-all}"

case "$TARGET" in
    dc)
        echo -e "${YELLOW}Configuring domain controller (${DC_HOST})...${NC}"
        ansible-playbook site.yml --tags dc --ask-become-pass
        ;;
    members)
        echo -e "${YELLOW}Configuring ${MEMBER_COUNT} domain member(s): ${MEMBERS_INLINE}...${NC}"
        ansible-playbook site.yml --tags members --ask-become-pass
        ;;
    all)
        echo -e "${YELLOW}Configuring full AD environment...${NC}"
        echo ""
        echo "Step 1: Configure domain controller (${DC_HOST})"
        ansible-playbook site.yml --tags dc --ask-become-pass
        echo ""
        echo -e "${GREEN}Domain controller configured. Waiting 10 seconds before configuring domain members...${NC}"
        sleep 10
        echo ""
        echo "Step 2: Configure ${MEMBER_COUNT} domain member(s): ${MEMBERS_INLINE}"
        ansible-playbook site.yml --tags members --ask-become-pass
        ;;
    check)
        echo -e "${YELLOW}Checking connectivity to all hosts...${NC}"
        ansible all -m ping --ask-become-pass
        ;;
    *)
        echo "Usage: $0 [dc|members|all|check]"
        echo ""
        echo "  dc      - Configure domain controller only"
        echo "  members - Configure domain members only"
        echo "  all     - Configure full environment (default)"
        echo "  check   - Check connectivity to all hosts"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Domain: ${DOMAIN_NAME}"
echo "DC:     ${DC_HOST}"
echo "        (run 'ssh ${DC_HOST} hostname -I' to check its IP)"
echo ""
echo "Members provisioned (${MEMBER_COUNT}):"
echo "$MEMBER_LIST" | while IFS= read -r host; do
    echo "  - ${host}"
done
echo ""
echo "Test Users:"
echo "  jsmith       / Summer2024!"
echo "  mwilson      / Welcome123!"
echo "  admin.backup / Backup@dmin1  (Domain Admin)"
echo "  svc_sql      / SqlService1!  (has SPN, Kerberoastable)"
