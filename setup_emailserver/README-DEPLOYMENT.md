# 钓鱼测试邮件服务器 - 一键部署指南

完整的A-B-C架构钓鱼邮件测试环境，经过实战测试，可靠稳定。

## 🎯 系统架构

```
┌─────────────┐          ┌─────────────┐          ┌─────────────┐
│  A 机器     │  SMTP    │  B 机器     │  IMAP    │  C 机器     │
│  (发送端)   ├─────────>│ (邮件服务器)│<─────────┤  (接收端)   │
│             │  :25     │             │  :143    │             │
│ 发送钓鱼邮件│          │ Postfix +   │          │ 接收并下载  │
│ 可带附件    │          │ Dovecot     │          │ 邮件和附件  │
└─────────────┘          └─────────────┘          └─────────────┘
```

## 📦 文件清单

```
phishing-email-test/
├── phishing-email-server-final.yml   # 邮件服务器部署脚本（B机器）
├── inventory-test.ini                # 服务器清单配置
├── send_email_with_attachment.py     # 发送脚本（A机器）
├── receive_emails.py                 # 接收脚本（C机器）
└── README-DEPLOYMENT.md              # 本文档
```

## 🚀 完整部署流程

### 阶段1: 准备B机器（邮件服务器）

#### 1.1 系统要求
- Ubuntu 20.04/22.04 或 Debian 11/12
- 最小 512MB RAM，5GB 磁盘
- 有固定IP或已知当前IP

#### 1.2 准备B机器
```bash
# 在B机器上执行

# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Python3
sudo apt install -y python3

# 配置sudo无密码（可选，方便Ansible）
echo "$USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/ansible-$USER
```

### 阶段2: 配置控制机器（运行Ansible）


#### 2.1 安装Ansible
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y ansible

# 验证安装
ansible --version
```

#### 2.2 配置SSH密钥
```bash
# 生成SSH密钥（如果没有）
ssh-keygen -t rsa -b 4096
# 所有提示按Enter使用默认值

# 复制公钥到B机器
ssh-copy-id 你的用户名@B机器IP
# 例如: ssh-copy-id lexuswang@172.30.0.12

# 测试SSH连接
ssh 你的用户名@B机器IP
# 应该无需密码直接登录
exit
```

#### 2.3 配置inventory文件
```bash
# 编辑 inventory-test.ini
cat > inventory-test.ini << EOF
[email_test]
172.30.0.12 ansible_user=lexuswang ansible_ssh_private_key_file=~/.ssh/id_rsa

[email_test:vars]
ansible_python_interpreter=/usr/bin/python3
EOF

# 替换以下内容：
# - 172.30.0.12 改成你的B机器IP
# - lexuswang 改成你的B机器用户名
```

#### 2.4 测试Ansible连接
```bash
# 测试连接
ansible -i inventory-test.ini email_test -m ping

# 应该看到:
# 172.30.0.12 | SUCCESS => {
#     "changed": false,
#     "ping": "pong"
# }
```

### 阶段3: 一键部署邮件服务器

```bash
# 在控制机器上执行
ansible-playbook -i inventory-test.ini phishing-email-server-final.yml

# 部署时间: 约2-5分钟
# 完成后会显示详细的配置信息
```

部署成功后会看到：
```
✅ 服务状态:
   - Postfix (SMTP): RUNNING
   - Dovecot (IMAP): RUNNING

👥 测试用户账户:
   1. testuser1@test.local / password1
   2. testuser2@test.local / password2
   3. victim@test.local / victim123
```

### 阶段4: 配置A机器（发送端）

```bash
# 复制发送脚本到A机器
scp send_email_with_attachment.py A机器用户@A机器IP:/home/用户/

# 在A机器上
chmod +x send_email_with_attachment.py

# 测试发送
python3 send_email_with_attachment.py \
  --server B机器IP \
  --to victim@test.local \
  --template invoice_attachment \
  --create-fake
```

### 阶段5: 配置C机器（接收端）

```bash
# 复制接收脚本到C机器
scp receive_emails.py C机器用户@C机器IP:/home/用户/

# 在C机器上
chmod +x receive_emails.py

# 测试接收
python3 receive_emails.py \
  --server B机器IP \
  --user victim \
  --password victim123
```

## ✅ 完整测试场景

### 测试1: 基本邮件收发

**A机器发送：**
```bash
python3 send_email_with_attachment.py \
  --server 172.30.0.12 \
  --to victim@test.local \
  --template password_reset
```

**C机器接收：**
```bash
python3 receive_emails.py \
  --server 172.30.0.12 \
  --user victim \
  --password victim123
```

### 测试2: 带附件的钓鱼邮件

**A机器发送：**
```bash
# 发送带PDF附件
python3 send_email_with_attachment.py \
  --server 172.30.0.12 \
  --to victim@test.local \
  --template invoice_attachment \
  --attachment malicious.pdf
