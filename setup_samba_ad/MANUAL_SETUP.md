# Samba4 Active Directory Lab Environment Manual Configuration Guide

## Environment Overview

| Hostname | Role | IP Address (Internal) | Description |
|----------|------|-----------------------|-------------|
| victim1 | Domain Controller | 10.0.1.4 | Samba AD DC |
| victim2 | Domain Member | 10.0.1.5 | Domain Member |
| redirector | Domain Member | 10.0.1.2 | Domain Member |
| emailServer | Domain Member | 10.0.1.3 | Domain Member |

**Domain Configuration:**
- Domain Name (Realm): `YOURCOMPANY.LOCAL`
- NetBIOS Name: `YOURCOMPANY`
- Domain Administrator Password: `P@ssw0rd123!`

---

## Part 1: Configuring the Domain Controller (victim1)

### 1.1 Install Required Packages

```bash
ssh victim1
sudo apt update
sudo apt install -y samba smbclient krb5-user krb5-config winbind \
    libpam-winbind libnss-winbind acl attr dnsutils ldb-tools python3-samba
```

When installing `krb5-user`, you'll be prompted to enter the realm. Enter: `YOURCOMPANY.LOCAL`

### 1.2 Stop and Disable Conflicting Services

```bash
sudo systemctl stop smbd nmbd winbind
sudo systemctl disable smbd nmbd winbind
sudo systemctl mask smbd nmbd winbind

# Critical step: Disable systemd-resolved (otherwise Samba DNS cannot bind to port 53)
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved
echo "nameserver 127.0.0.1" | sudo tee /etc/resolv.conf
```

### 1.3 Backup and Remove Existing Configuration

```bash
sudo mv /etc/samba/smb.conf /etc/samba/smb.conf.orig
```

### 1.4 Provision Samba AD Domain

```bash
sudo samba-tool domain provision \
    --server-role=dc \
    --use-rfc2307 \
    --dns-backend=SAMBA_INTERNAL \
    --realm=YOURCOMPANY.LOCAL \
    --domain=YOURCOMPANY \
    --adminpass='P@ssw0rd123!'
```

### 1.5 Configure Kerberos

```bash
sudo cp /var/lib/samba/private/krb5.conf /etc/krb5.conf
```

### 1.6 Configure /etc/hosts

```bash
echo "10.0.1.4 victim1.yourcompany.local victim1" | sudo tee -a /etc/hosts
```

### 1.7 Start Samba AD DC Service

```bash
sudo systemctl unmask samba-ad-dc
sudo systemctl enable samba-ad-dc
sudo systemctl start samba-ad-dc
```

### 1.8 Verify Configuration

```bash
# Check domain level
sudo samba-tool domain level show

# Test DNS
host -t A victim1.yourcompany.local localhost

# Test Kerberos
kinit Administrator
# Enter password: P@ssw0rd123!

# View tickets
klist
```

### 1.9 Create Test Users (for Penetration Testing)

```bash
# Regular users
sudo samba-tool user create jsmith 'Summer2024!' \
    --given-name="John" --surname="Smith" \
    --mail-address="jsmith@yourcompany.local"

sudo samba-tool user create mwilson 'Welcome123!' \
    --given-name="Mary" --surname="Wilson" \
    --mail-address="mwilson@yourcompany.local"

# Backup administrator account (add to Domain Admins group)
sudo samba-tool user create admin.backup 'Backup@dmin1' \
    --given-name="Backup" --surname="Admin" \
    --mail-address="admin.backup@yourcompany.local"

sudo samba-tool group addmembers "Domain Admins" admin.backup

# Service account (for Kerberoasting demonstration)
sudo samba-tool user create svc_sql 'SqlService1!' \
    --given-name="SQL" --surname="Service" \
    --mail-address="svc_sql@yourcompany.local"

# Set SPN for service account (makes it Kerberoastable)
sudo samba-tool spn add MSSQLSvc/victim1.yourcompany.local:1433 svc_sql
```

### 1.10 List Created Users

```bash
sudo samba-tool user list
```

---

## Part 2: Configuring Domain Members (victim2, redirector, emailServer)

**Repeat the following steps on each domain member machine**

### 2.1 Install Required Packages

```bash
sudo apt update
sudo apt install -y samba smbclient krb5-user krb5-config winbind \
    libpam-winbind libnss-winbind acl attr dnsutils
```

### 2.2 Configure /etc/hosts

```bash
# Add DC resolution
echo "10.0.1.4 victim1.yourcompany.local victim1" | sudo tee -a /etc/hosts

# Add local machine resolution (modify according to actual IP)
# For victim2:
echo "10.0.1.5 victim2.yourcompany.local victim2" | sudo tee -a /etc/hosts
# For redirector:
echo "10.0.1.2 redirector.yourcompany.local redirector" | sudo tee -a /etc/hosts
# For emailServer:
echo "10.0.1.3 emailServer.yourcompany.local emailServer" | sudo tee -a /etc/hosts
```

