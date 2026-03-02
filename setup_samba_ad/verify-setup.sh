#!/bin/bash
# Samba4 AD 环境验证脚本

echo "============================================"
echo "  Samba4 AD 环境验证"
echo "============================================"
echo ""

# 检查 DC
echo "[1] 检查域控制器 (victim1)..."
ssh victim1 "sudo samba-tool domain level show 2>/dev/null | head -3" || echo "ERROR: DC不可用"
echo ""

# 列出域计算机
echo "[2] 域中的计算机："
ssh victim1 "sudo samba-tool computer list 2>/dev/null"
echo ""

# 列出域用户
echo "[3] 域用户："
ssh victim1 "sudo samba-tool user list 2>/dev/null"
echo ""

# 检查域成员
echo "[4] 检查域成员连接..."
for host in victim2 redirector emailServer; do
    echo -n "  $host: "
    result=$(ssh $host "wbinfo -u 2>/dev/null | wc -l")
    if [ "$result" -gt 0 ]; then
        echo "OK (可列出 $result 个用户)"
    else
        echo "ERROR"
    fi
done
echo ""

# 测试 Kerberos
echo "[5] 测试 Kerberos 认证 (从 victim2)..."
ssh victim2 "echo 'Summer2024!' | kinit jsmith@YOURCOMPANY.LOCAL 2>&1 | grep -E 'Warning|Error|valid'"
echo ""

# 测试 SMB 访问
echo "[6] 测试 SMB 访问..."
ssh victim2 "smbclient -L //victim1 -k -N 2>&1 | grep -E 'Sharename|sysvol|netlogon'"
echo ""

echo "============================================"
echo "  验证完成"
echo "============================================"
echo ""
echo "测试账户信息:"
echo "  jsmith / Summer2024!         (普通用户)"
echo "  mwilson / Welcome123!        (普通用户)"
echo "  admin.backup / Backup@dmin1  (Domain Admin)"
echo "  svc_sql / SqlService1!       (有 SPN，可 Kerberoast)"
echo "  Administrator / P@ssw0rd123! (域管理员)"
