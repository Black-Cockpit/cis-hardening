Ansible Collection - hasnimehdi91.cis_hardening
=========

This collection provides roles for cis benchmark.

## Installation

Requirements: `python 3`, `ansible-8.6.1` or higher version

```bash
ansible-galaxy collection install hasnimehdi91.cis_hardening
```


## Usage

```yaml
- name: System hardening
  hosts: all
  gather_facts: yes
  any_errors_fatal: yes
  become: yes
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

