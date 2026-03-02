# Samba4 Active Directory 靶场环境手工配置指南

## 环境概述

| 主机名 | 角色 | IP地址(内网) | 说明 |
|--------|------|--------------|------|
| victim1 | Domain Controller | 10.0.1.4 | Samba AD DC |
| victim2 | Domain Member | 10.0.1.5 | 域成员 |
| redirector | Domain Member | 10.0.1.2 | 域成员 |
| emailServer | Domain Member | 10.0.1.3 | 域成员 |

**域配置信息:**
- 域名 (Realm): `YOURCOMPANY.LOCAL`
- NetBIOS 名: `YOURCOMPANY`
- 域管理员密码: `P@ssw0rd123!`

---

## 第一部分：配置域控制器 (victim1)

### 1.1 安装必要软件包

```bash
ssh victim1
sudo apt update
sudo apt install -y samba smbclient krb5-user krb5-config winbind \
    libpam-winbind libnss-winbind acl attr dnsutils ldb-tools python3-samba
```

安装 `krb5-user` 时会提示输入 realm，输入: `YOURCOMPANY.LOCAL`

### 1.2 停止并禁用冲突服务

```bash
sudo systemctl stop smbd nmbd winbind
sudo systemctl disable smbd nmbd winbind
sudo systemctl mask smbd nmbd winbind

# 关键步骤：禁用 systemd-resolved（否则 Samba DNS 无法绑定 53 端口）
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved
echo "nameserver 127.0.0.1" | sudo tee /etc/resolv.conf
```

### 1.3 备份并删除原有配置

```bash
sudo mv /etc/samba/smb.conf /etc/samba/smb.conf.orig
```

### 1.4 配置 Samba AD 域

```bash
sudo samba-tool domain provision \
    --server-role=dc \
    --use-rfc2307 \
    --dns-backend=SAMBA_INTERNAL \
    --realm=YOURCOMPANY.LOCAL \
    --domain=YOURCOMPANY \
    --adminpass='P@ssw0rd123!'
```

### 1.5 配置 Kerberos

```bash
sudo cp /var/lib/samba/private/krb5.conf /etc/krb5.conf
```

### 1.6 配置 /etc/hosts

```bash
echo "10.0.1.4 victim1.yourcompany.local victim1" | sudo tee -a /etc/hosts
```

### 1.7 启动 Samba AD DC 服务

```bash
sudo systemctl unmask samba-ad-dc
sudo systemctl enable samba-ad-dc
sudo systemctl start samba-ad-dc
```

### 1.8 验证配置

```bash
# 检查域级别
sudo samba-tool domain level show

# 测试 DNS
host -t A victim1.yourcompany.local localhost

# 测试 Kerberos
kinit Administrator
# 输入密码: P@ssw0rd123!

# 查看票据
klist
```

### 1.9 创建测试用户（用于渗透测试）

```bash
# 普通用户
sudo samba-tool user create jsmith 'Summer2024!' \
    --given-name="John" --surname="Smith" \
    --mail-address="jsmith@yourcompany.local"

sudo samba-tool user create mwilson 'Welcome123!' \
    --given-name="Mary" --surname="Wilson" \
    --mail-address="mwilson@yourcompany.local"

# 备份管理员账户（加入Domain Admins组）
sudo samba-tool user create admin.backup 'Backup@dmin1' \
    --given-name="Backup" --surname="Admin" \
    --mail-address="admin.backup@yourcompany.local"

sudo samba-tool group addmembers "Domain Admins" admin.backup

# 服务账户（用于Kerberoasting演示）
sudo samba-tool user create svc_sql 'SqlService1!' \
    --given-name="SQL" --surname="Service" \
    --mail-address="svc_sql@yourcompany.local"

# 为服务账户设置SPN（使其可被Kerberoast）
sudo samba-tool spn add MSSQLSvc/victim1.yourcompany.local:1433 svc_sql
```

### 1.10 查看创建的用户