```

**C机器接收：**
```bash
# 接收并自动下载附件
python3 receive_emails.py \
  --server 172.30.0.12 \
  --user victim \
  --password victim123 \
  --output ./downloads
```

### 测试3: 批量发送

**A机器批量发送：**
```bash
for user in victim testuser1 testuser2; do
  python3 send_email_with_attachment.py \
    --server 172.30.0.12 \
    --to ${user}@test.local \
    --template security_alert
  sleep 1
done
```

### 测试4: 自定义钓鱼邮件

**A机器自定义发送：**
```bash
python3 send_email_with_attachment.py \
  --server 172.30.0.12 \
  --from "ceo@company.com" \
  --to victim@test.local \
  --subject "紧急：需要您的批准" \
  --body "<html><body><h1>请立即批准附件</h1></body></html>" \
  --attachment urgent.docx
```

## 🔧 维护和管理

### 在B机器上查看邮件

```bash
# SSH到B机器
ssh lexuswang@172.30.0.12

# 查看victim的新邮件
sudo ls -la /home/victim/Maildir/new/

# 查看邮件内容
sudo cat /home/victim/Maildir/new/*

# 查看所有用户的邮件数量
for user in testuser1 testuser2 victim; do
  echo "$user: $(sudo ls /home/$user/Maildir/new/ 2>/dev/null | wc -l) 封新邮件"
done
```

### 查看服务日志

```bash
# 在B机器上

# Postfix日志（SMTP）
sudo tail -f /var/log/mail.log

# Dovecot日志（IMAP）
sudo tail -f /var/log/dovecot.log

# 实时监控两个日志
sudo tail -f /var/log/mail.log /var/log/dovecot.log
```

### 服务管理

```bash
# 在B机器上

# 检查服务状态
sudo systemctl status postfix
sudo systemctl status dovecot

# 重启服务
sudo systemctl restart postfix
sudo systemctl restart dovecot

# 停止服务
sudo systemctl stop postfix dovecot

# 启动服务
sudo systemctl start postfix dovecot
```

### 清理测试数据

```bash
# 在B机器上

# 清空所有用户的邮箱
for user in testuser1 testuser2 victim; do
  sudo rm -rf /home/$user/Maildir/new/*
  sudo rm -rf /home/$user/Maildir/cur/*
done

# 清空邮件队列
sudo postsuper -d ALL

# 清空日志
sudo truncate -s 0 /var/log/mail.log
sudo truncate -s 0 /var/log/dovecot.log
```

## 🐛 故障排查

### 问题1: 无法发送邮件

**症状：** Connection timeout 或 Connection refused

**诊断：**
```bash
# 在B机器检查
sudo systemctl status postfix
sudo netstat -tulpn | grep :25

# 测试本地SMTP
echo "QUIT" | nc localhost 25
```

**解决：**
```bash
# 重启Postfix
sudo systemctl restart postfix

# 检查配置
sudo postconf | grep inet_interfaces
# 应该显示: inet_interfaces = all

# 如果不对，修复
sudo postconf -e "inet_interfaces = all"
sudo systemctl restart postfix
```

### 问题2: 无法接收邮件

**症状：** Authentication failed 或 Internal error

**诊断：**
```bash
# 在B机器检查
sudo systemctl status dovecot
sudo tail -30 /var/log/dovecot.log

# 测试IMAP登录
echo "a1 LOGIN victim victim123" | nc localhost 143
```

**解决：**
```bash
# 检查用户文件权限
ls -la /etc/dovecot/users
# 应该是: -rw-r----- dovecot dovecot

# 修复权限
sudo chown dovecot:dovecot /etc/dovecot/users
sudo chmod 640 /etc/dovecot/users
sudo systemctl restart dovecot
```

### 问题3: Postfix配置错误

**症状：** smtpd process exit status 1

**解决：**
```bash
# 重新运行Ansible部署
ansible-playbook -i inventory-test.ini phishing-email-server-final.yml

# 或手动修复
sudo postconf -e "smtpd_relay_restrictions = permit_mynetworks, reject_unauth_destination"
sudo postconf -e "smtpd_recipient_restrictions = permit_mynetworks, permit"
sudo systemctl restart postfix
```

### 问题4: Dovecot用户认证失败

**症状：** User is missing UID

**解决：**
```bash
# 重新生成用户文件
sudo bash -c 'cat > /etc/dovecot/users << EOF
testuser1:{PLAIN}password1:$(id -u testuser1):$(id -g testuser1)::/home/testuser1
testuser2:{PLAIN}password2:$(id -u testuser2):$(id -g testuser2)::/home/testuser2
victim:{PLAIN}victim123:$(id -u victim):$(id -g victim)::/home/victim
EOF'

sudo chown dovecot:dovecot /etc/dovecot/users
sudo chmod 640 /etc/dovecot/users
sudo systemctl restart dovecot
```

### 完整诊断脚本

在B机器上运行完整诊断：

```bash
cat > diagnose.sh << 'EOF'
#!/bin/bash
echo "=== 服务状态 ==="
systemctl is-active postfix && echo "✓ Postfix运行中" || echo "✗ Postfix未运行"
systemctl is-active dovecot && echo "✓ Dovecot运行中" || echo "✗ Dovecot未运行"

echo -e "\n=== 监听端口 ==="
sudo ss -tulpn | grep :25 && echo "✓ SMTP端口25开放" || echo "✗ SMTP端口25未开放"
sudo ss -tulpn | grep :143 && echo "✓ IMAP端口143开放" || echo "✗ IMAP端口143未开放"

echo -e "\n=== 测试SMTP ==="
timeout 2 bash -c "echo QUIT | nc localhost 25" && echo "✓ SMTP工作正常" || echo "✗ SMTP连接失败"

echo -e "\n=== 测试IMAP ==="
timeout 2 bash -c "echo 'a1 LOGIN victim victim123' | nc localhost 143" && echo "✓ IMAP工作正常" || echo "✗ IMAP认证失败"

echo -e "\n=== 邮件统计 ==="
for user in testuser1 testuser2 victim; do
  count=$(sudo ls /home/$user/Maildir/new/ 2>/dev/null | wc -l)
  echo "$user: $count 封新邮件"
done

echo -e "\n=== 最近的错误日志 ==="
sudo tail -5 /var/log/mail.log | grep -i error || echo "无错误"
sudo tail -5 /var/log/dovecot.log | grep -i error || echo "无错误"
EOF

chmod +x diagnose.sh
./diagnose.sh
```

## 📊 性能和限制

### 当前配置的限制

- **单个邮件大小：** 50MB
- **邮箱配额：** 无限制
- **并发连接：** 默认限制（通常足够测试使用）
- **每日发送量：** 无限制（开放中继）

### 如需修改限制

```bash
# 在B机器上修改Postfix限制
sudo postconf -e "message_size_limit = 104857600"  # 100MB
sudo postconf -e "mailbox_size_limit = 1073741824" # 1GB
sudo systemctl restart postfix
```

## 🔐 安全注意事项

### ⚠️ 危险配置（仅用于测试）

此配置包含以下**严重不安全**的设置：

1. **开放中继** - 任何人都可以通过此服务器发送邮件
2. **无加密** - 所有通信都是明文传输
3. **弱密码** - 使用简单的测试密码
4. **无垃圾邮件过滤** - 接受所有邮件
5. **无认证限制** - SMTP不需要认证

### ✅ 安全使用建议

1. **网络隔离** - 使用独立的虚拟网络
2. **防火墙** - 不要允许外网访问
3. **及时关闭** - 测试完成后立即停止服务
4. **监控日志** - 定期检查是否有异常活动
5. **数据清理** - 定期清理测试邮件

### 关闭服务

测试完成后：

```bash
# 在B机器上
sudo systemctl stop postfix dovecot
sudo systemctl disable postfix dovecot

# 或完全卸载
sudo apt remove --purge postfix dovecot-core dovecot-imapd
```

## 📚 参考资源

- [Postfix文档](http://www.postfix.org/documentation.html)
- [Dovecot文档](https://doc.dovecot.org/)
- [Ansible文档](https://docs.ansible.com/)
- [OWASP钓鱼指南](https://owasp.org/www-community/attacks/Phishing)

## 🎓 实验建议

### 实验1: 社会工程学测试
测试不同类型钓鱼邮件的有效性：
- 紧急/权威类（密码重置、安全警报）
- 利益诱惑类（中奖、奖金）
- 工作相关类（发票、合同）
- 个人化攻击（针对特定人员）

### 实验2: 附件类型研究
测试不同附件的点击率：
- .pdf（最常见）
- .docx（文档类）
- .xlsx（表格类）
- .exe/.zip（可执行文件）

### 实验3: 发件人身份影响
比较不同发件人身份的影响：
- 内部IT部门
- 外部合作伙伴
- 高管/领导
- 个人联系人

### 实验4: 时间因素分析
研究发送时间对成功率的影响：
- 工作日 vs 周末
- 上班时间 vs 下班时间
- 月初 vs 月末（与发票相关）

## 📝 变更日志

### v1.0 - 最终稳定版本
- ✅ 修复了Postfix relay restrictions配置
- ✅ 修复了Dovecot用户文件权限问题
- ✅ 自动获取并设置用户UID/GID
- ✅ 添加了服务健康检查
- ✅ 完善的错误处理和日志记录
- ✅ 详细的部署后配置信息
- ✅ 经过完整的A-B-C测试验证

## 🤝 支持

如遇到问题：
1. 查看本文档的故障排查章节
2. 检查B机器的日志文件
3. 运行诊断脚本
4. 重新部署（Ansible是幂等的，可以安全重复运行）

---

**最后更新：** 2026-01-16
**测试环境：** Ubuntu 22.04
**状态：** ✅ 生产就绪（测试用途）
