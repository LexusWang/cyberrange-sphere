#!/bin/bash
# 批量在多台机器上配置 /home 磁盘
# 用法: ./setup-home-disk.sh victim1 victim2 victim3 ...
# 或者: ./setup-home-disk.sh all  (使用默认列表)

# 不使用 set -e，让脚本能继续处理下一台机器

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 默认机器列表
DEFAULT_HOSTS="victim1 victim2 victim3 victim4 victim5"

# 要执行的脚本内容
REMOTE_SCRIPT='#!/bin/bash

echo "=== 开始配置 /home 磁盘 ==="

# 1. 备份现有 home 目录
echo "[1/10] 备份 /home 目录..."
sudo mkdir -p /tmp/home_backup
sudo rsync -av /home/ /tmp/home_backup/

# 2. 格式化新磁盘
echo "[2/10] 格式化 /dev/vdb..."
sudo mkfs.ext4 -L home /dev/vdb

# 3. 临时挂载
echo "[3/10] 临时挂载到 /mnt/newhome..."
sudo mkdir -p /mnt/newhome
sudo mount -L home /mnt/newhome

# 4. 恢复数据
echo "[4/10] 恢复 home 目录内容..."
sudo rsync -av /tmp/home_backup/ /mnt/newhome/

# 5. 卸载临时挂载点
echo "[5/10] 卸载临时挂载点..."
sudo umount /mnt/newhome

# 6. 挂载到 /home
echo "[6/10] 挂载到 /home..."
sudo mount -L home /home

# 7. 添加 fstab 条目
echo "[7/10] 更新 /etc/fstab..."
if ! grep -q "LABEL=home" /etc/fstab; then
    echo "LABEL=home    /home    ext4    defaults    0 0" | sudo tee -a /etc/fstab
else
    echo "fstab 条目已存在，跳过"
fi

# 8. 重载 systemd
echo "[8/10] 重载 systemd..."
sudo systemctl daemon-reload

# 9. 验证挂载
echo "[9/10] 验证挂载..."
df -h /home

# 10. 清理
echo "[10/10] 清理临时文件..."
sudo rm -rf /tmp/home_backup

echo "=== 完成! /home 已挂载到新磁盘 ==="
'

# 显示用法
usage() {
    echo "用法: $0 [host1 host2 ...] 或 $0 all"
    echo ""
    echo "示例:"
    echo "  $0 victim1 victim2 victim3"
    echo "  $0 all                        # 使用默认列表: $DEFAULT_HOSTS"
    echo ""
    echo "选项:"
    echo "  --dry-run    仅显示将要执行的操作，不实际执行"
    echo "  --help       显示此帮助信息"
    exit 1
}

# 检查参数
if [ $# -eq 0 ]; then
    usage
fi

# 解析参数
DRY_RUN=false
HOSTS=()

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
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
echo -e "${BLUE}  批量配置 /home 磁盘脚本${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "目标主机: ${YELLOW}${HOSTS[*]}${NC}"
echo -e "主机数量: ${#HOSTS[@]}"
if $DRY_RUN; then
    echo -e "${YELLOW}模式: 试运行 (不实际执行)${NC}"
fi
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

    if $DRY_RUN; then
        echo -e "${YELLOW}[试运行] 将在 $host 上执行脚本${NC}"
        echo "ssh $host 'bash -s' <<< \"\$REMOTE_SCRIPT\""
        ((SUCCESS++))
        continue
    fi

    # 先检查连接
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$host" "echo 'SSH连接成功'" 2>/dev/null; then
        echo -e "${RED}错误: 无法连接到 $host${NC}"
        ((FAILED++))
        FAILED_HOSTS+=("$host")
        continue
    fi

    # 检查 /dev/vdb 是否存在
    if ! ssh "$host" "test -b /dev/vdb" 2>/dev/null; then
        echo -e "${RED}错误: $host 上不存在 /dev/vdb${NC}"
        ((FAILED++))
        FAILED_HOSTS+=("$host")
        continue
    fi

    # 检查是否已经挂载
    if ssh "$host" "mount | grep -q 'LABEL=home on /home'" 2>/dev/null; then
        echo -e "${YELLOW}跳过: $host 上 /home 已挂载到新磁盘${NC}"
        ((SUCCESS++))
        continue
    fi

    # 执行脚本
    if ssh "$host" "bash -s" <<< "$REMOTE_SCRIPT"; then
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
