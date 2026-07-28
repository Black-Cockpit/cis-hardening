#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Audit module: verify expected audit rules on disk and in the kernel."""
from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.hasnimehdi91.cis_hardening.plugins.module_utils.cis_common import (
    directory_config_lines,
    missing_audit_rules,
)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cis_auditd_rules
short_description: Audit the presence of auditd rules on disk and loaded
description:
  - Compares a list of expected audit rules against the rules present in
    the rules directory and, optionally, the rules loaded in the kernel
    (via C(auditctl -l)).
  - Rules are compared with collapsed whitespace so formatting never
    causes false findings.
  - The module never changes the system; it only reports compliance.
options:
  expected_rules:
    description: Audit rules that must be present.
    required: true
    type: list
    elements: str
  rules_dir:
    description: Directory holding the persistent rules files.
    default: /etc/audit/rules.d
    type: path
  check_loaded:
    description: Whether to also verify the rules loaded in the kernel.
    default: true
    type: bool
author:
  - Hasni Mehdi (@hasnimehdi91)
'''

EXAMPLES = r'''
- name: Audit sudoers change collection rules
  hasnimehdi91.cis_hardening.cis_auditd_rules:
    expected_rules:
      - "-w /etc/sudoers -p wa -k scope"
      - "-w /etc/sudoers.d -p wa -k scope"
  register: sudoers_rules_state
'''

RETURN = r'''
compliant:
  description: True when no expected rule is missing anywhere.
  returned: always
  type: bool
missing_on_disk:
  description: Expected rules absent from the rules directory.
  returned: always
  type: list
missing_loaded:
  description: Expected rules absent from the loaded kernel rules.
  returned: always
  type: list
'''


def main():
    """Entry point: compare expected rules with disk and kernel state."""
    # Declare the audit only module interface
    module = AnsibleModule(
        argument_spec=dict(
            expected_rules=dict(type='list', elements='str', required=True),
            rules_dir=dict(type='path', default='/etc/audit/rules.d'),
            check_loaded=dict(type='bool', default=True),
        ),
        supports_check_mode=True,
    )

    # Compare against the persistent rules files
    expected_rules = module.params['expected_rules']
    on_disk_lines = [line for _, line in directory_config_lines(
        module.params['rules_dir'], suffix='.rules')]
    absent_on_disk = missing_audit_rules(expected_rules, on_disk_lines)

    # Compare against the loaded kernel rules when requested; a failing
    # auditctl is an audit error, not a silent pass
    absent_loaded = []
    if module.params['check_loaded']:
        auditctl_binary = module.get_bin_path('auditctl', required=True)
        return_code, standard_out, standard_err = module.run_command(
            [auditctl_binary, '-l'])
        if return_code != 0:
            module.fail_json(msg='auditctl -l failed: %s' % standard_err.strip())
        absent_loaded = missing_audit_rules(expected_rules,
                                            standard_out.splitlines())

    # Report the audit result without changing anything
    module.exit_json(changed=False,
                     compliant=(not absent_on_disk and not absent_loaded),
                     missing_on_disk=absent_on_disk,
                     missing_loaded=absent_loaded)


if __name__ == '__main__':
    main()
