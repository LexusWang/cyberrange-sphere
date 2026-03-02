# Configure the Control Machine (Running Ansible)

## 1.1 Install Ansible

Follow the instructions on this [page](https://docs.ansible.com/projects/ansible/latest/installation_guide/intro_installation.html#installing-and-upgrading-ansible-with-pipx) to install Ansible on the control machine.

Alternatively, use the following commands:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y ansible
```

Verify installation
```bash
ansible --version
```

## 1.2 Configure SSH Keys

```bash
# Generate an SSH key (if you don’t already have one)
ssh-keygen -t rsa -b 4096
# Press Enter for all prompts to use default values

# Copy the public key to Machine B
ssh-copy-id your_username@B_machine_IP
# Example: ssh-copy-id lexuswang@172.30.0.12

# Test the SSH connection
ssh your_username@B_machine_IP
# You should be able to log in without a password
exit
```

## 1.3 Configure the Inventory File

```bash
# Edit inventory-test.ini
cat > inventory-test.ini << EOF
[email_test]
172.30.0.12 ansible_user=lexuswang ansible_ssh_private_key_file=~/.ssh/id_rsa

[email_test:vars]
ansible_python_interpreter=/usr/bin/python3
EOF

# Replace the following:
# - 172.30.0.12 with your Machine B IP address
# - lexuswang with your Machine B username
```

## 1.4 Test the Ansible Connection

```bash
# Test connectivity
ansible -i inventory-test.ini email_test -m ping

# You should see:
# 172.30.0.12 | SUCCESS => {
#     "changed": false,
#     "ping": "pong"
# }
```
