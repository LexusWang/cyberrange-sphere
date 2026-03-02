#!/bin/bash

# DVWA 自动安装脚本 - 适用于 Ubuntu 24.04
# 用法: sudo ./install_dvwa.sh

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# DVWA 配置
DVWA_DB_USER="dvwa"
DVWA_DB_PASS="dvwa_password"
DVWA_DB_NAME="dvwa"
MYSQL_ROOT_PASS="root_password"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
    log_error "请使用 sudo 运行此脚本"
    exit 1
fi

log_info "开始安装 DVWA..."

# 更新系统
log_info "更新系统包..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# 安装 LAMP 组件
log_info "安装 Apache, PHP, MariaDB..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    apache2 \
    mariadb-server \
    mariadb-client \
    php \
    php-mysqli \
    php-gd \
    libapache2-mod-php \
    git \
    unzip

# 启动服务
log_info "启动 Apache 和 MariaDB 服务..."
systemctl start apache2
systemctl enable apache2
systemctl start mariadb
systemctl enable mariadb

# 配置 MariaDB
log_info "配置 MariaDB 数据库..."

# 设置 root 密码并创建 DVWA 数据库和用户
mysql -u root <<EOF
-- 设置 root 密码
ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASS}';
-- 创建 DVWA 数据库
CREATE DATABASE IF NOT EXISTS ${DVWA_DB_NAME};
-- 创建 DVWA 用户
CREATE USER IF NOT EXISTS '${DVWA_DB_USER}'@'localhost' IDENTIFIED BY '${DVWA_DB_PASS}';
-- 授权
GRANT ALL PRIVILEGES ON ${DVWA_DB_NAME}.* TO '${DVWA_DB_USER}'@'localhost';
FLUSH PRIVILEGES;
EOF

# 下载 DVWA
log_info "下载 DVWA..."
DVWA_DIR="/var/www/html/dvwa"

if [ -d "$DVWA_DIR" ]; then
    log_warn "DVWA 目录已存在，删除旧版本..."
    rm -rf "$DVWA_DIR"
fi

git clone https://github.com/digininja/DVWA.git "$DVWA_DIR"

# 配置 DVWA
log_info "配置 DVWA..."
cp "$DVWA_DIR/config/config.inc.php.dist" "$DVWA_DIR/config/config.inc.php"

# 修改数据库配置 (使用更可靠的替换方式)
sed -i "s/p@ssw0rd/${DVWA_DB_PASS}/" "$DVWA_DIR/config/config.inc.php"

# 设置文件权限
log_info "设置文件权限..."
chown -R www-data:www-data "$DVWA_DIR"
chmod -R 755 "$DVWA_DIR"
chmod -R 777 "$DVWA_DIR/hackable/uploads"
chmod 777 "$DVWA_DIR/config"

# 配置 PHP
log_info "配置 PHP..."
PHP_INI=$(php -i | grep "Loaded Configuration File" | awk '{print $5}')
if [ -z "$PHP_INI" ] || [ ! -f "$PHP_INI" ]; then
    # 尝试常见路径
    for ini in /etc/php/8.3/apache2/php.ini /etc/php/8.2/apache2/php.ini /etc/php/8.1/apache2/php.ini; do
        if [ -f "$ini" ]; then
            PHP_INI="$ini"
            break
        fi
    done
fi

if [ -f "$PHP_INI" ]; then
    log_info "修改 PHP 配置: $PHP_INI"
    sed -i 's/allow_url_include = Off/allow_url_include = On/' "$PHP_INI"
    sed -i 's/allow_url_fopen = Off/allow_url_fopen = On/' "$PHP_INI"
else
    log_warn "未找到 PHP 配置文件，请手动配置 allow_url_include = On"
fi

# 重启 Apache
log_info "重启 Apache..."
systemctl restart apache2

# 获取 IP 地址
IP_ADDR=$(hostname -I | awk '{print $1}')

log_info "========================================"
log_info "DVWA 安装完成!"
log_info "========================================"
log_info "访问地址: http://${IP_ADDR}/dvwa/"
log_info "默认登录: admin / password"
log_info ""
log_info "首次访问请点击 'Create / Reset Database' 按钮初始化数据库"
log_info ""
log_info "数据库信息:"
log_info "  数据库名: ${DVWA_DB_NAME}"
log_info "  用户名: ${DVWA_DB_USER}"
log_info "  密码: ${DVWA_DB_PASS}"
log_info "========================================"
