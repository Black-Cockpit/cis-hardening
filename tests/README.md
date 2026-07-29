# Tests

The collection ships two kinds of tests: fast Python unit tests for the
custom modules, and a disposable-VM integration harness that hardens a real
machine and verifies the result.

## Unit tests

The custom audit modules (`cis_file_access`, `cis_kernel_module`,
`cis_sysctl_param`, `cis_sshd_config`, `cis_auditd_rules`) are built on
pure, side-effect-free helper functions. The unit tests exercise those
helpers and confirm every module compiles and carries valid documentation.
They run in seconds, need no VM, and use only the Python standard library.

Run them from the collection root:

```bash
python -m unittest discover -s tests/unit
```

Add `-v` for one line per test.

## Integration tests

The integration harness proves the `linux` role against a real system: it
boots a throwaway virtual machine, takes a baseline audit, hardens the
machine, reboots it, then re-audits and asserts that every automated rule
is compliant apart from a documented, per-machine allowlist. It uses
VirtualBox and Vagrant, and drives the role over SSH from the host.

The set of machines to test is a matrix — each entry pins a distribution,
benchmark, and CIS profile. Adding a new platform is a new matrix entry
plus its allowlist, with no changes to the harness itself.

Run one entry, or the whole matrix:

```bash
cd tests/integration
./run.sh rocky8_l2      # a single entry, full cycle
./run.sh all            # every entry, with a pass/fail summary
```

See the [integration test documentation](integration/README.md) for the
prerequisites (including the VirtualBox/KVM note), how the pass/fail
assertion works, and how to add a platform.
