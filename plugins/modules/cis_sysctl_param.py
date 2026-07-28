#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Audit module: verify a sysctl parameter's running and persisted value."""
from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.hasnimehdi91.cis_hardening.plugins.module_utils.cis_common import (
    sysctl_persisted_value,
    sysctl_running_value,
)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cis_sysctl_param
short_description: Audit a kernel parameter against accepted values
description:
  - Checks the running value (from /proc/sys) and the persisted value
    (last assignment across the given configuration files) of a sysctl
    parameter against a list of accepted values.
  - The module never changes the system; it only reports compliance.
options:
  name:
    description: Dotted sysctl parameter name.
    required: true
    type: str
  accepted:
    description: Values considered compliant.
    required: true
    type: list
    elements: str
  config_files:
    description: Sysctl configuration files in evaluation order.
    required: true
    type: list
    elements: path
author:
  - Hasni Mehdi (@hasnimehdi91)
'''

EXAMPLES = r'''
- name: Audit kernel.kptr_restrict
  hasnimehdi91.cis_hardening.cis_sysctl_param:
    name: kernel.kptr_restrict
    accepted: ["1", "2"]
    config_files: "{{ sysctl_conf_files }}"
  register: kptr_state
'''

RETURN = r'''
compliant:
  description: True when both the running and persisted values are accepted.
  returned: always
  type: bool
running:
  description: Current value from /proc/sys, or null when unreadable.
  returned: always
  type: str
persisted:
  description: Last persisted value across the configuration files, or null.
  returned: always
  type: str
'''


def main():
    """Entry point: read both values, compare and exit with the report."""
    # Declare the audit only module interface
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True),
            accepted=dict(type='list', elements='str', required=True),
            config_files=dict(type='list', elements='path', required=True),
        ),
        supports_check_mode=True,
    )

    # Read the running and the persisted value of the parameter
    parameter_name = module.params['name']
    running_value = sysctl_running_value(parameter_name)
    persisted_value = sysctl_persisted_value(parameter_name,
                                             module.params['config_files'])

    # Both values must be present and within the accepted set
    accepted_values = module.params['accepted']
    compliant = (running_value in accepted_values and
                 persisted_value in accepted_values)

    # Report the audit result without changing anything
    module.exit_json(changed=False, compliant=compliant,
                     running=running_value, persisted=persisted_value)


if __name__ == '__main__':
    main()
