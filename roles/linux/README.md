# Linux CIS hardening

Audit and remediate Enterprise Linux hosts against the
[CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks). The role reads
the host's distribution and major version, selects the matching benchmark,
and runs every rule that applies to the requested profile — reporting the
result of each rule and, when enabled, remediating the ones that fail.

> **Test before you enforce.** Hardening changes SSH, PAM, sudo, auditd,
> the firewall, kernel parameters and account policies. Always run in
> audit-only mode first, review the report, and validate remediation on a
> disposable machine before touching production.

## Supported platforms and benchmarks

The benchmark is chosen automatically from `ansible_distribution` and
`ansible_distribution_major_version`:

| Distribution | Version 8 | Version 10 |
| --- | --- | --- |
| Red Hat Enterprise Linux | RHEL 8 v4.0.0 | RHEL 10 v1.0.1 |
| Rocky Linux | Rocky 8 v2.0.0 | Rocky 10 v1.0.0 |
| AlmaLinux | AlmaLinux 8 | AlmaLinux 10 |
| Oracle Linux | Oracle 8 | Oracle 10 |
| CentOS | CentOS 8 | CentOS 10 |

To force a specific benchmark regardless of the detected distribution, set
`benchmark_mapping` (see below).

## Profiles (levels)

CIS defines two hardening levels and two system profiles. Request any
combination through the `levels` variable:

- `server_level_1`, `server_level_2`
- `workstation_level_1`, `workstation_level_2`

Level 1 is a conservative baseline with minimal operational impact. Level 2
is defense-in-depth and is stricter (it can affect usability). A level-2
request runs level-1 rules as well.

## Requirements

- A control node with Ansible (see the collection requirements).
- The target runs a supported distribution and major version (8 or 10).
- `become` privileges on the target.
- The `ansible.posix` collection (used for `sysctl` and `selinux`).

## Role variables

| Variable | Default | Description |
| --- | --- | --- |
| `audit_only` | `true` | When `true`, only assess and report — no changes. Set to `false` to remediate. |
| `levels` | `[workstation_level_1, workstation_level_2]` | The CIS profiles to evaluate. Set to the server levels for server hardening. |
| `benchmark_mapping` | *(auto)* | Force a specific benchmark (e.g. `rhel8_v4`, `rocky10_v1`) instead of the auto-selected one. |
| `warning_banner` | Authorized-use notice | Text written to the login banners (`/etc/issue`, `/etc/issue.net`, `/etc/motd`). |
| `site_policy` | *(unset)* | Site-specific values the role cannot decide on its own (for example `site_policy.root_password`). |
| `cis_defaults` | see defaults | Tunable values used by individual rules (sshd timeouts, NTP servers, audit tool paths, etc.). |
| `reboot_required` | `false` | Tracks whether applied changes need a reboot to fully take effect. |

Remediation runs only when `audit_only: false` **and** the rule is
non-compliant. Rules that require a site decision (a bootloader password,
an SSH access list, a separate partition layout) are reported as advisory
and are never changed automatically.

## Results

Every rule appends an entry to `audit_result`, which the role prints at the
end of the run. Each entry carries the rule id, the benchmark number and
verbatim title, the benchmark name and version, whether it is scored and
automated, and the compliance status. This is the audit report you review
before enabling remediation, and the evidence you keep after.

## Usage

Audit only (safe first run, server level 1 + 2):

```yaml
- name: Audit Linux hosts against CIS
  hosts: all
  become: true
  gather_facts: true
  roles:
    - name: hasnimehdi91.cis_hardening.linux
      vars:
        audit_only: true
        levels:
          - server_level_1
          - server_level_2
```

Remediate (after reviewing the audit report):

```yaml
- name: Harden Linux hosts against CIS
  hosts: all
  become: true
  gather_facts: true
  any_errors_fatal: true
  roles:
    - name: hasnimehdi91.cis_hardening.linux
      vars:
        audit_only: false
        levels:
          - server_level_1
```

Force a specific benchmark (for example, evaluate an AlmaLinux host against
the RHEL rule set):

```yaml
      vars:
        benchmark_mapping: rhel8_v4
```

A reboot is recommended after remediation so kernel parameters, SELinux
mode and bootloader changes take full effect.

## Testing

This role is exercised by a disposable-VM integration harness and a set of
Python unit tests. See the [tests documentation](../../tests/README.md) for
how to run them.
