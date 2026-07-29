# Integration test harness

Prove the `cis_hardening.linux` role against a real system: a disposable
VirtualBox VM is booted, audited, hardened, rebooted, and re-audited, then
the result is asserted. Everything is driven by `run.sh`.

## Requirements

Install on the host:

- VirtualBox
- Vagrant
- Ansible (`ansible-playbook` on `PATH`)

### Free VT-x for VirtualBox (KVM hosts)

VirtualBox and KVM cannot both own the CPU's virtualization (VT-x) at the
same time. On a host where the KVM modules are loaded, VirtualBox fails to
boot the VM with:

```text
VBoxManage: error: VT-x is being used by another hypervisor (VERR_VMX_IN_VMX_ROOT_MODE)
```

Unload the KVM module before running the harness (Intel shown; use
`kvm_amd` on AMD):

```bash
sudo modprobe -r kvm_intel
```

It is safe to unload when nothing is using KVM (no running libvirt/QEMU
guests) and it is reversible with `sudo modprobe kvm_intel`. If the
unload reports the module is in use, stop the KVM guests first (for
example `sudo systemctl stop libvirtd`). The modules can reload on reboot
or when libvirt starts, so re-check before each session.

## Run it

```bash
cd tests/integration
./run.sh rocky8_l1
```

That command runs the whole cycle for the `rocky8_l1` entry:

1. `vagrant up` — boot Rocky 8 and set the vagrant password.
2. Baseline audit (no changes) → `reports/rocky8_l1-audit.json`.
3. Harden (apply remediation).
4. Reboot, so kernel, SELinux and GRUB changes take effect.
5. Verify — re-audit and assert compliance →
   `reports/rocky8_l1-verify.json`.
6. Destroy the VM.

### Other forms

```bash
./run.sh rocky8_l1 keep   # run, but keep the VM for inspection (vagrant ssh)
./run.sh all              # run every entry, print a pass/fail summary
./run.sh                  # print usage and list the entries
```

## Result

The run passes when every automated rule is compliant after hardening,
except the rules listed in `expected_failures/<entry>.yml`. Any other
rule left non-compliant fails the run and is named in the output.

Stock Vagrant boxes have a single root partition, so the
separate-partition rules (`1.1.2.x`) cannot pass and are allow-listed.
On the first run, expect a few extra rule IDs to be reported: read them
from the verify report and add the genuine "cannot pass on this box"
ones to the allowlist.

## Add a platform

Add an entry to `platforms.yml` and a matching
`expected_failures/<entry>.yml`. New OS versions, distributions, benchmark
versions and levels are all just matrix rows — no changes to `run.sh` or
the playbooks.

## Why the vagrant password

The role removes `NOPASSWD` from sudoers, so after hardening `sudo`
requires a password. The `set_password` provisioner sets one (default
`vagrant`, overridable per entry with `become_password`) and `run.sh`
passes the matching become password to Ansible, so the run keeps its sudo
access to the end.
