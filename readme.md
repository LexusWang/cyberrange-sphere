# Attack Emulation Lab Scenarios

## Design Philosophy
- Single-Host Scenarios: Focus on modeling the causal dependencies of individual attack steps, validating tool effectiveness and exploit feasibility.
- Multi-Host Scenarios: Evaluate the ability to plan complete attack chains, including decision-making for lateral movement and privilege escalation.
- Progressive Difficulty: Gradually increase complexity from deterministic attacks (known CVEs) to attacks that require reasoning and inference (e.g., misconfigurations).

## Single-Machine Scenarios
Single-Machine scenarios means that the victim environment consists of only one machine.
Together with the attacker’s environment (which also usually consists of a single machine), the entire cyber range typically includes two machines.

Here, we present a complete [example](struts2_lab/readme.md) demonstrating how to deploy the environments using SPHERE.

### Deployed Scenarios

| Lab | CVE | Service | Attack Type | Link |
|-----|-----|---------|-------------|------|
| Struts2 RCE | CVE-2017-5638 | Apache Struts 2.3.x | Remote code execution via crafted Content-Type header | [deploy](struts2_lab/readme.md) |
| Heartbleed | CVE-2014-0160 | nginx 1.6.3 + OpenSSL 1.0.1f | TLS heartbeat memory leak (credentials, keys) | [deploy](heartbleed_lab/readme.md) |
| Log4Shell | CVE-2021-44228 | Apache Solr 8.11.0 + Log4j 2.14.1 | JNDI injection → remote code execution | [deploy](log4shell_lab/readme.md) |
| Redis Unauthorized Access | — | Redis 6.x (no auth) | Unauthenticated access → SSH key injection | [deploy](redis_unauth_lab/readme.md) |
| SambaCry | CVE-2017-7494 | Samba 4.5.9 | Writable share → shared library upload → RCE | [deploy](sambacry_lab/readme.md) |

### Planned Scenarios

#### Web Server Exploitation
-  wpDiscuz 7.0.0–7.0.4 (CVE-2020-24186)
-  Confluence (CVE-2023-22527)

#### FTP Server Exploitation
- Anonymous FTP with Write Permission
- vsftpd 2.3.4 Backdoor (CVE-2011-2523)

#### Other
- Email Phishing Attack
- DNS Server Exploitation

## Multi-Machine Scenarios
Multi-Machine scenarios refer to attack simulation environments that involve more than two machines. Typically, there are multiple victim machines, which can be used to simulate attack scenarios that require lateral movement.

Here, we also use an [example](setup_samba_ad/readme.md) to demonstrate how to deploy the environments using SPHERE.

### AD Domain

Please refer to this [doc](setup_samba_ad/ANSIBLE_DEPLOYMENT.md) to setup Samba4 Active Directory Lab Environment based on multiple machines.