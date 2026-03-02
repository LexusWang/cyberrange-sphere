#!/bin/bash
# 批量在多台机器上扩展根分区
# 用法: ./resize-root-disk.sh victim1 victim2 victim3 ...
# 或者: ./resize-root-disk.sh all  (使用默认列表)

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 默认机器列表
DEFAULT_HOSTS="victim1 victim2 victim3 victim4 victim5"

# 显示用法
usage() {
    echo "用法: $0 [host1 host2 ...] 或 $0 all"
    echo ""
    echo "示例:"
    echo "  $0 victim1 victim2 victim3"
    echo "  $0 all                        # 使用默认列表: $DEFAULT_HOSTS"
    exit 1
}

# 检查参数
if [ $# -eq 0 ]; then
    usage
fi

# 解析参数
HOSTS=()

for arg in "$@"; do
    case $arg in
        --help|-h)
            usage
            ;;
        all)
            HOSTS=($DEFAULT_HOSTS)
            ;;
        *)
            HOSTS+=("$arg")
            ;;
    esac
done

if [ ${#HOSTS[@]} -eq 0 ]; then
    echo -e "${RED}错误: 未指定目标主机${NC}"
    usage
fi

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  批量扩展根分区脚本${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "目标主机: ${YELLOW}${HOSTS[*]}${NC}"
echo -e "主机数量: ${#HOSTS[@]}"
echo ""

# 确认执行
read -p "确认在以上主机执行? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""

# 统计
SUCCESS=0
FAILED=0
FAILED_HOSTS=()

# 依次在每台机器上执行
for host in "${HOSTS[@]}"; do
    echo -e "${BLUE}--------------------------------------${NC}"
    echo -e "${YELLOW}[$((SUCCESS + FAILED + 1))/${#HOSTS[@]}] 正在处理: $host${NC}"
    echo -e "${BLUE}--------------------------------------${NC}"

    # 先检查连接
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$host" "echo 'SSH连接成功'" 2>/dev/null; then
        echo -e "${RED}错误: 无法连接到 $host${NC}"
        ((FAILED++))
        FAILED_HOSTS+=("$host")
        continue
    fi

    # 执行命令
    if ssh "$host" "sudo partprobe && sudo resize2fs /dev/vda3"; then
        echo -e "${GREEN}成功: $host${NC}"
        ((SUCCESS++))
    else
        echo -e "${RED}失败: $host${NC}"
        ((FAILED++))
        FAILED_HOSTS+=("$host")
    fi

    echo ""
done

# 显示结果汇总
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  执行结果汇总${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "成功: ${GREEN}$SUCCESS${NC}"
echo -e "失败: ${RED}$FAILED${NC}"

if [ $FAILED -gt 0 ]; then
    echo -e "失败的主机: ${RED}${FAILED_HOSTS[*]}${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}全部完成!${NC}"
