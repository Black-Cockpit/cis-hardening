# hasnimehdi91.cis_hardening

Ansible collection to **audit and remediate** systems against the
[CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks). It ships two
roles — one for Enterprise Linux hosts and one for NGINX — that assess every
applicable benchmark rule, report the result of each, and optionally apply
the remediation.

Both roles are **audit-first**: they default to a non-destructive assessment
and only change the system when you explicitly enable remediation. That
lets you use the collection as a compliance scanner, an enforcement tool, or
both.

> **Test before you enforce.** Hardening touches SSH, PAM, sudo, auditd, the
> firewall, kernel parameters, account policy and service configuration.
> Run in audit-only mode first, review the report, and validate remediation
> on a disposable machine before applying to production.

## Roles

- **linux** — CIS hardening for Enterprise Linux. See the
  [linux role documentation](roles/linux/README.md).
- **nginx** — CIS hardening for NGINX. See the
  [nginx role documentation](roles/nginx/README.md).

## Coverage

The `linux` role selects the benchmark automatically from the host's
distribution and major version:

| Distribution | Version 8 | Version 10 |
| --- | --- | --- |
| Red Hat Enterprise Linux | RHEL 8 v4.0.0 | RHEL 10 v1.0.1 |
| Rocky Linux | Rocky 8 v2.0.0 | Rocky 10 v1.0.0 |
| AlmaLinux | AlmaLinux 8 | AlmaLinux 10 |
| Oracle Linux | Oracle 8 | Oracle 10 |
| CentOS | CentOS 8 | CentOS 10 |

Each benchmark is evaluated at the requested CIS profile: `server_level_1`,
`server_level_2`, `workstation_level_1`, or `workstation_level_2`.

The `nginx` role covers the CIS NGINX Benchmark (v3.0.0) on Enterprise Linux
and Debian-family systems, including containerized NGINX, at the web-server,
load-balancer and reverse-proxy profiles.

## Requirements

- Python 3 on the control node.
- Ansible `8.6.1` or newer (ansible-core `2.15.8`+).
- The `ansible.posix` collection (used by the linux role).
- `become` privileges on the targets, running a supported platform.

## Installation

```bash
ansible-galaxy collection install hasnimehdi91.cis_hardening
```

## Usage

Audit an Enterprise Linux host (safe, non-destructive first run):

```yaml
- name: Audit hosts against CIS
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

Remediate, after reviewing the audit report:

```yaml
- name: Harden hosts against CIS
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

```bash
ansible-playbook playbook.yml
```

Per-role variables, profiles and examples (including NGINX) are documented
in each role: the [linux role](roles/linux/README.md) and the
[nginx role](roles/nginx/README.md).

## Testing

The collection includes Python unit tests for its custom modules and a
disposable-VM integration harness that hardens a real machine and verifies
the result. See the [tests documentation](tests/README.md).

## Links

- Repository: <https://github.com/Black-Cockpit/cis-hardening>
- Issues: <https://github.com/Black-Cockpit/cis-hardening/issues>