### 2.3 Configure DNS to Point to DC

```bash
# Disable systemd-resolved
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved

# Configure resolv.conf
sudo bash -c 'cat > /etc/resolv.conf << EOF
search yourcompany.local
nameserver 10.0.1.4
EOF'
```

### 2.4 Configure Kerberos

Create `/etc/krb5.conf`:

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

### 2.5 Configure Samba (smb.conf)

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

### 2.6 Create Shared Directory

```bash
sudo mkdir -p /srv/samba/shared
sudo chmod 775 /srv/samba/shared
```

### 2.7 Join the Domain

```bash
# Stop services
sudo systemctl stop smbd nmbd winbind

# Join domain
sudo net ads join -U Administrator%'P@ssw0rd123!'
```

### 2.8 Configure NSS

Edit `/etc/nsswitch.conf` and modify the following lines:

```bash
sudo sed -i 's/^passwd:.*/passwd: files systemd winbind/' /etc/nsswitch.conf
sudo sed -i 's/^group:.*/group: files systemd winbind/' /etc/nsswitch.conf
```

### 2.9 Configure PAM (Allow Domain Users to Login)

```bash
sudo pam-auth-update --enable winbind

# Configure automatic home directory creation
echo "session required pam_mkhomedir.so skel=/etc/skel umask=0022" | \
    sudo tee -a /etc/pam.d/common-session
```

### 2.10 Start Services

```bash
sudo systemctl start smbd nmbd winbind
sudo systemctl enable smbd nmbd winbind
```

### 2.11 Verify Configuration

```bash
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
```

---

## Part 3: Verifying the Overall Environment

### 3.1 Verify on the DC

```bash
# List all domain members
sudo samba-tool computer list

# Check replication status
sudo samba-tool drs showrepl

# Test LDAP
ldapsearch -x -H ldap://localhost -b "DC=yourcompany,DC=local" "(objectClass=user)" cn
```

### 3.2 Test Kerberos Authentication on Domain Members

```bash
# Obtain TGT
kinit jsmith@YOURCOMPANY.LOCAL
# Password: Summer2024!

# View tickets
klist

# Access DC share
smbclient //victim1/netlogon -k
```

### 3.3 Test SMB Access

```bash
# Use password authentication
smbclient //victim1/netlogon -U jsmith%'Summer2024!'

# List shares
smbclient -L //victim1 -U jsmith%'Summer2024!'
```

---

## Part 4: Penetration Testing Scenarios

### 4.1 Available Test Users

| Username | Password | Role | Notes |
|----------|----------|------|-------|
| Administrator | P@ssw0rd123! | Domain Admin | Domain administrator |
| admin.backup | Backup@dmin1 | Domain Admin | Backup administrator |
| jsmith | Summer2024! | Domain User | Regular user |
| mwilson | Welcome123! | Domain User | Regular user |
| svc_sql | SqlService1! | Domain User | SQL service account with SPN |

### 4.2 Attackable Scenarios

1. **Password Spraying**
   - Spray common passwords against domain users

2. **Kerberoasting**
   - The svc_sql account has an SPN set, allowing TGS requests for offline cracking
   ```bash
   # Using impacket
   GetUserSPNs.py YOURCOMPANY.LOCAL/jsmith:'Summer2024!' -dc-ip 10.0.1.4 -request
   ```

3. **AS-REP Roasting**
   - Create users without pre-authentication requirements for testing

4. **Pass-the-Hash / Pass-the-Ticket**
   - Perform lateral movement after obtaining credentials

5. **DCSync**
   - Extract all password hashes using Domain Admin privileges

6. **SMB Relay**
   - Perform SMB relay attacks between domain members

---

## Troubleshooting

### Issue: Cannot Join Domain

```bash
# Check DNS resolution
nslookup victim1.yourcompany.local 10.0.1.4

# Check time synchronization
date
# If time difference is greater than 5 minutes, synchronize:
sudo ntpdate victim1.yourcompany.local
```

### Issue: Winbind Cannot Connect

```bash
# Check service status
sudo systemctl status winbind

# Restart services
sudo systemctl restart smbd nmbd winbind

# Check logs
sudo tail -f /var/log/samba/log.winbindd
```

### Issue: Domain Users Cannot Login

```bash
# Check PAM configuration
cat /etc/pam.d/common-auth | grep winbind

# Check NSS configuration
getent passwd | grep -i yourcompany
```

---

## Quick Reset

To reset the entire environment:

### Reset Domain Member:
```bash
sudo net ads leave -U Administrator%'P@ssw0rd123!'
sudo systemctl stop smbd nmbd winbind
sudo rm -rf /var/lib/samba/*
sudo rm /etc/samba/smb.conf
```

### Reset Domain Controller:
```bash
sudo systemctl stop samba-ad-dc
sudo rm -rf /var/lib/samba/*
sudo rm /etc/samba/smb.conf
# Then re-execute samba-tool domain provision
```