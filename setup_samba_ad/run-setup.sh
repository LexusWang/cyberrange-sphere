#!/bin/bash
# Samba4 AD 环境自动化部署脚本
# 用法: ./run-setup.sh [dc|members|all]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Samba4 AD 靶场环境部署脚本${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# 检查 ansible 是否安装
if ! command -v ansible-playbook &> /dev/null; then
    echo -e "${RED}错误: ansible 未安装${NC}"
    echo "请运行: pip install ansible"
    exit 1
fi

# 检查参数
TARGET="${1:-all}"

case "$TARGET" in
    dc)
        echo -e "${YELLOW}仅配置域控制器 (victim1)...${NC}"
        ansible-playbook site.yml --tags dc --ask-become-pass
        ;;
    members)
        echo -e "${YELLOW}仅配置域成员 (victim2, redirector, emailServer)...${NC}"
        ansible-playbook site.yml --tags members --ask-become-pass
        ;;
    all)
        echo -e "${YELLOW}配置完整 AD 环境...${NC}"
        echo ""
        echo "步骤 1: 配置域控制器"
        ansible-playbook site.yml --tags dc --ask-become-pass
        echo ""
        echo -e "${GREEN}域控制器配置完成，等待10秒后配置域成员...${NC}"
        sleep 10
        echo ""
        echo "步骤 2: 配置域成员"
        ansible-playbook site.yml --tags members --ask-become-pass
        ;;
    check)
        echo -e "${YELLOW}检查连接性...${NC}"
        ansible all -m ping --ask-become-pass
        ;;
    *)
        echo "用法: $0 [dc|members|all|check]"
        echo ""
        echo "  dc      - 仅配置域控制器"
        echo "  members - 仅配置域成员"
        echo "  all     - 配置完整环境 (默认)"
        echo "  check   - 检查所有主机连接性"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  部署完成!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "域信息:"
echo "  域名: YOURCOMPANY.LOCAL"
echo "  DC:   victim1 (10.0.1.4)"
echo ""
echo "测试用户:"
echo "  jsmith / Summer2024!"
echo "  mwilson / Welcome123!"
echo "  admin.backup / Backup@dmin1 (Domain Admin)"
echo "  svc_sql / SqlService1! (有SPN)"