```bash
sudo samba-tool user list
```

---

## 第二部分：配置域成员 (victim2, redirector, emailServer)

**以下步骤在每台域成员机器上重复执行**

### 2.1 安装必要软件包

```bash
sudo apt update
sudo apt install -y samba smbclient krb5-user krb5-config winbind \
    libpam-winbind libnss-winbind acl attr dnsutils
```

### 2.2 配置 /etc/hosts

```bash
# 添加DC解析
echo "10.0.1.4 victim1.yourcompany.local victim1" | sudo tee -a /etc/hosts

# 添加本机解析 (根据实际IP修改)
# victim2:
echo "10.0.1.5 victim2.yourcompany.local victim2" | sudo tee -a /etc/hosts
# redirector:
echo "10.0.1.2 redirector.yourcompany.local redirector" | sudo tee -a /etc/hosts
# emailServer:
echo "10.0.1.3 emailServer.yourcompany.local emailServer" | sudo tee -a /etc/hosts
```

### 2.3 配置 DNS 指向 DC

```bash
# 禁用 systemd-resolved
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved

# 配置 resolv.conf
sudo bash -c 'cat > /etc/resolv.conf << EOF
search yourcompany.local
nameserver 10.0.1.4
EOF'
```

### 2.4 配置 Kerberos

创建 `/etc/krb5.conf`:

```bash
sudo bash -c 'cat > /etc/krb5.conf << EOF
[libdefaults]
    default_realm = YOURCOMPANY.LOCAL
    dns_lookup_realm = false
    dns_lookup_kdc = true
    ticket_lifetime = 24h
    renew_lifetime = 7d
    forwardable = true

[realms]
    YOURCOMPANY.LOCAL = {
        kdc = victim1.yourcompany.local
        admin_server = victim1.yourcompany.local
        default_domain = yourcompany.local
    }

[domain_realm]
    .yourcompany.local = YOURCOMPANY.LOCAL
    yourcompany.local = YOURCOMPANY.LOCAL
EOF'
```

### 2.5 配置 Samba (smb.conf)

```bash
sudo mv /etc/samba/smb.conf /etc/samba/smb.conf.orig

sudo bash -c 'cat > /etc/samba/smb.conf << EOF
[global]
    workgroup = YOURCOMPANY
    security = ADS
    realm = YOURCOMPANY.LOCAL

    winbind use default domain = yes
    winbind offline logon = yes
    winbind enum users = yes
    winbind enum groups = yes
    winbind refresh tickets = yes

    idmap config * : backend = tdb
    idmap config * : range = 3000-7999
    idmap config YOURCOMPANY : backend = rid
    idmap config YOURCOMPANY : range = 10000-999999

    template homedir = /home/%U
    template shell = /bin/bash

    log file = /var/log/samba/log.%m
    max log size = 1000

    load printers = no
    printing = bsd
    printcap name = /dev/null
    disable spoolss = yes

[homes]
    comment = Home Directories
    browseable = no
    read only = no
    create mask = 0700
    directory mask = 0700
    valid users = %S

[shared]
    comment = Shared Files
    path = /srv/samba/shared
    browseable = yes
    read only = no
    create mask = 0664
    directory mask = 0775
EOF'
```

### 2.6 创建共享目录

```bash
sudo mkdir -p /srv/samba/shared
sudo chmod 775 /srv/samba/shared
```

### 2.7 加入域

```bash
# 停止服务
sudo systemctl stop smbd nmbd winbind

# 加入域
sudo net ads join -U Administrator%'P@ssw0rd123!'
```

### 2.8 配置 NSS

编辑 `/etc/nsswitch.conf`，修改以下行:

```bash
sudo sed -i 's/^passwd:.*/passwd: files systemd winbind/' /etc/nsswitch.conf
sudo sed -i 's/^group:.*/group: files systemd winbind/' /etc/nsswitch.conf
```

### 2.9 配置 PAM (允许域用户登录)

