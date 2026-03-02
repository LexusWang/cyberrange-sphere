# 配置控制机器（运行Ansible）


## 1.1 Install Ansible
Follow the instructions on this [page](https://docs.ansible.com/projects/ansible/latest/installation_guide/intro_installation.html#installing-and-upgrading-ansible-with-pipx) to install ansible on the controller.

Otherwise, use the following commands.
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y ansible

# Verify installation
ansible --version
```

## 1.2 配置SSH密钥
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

## 1.3 配置inventory文件
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

## 1.4 测试Ansible连接
```bash
# 测试连接
ansible -i inventory-test.ini email_test -m ping

# 应该看到:
# 172.30.0.12 | SUCCESS => {
#     "changed": false,
#     "ping": "pong"
# }
```