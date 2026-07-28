#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Audit module: verify an effective sshd parameter via sshd -T."""
from __future__ import absolute_import, division, print_function

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.hasnimehdi91.cis_hardening.plugins.module_utils.cis_common import (
    parse_sshd_config_dump,
)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cis_sshd_config
short_description: Audit an effective sshd configuration parameter
description:
  - Runs C(sshd -T) and compares the effective value of one parameter
    against a list of accepted values (case insensitive).
  - When the ssh server is not installed the rule is reported compliant,
    matching the behavior of the shell based checks it replaces.
  - The module never changes the system; it only reports compliance.
options:
  parameter:
    description: sshd configuration parameter name.
    required: true
    type: str
  accepted:
    description: Values considered compliant (case insensitive).
    required: true
    type: list
    elements: str
author:
  - Hasni Mehdi (@hasnimehdi91)
'''

EXAMPLES = r'''
- name: Audit GSSAPIAuthentication
  hasnimehdi91.cis_hardening.cis_sshd_config:
    parameter: gssapiauthentication
    accepted: ["no"]
  register: gssapi_state
'''

RETURN = r'''
compliant:
  description: True when the effective value is accepted or sshd is absent.
  returned: always
  type: bool
value:
  description: Effective parameter value, or null when unavailable.
  returned: always
  type: str
sshd_present:
  description: Whether an ssh server configuration was found.
  returned: always
  type: bool
'''


def main():
    """Entry point: dump the effective config, compare and report."""
    # Declare the audit only module interface
    module = AnsibleModule(
        argument_spec=dict(
            parameter=dict(type='str', required=True),
            accepted=dict(type='list', elements='str', required=True),
        ),
        supports_check_mode=True,
    )

    # A host without an ssh server is compliant by convention, exactly
    # like the shell checks this module replaces
    if not os.path.isdir('/etc/ssh'):
        module.exit_json(changed=False, compliant=True, value=None,
                         sshd_present=False)

    # Dump the effective configuration; a failing sshd -T is reported
    # as an error because the audit cannot be trusted without it
    sshd_binary = module.get_bin_path('sshd', required=True)
    return_code, standard_out, standard_err = module.run_command(
        [sshd_binary, '-T'])
    if return_code != 0:
        module.fail_json(msg='sshd -T failed: %s' % standard_err.strip())

    # Compare the effective value against the accepted set
    effective_settings = parse_sshd_config_dump(standard_out)
    parameter_name = module.params['parameter'].lower()
    effective_value = effective_settings.get(parameter_name)
    accepted_values = [value.lower() for value in module.params['accepted']]
    compliant = (effective_value is not None and
                 effective_value.lower() in accepted_values)

    # Report the audit result without changing anything
    module.exit_json(changed=False, compliant=compliant,
                     value=effective_value, sshd_present=True)


if __name__ == '__main__':
    main()
