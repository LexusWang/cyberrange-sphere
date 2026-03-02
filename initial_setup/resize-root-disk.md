# Function:
resize-root-disk.sh is designed for Ubuntu 24.04 machines. By default, the 32 GB disk allocated to a virtual machine is not automatically expanded/mounted to the root (/) filesystem, which can make the system unusable. On such machines, the following commands usually need to be executed manually:
```
sudo partprobe
sudo resize2fs /dev/vda3
```
resize-root-disk.sh automates these commands and allows them to be executed in batch across multiple machines.

# Usage:
## Specify a list of machines
./resize-root-disk.sh victim1 victim2 victim3 victim4 victim5                  
## Use the default machine list (victim1–victim5)
./resize-root-disk.sh all
## Dry run (no actual changes; only show what would be executed)
./resize-root-disk.sh --dry-run victim1 victim2
## Process only selected machines
./resize-root-disk.sh victim1 victim3
