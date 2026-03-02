# Attack Emulation Lab Scenarios

## Design Philosophy
- Single-Host Scenarios: Focus on modeling the causal dependencies of individual attack steps, validating tool effectiveness and exploit feasibility.
- Multi-Host Scenarios: Evaluate the ability to plan complete attack chains, including decision-making for lateral movement and privilege escalation.
- Progressive Difficulty: Gradually increase complexity from deterministic attacks (known CVEs) to attacks that require reasoning and inference (e.g., misconfigurations).

## Single-Machine Scenarios
Single-Machine scenarios means that the victim environment consists of only one machine.
Together with the attacker’s environment (which also usually consists of a single machine), the entire cyber range typically includes two machines.

Here, we present a complete [example](struts2_lab/readme.md) demonstrating how to deploy the environments using SPHERE.

### 1. Demilitarized Zone (DMZ)
#### 1.1 Web Server Exploitation
**Goal**: Simulate an external attacker gaining initial access through web vulnerabilities.

1.1.A Vulnerable Struts2 Server:
-  CVE-2017-5638 (S2-045) ([deploy](struts2_lab/readme.md))
-  wpDiscuz 7.0.0–7.0.4 (CVE-2020-24186)
-  Confleunce (CVE-2023-22527)

#### 1.2 FTP Server Exploitation
**Objective**: Evaluate vulnerabilities and misconfigurations in file transfer services.

1.2.A: Anonymous FTP with Write Permission

1.2.B: vsftpd Backdoor
- **Vulnerability**: CVE-2011-2523 (vsftpd 2.3.4 backdoor)
- **Attack Path**:
```
FTP banner grabbing → Version identification → Backdoor trigger → Shell (port 6200)
```

#### Public-facing Workstation
Email Phishing Attack

#### Email Server

#### DNS Server

## Multi-Machine Scenarios
Multi-Machine scenarios refer to attack simulation environments that involve more than two machines. Typically, there are multiple victim machines, which can be used to simulate attack scenarios that require lateral movement.

Here, we also use an [example](setup_samba_ad/readme.md) to demonstrate how to deploy the environments using SPHERE.

### AD Domain

Please refer to this [doc](setup_samba_ad/ANSIBLE_DEPLOYMENT.md) to setup Samba4 Active Directory Lab Environment based on multiple machines.