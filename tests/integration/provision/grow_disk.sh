#!/usr/bin/env bash
#
# Grow the guest root partition and filesystem into the unallocated space
# already present on the disk.
#
# The rockylinux/8 box ships a 20 GB disk but only partitions ~10 GB of it,
# leaving the root partition around 9 GB. This step extends the root
# partition and its filesystem to use the rest, so the hardening upgrades
# have room. It only touches the in-guest partition table and filesystem;
# it does NOT resize the virtual disk (that experimental feature corrupts
# the boot on this box).
#
# Layout is detected at run time (partition number and filesystem type) so
# the same script serves other boxes without tuning. All operations are
# no-ops when there is nothing to grow, so re-running is safe.
set -euo pipefail

# growpart lives in cloud-utils-growpart, which the base box may lack
if ! command -v growpart >/dev/null 2>&1; then
    dnf install -y cloud-utils-growpart >/dev/null
fi

# Identify the device, disk and partition backing the root mount
root_source="$(findmnt -no SOURCE /)"
root_fstype="$(findmnt -no FSTYPE /)"
whole_disk="/dev/$(lsblk -no PKNAME "$root_source" | head -1)"
partition_number="$(echo "$root_source" | grep -o '[0-9]*$')"

# Extend the partition into any free space that follows it (NOCHANGE if
# there is none)
growpart "$whole_disk" "$partition_number" || true

# Grow the mounted filesystem to fill the enlarged partition
if [ "$root_fstype" = "xfs" ]; then
    xfs_growfs / >/dev/null
else
    resize2fs "$root_source" >/dev/null
fi

# Report the resulting size in the provisioning log
echo "grow_disk: root filesystem is now $(findmnt -no SIZE /)"