```bash
sudo pam-auth-update --enable winbind

# 配置自动创建家目录
echo "session required pam_mkhomedir.so skel=/etc/skel umask=0022" | \
    sudo tee -a /etc/pam.d/common-session
```

### 2.10 启动服务

```bash
sudo systemctl start smbd nmbd winbind
sudo systemctl enable smbd nmbd winbind
```

### 2.11 验证配置

```bash
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
```

---

## 第三部分：验证整体环境

### 3.1 在 DC 上验证

```bash
# 列出所有域成员
sudo samba-tool computer list

# 检查复制状态
sudo samba-tool drs showrepl

# 测试 LDAP
ldapsearch -x -H ldap://localhost -b "DC=yourcompany,DC=local" "(objectClass=user)" cn
```

### 3.2 在域成员上测试 Kerberos 认证

```bash
# 获取 TGT
kinit jsmith@YOURCOMPANY.LOCAL
# 密码: Summer2024!

# 查看票据
klist

# 访问 DC 共享
smbclient //victim1/netlogon -k
```

### 3.3 测试 SMB 访问

```bash
# 使用密码认证
smbclient //victim1/netlogon -U jsmith%'Summer2024!'

# 列出共享
smbclient -L //victim1 -U jsmith%'Summer2024!'
```

---

## 第四部分：渗透测试场景

### 4.1 可用的测试用户

| 用户名 | 密码 | 角色 | 备注 |
|--------|------|------|------|
| Administrator | P@ssw0rd123! | Domain Admin | 域管理员 |
| admin.backup | Backup@dmin1 | Domain Admin | 备份管理员 |
| jsmith | Summer2024! | Domain User | 普通用户 |
| mwilson | Welcome123! | Domain User | 普通用户 |
| svc_sql | SqlService1! | Domain User | SQL服务账户，有SPN |

### 4.2 可演练的攻击场景

1. **密码喷洒 (Password Spraying)**
   - 使用常见密码对域用户进行喷洒攻击

2. **Kerberoasting**
   - svc_sql 账户设置了 SPN，可以请求其 TGS 并离线破解
   ```bash
   # 使用 impacket
   GetUserSPNs.py YOURCOMPANY.LOCAL/jsmith:'Summer2024!' -dc-ip 10.0.1.4 -request
   ```

3. **AS-REP Roasting**
   - 可以创建不需要预认证的用户进行测试

4. **Pass-the-Hash / Pass-the-Ticket**
   - 获取凭据后进行横向移动

5. **DCSync**
   - 使用 Domain Admin 权限提取所有密码哈希

6. **SMB Relay**
   - 在域成员之间进行 SMB 中继攻击

---

## 故障排除

### 问题: 无法加入域

```bash
# 检查 DNS 解析
nslookup victim1.yourcompany.local 10.0.1.4

# 检查时间同步
date
# 如果时间差距大于5分钟，需要同步:
sudo ntpdate victim1.yourcompany.local
```

### 问题: Winbind 无法连接

```bash
# 检查服务状态
sudo systemctl status winbind

# 重启服务
sudo systemctl restart smbd nmbd winbind

# 检查日志
sudo tail -f /var/log/samba/log.winbindd
```

### 问题: 域用户无法登录

```bash
# 检查 PAM 配置
cat /etc/pam.d/common-auth | grep winbind

# 检查 NSS 配置
getent passwd | grep -i yourcompany
```

---

## 快速重置

如需重置整个环境:

### 重置域成员:
```bash
sudo net ads leave -U Administrator%'P@ssw0rd123!'
sudo systemctl stop smbd nmbd winbind
sudo rm -rf /var/lib/samba/*
sudo rm /etc/samba/smb.conf
```

### 重置域控制器:
```bash
sudo systemctl stop samba-ad-dc
sudo rm -rf /var/lib/samba/*
sudo rm /etc/samba/smb.conf
# 然后重新执行 samba-tool domain provision
```
