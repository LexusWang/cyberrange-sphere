# Function:
resize-root-disk.sh is designed for Ubuntu 24.04 machines. By default, the 32 GB disk allocated to a virtual machine is not automatically expanded/mounted to the root (/) filesystem, which can make the system unusable. On such machines, the following commands usually need to be executed manually:
```
sudo partprobe
sudo resize2fs /dev/vda3
```
resize-root-disk.sh automates these commands and allows them to be executed in batch across multiple machines.

setup-home-disk.sh is used to mount a required extra disk, typically for machines that request disk space beyond the default size. By default, this extra disk is mounted at the /home directory.

# Usage:
## Specify a list of machines
./setup-home-disk.sh victim1 victim2 victim3 victim4 victim5                  
## Use the default machine list (victim1–victim5)
./setup-home-disk.sh all
## Dry run (no actual changes; only show what would be executed)
./setup-home-disk.sh --dry-run victim1 victim2
## Process only selected machines
./setup-home-disk.sh victim1 victim3

# Script Features
- Executes sequentially on each machine and shows progress (e.g., [1/5])
- Checks SSH connectivity and the existence of /dev/vdb before execution
- Detects whether the disk has already been configured to avoid repeated operations
- Displays a summary of execution results (number of successes/failures)
- Supports --dry-run mode for safe testing
- Colorized output for easy status identification

./resize-root-disk.sh victimDC victim1 victim2 victim3 victim4 victim5
./setup-home-disk.sh attacker victimDC victim1 victim2 victim3 victim4 victim5
