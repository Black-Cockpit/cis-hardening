#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Audit module: verify a file's mode, owner and group against a limit."""
from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.hasnimehdi91.cis_hardening.plugins.module_utils.cis_common import (
    mode_within_limit,
    stat_path,
)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cis_file_access
short_description: Audit file access (mode, owner, group) for a CIS rule
description:
  - Checks that a path grants no permission beyond a maximum mode and is
    owned by the expected user and group.
  - The module never changes the system; it only reports compliance.
options:
  path:
    description: Path to audit.
    required: true
    type: path
  max_mode:
    description: Most permissive allowed mode, octal string.
    required: true
    type: str
  owner:
    description: Expected owner name.
    default: root
    type: str
  group:
    description: Expected group name.
    default: root
    type: str
  allow_missing:
    description: Whether an absent path is considered compliant.
    default: true
    type: bool
author:
  - Hasni Mehdi (@hasnimehdi91)
'''

EXAMPLES = r'''
- name: Audit sshd_config access
  hasnimehdi91.cis_hardening.cis_file_access:
    path: /etc/ssh/sshd_config
    max_mode: "0600"
  register: sshd_config_access
'''

RETURN = r'''
compliant:
  description: Whether the path satisfies the access requirements.
  returned: always
  type: bool
exists:
  description: Whether the path exists.
  returned: always
  type: bool
failures:
  description: Human readable reasons for non compliance.
  returned: always
  type: list
'''


def evaluate_file_access(path_facts, max_mode, expected_owner,
                         expected_group, allow_missing):
    """Evaluate the compliance of a stat result against the expectations.

    :param path_facts: dict produced by stat_path
    :param max_mode: most permissive allowed octal mode string
    :param expected_owner: required owner name
    :param expected_group: required group name
    :param allow_missing: whether an absent path passes
    :returns: (compliant, failures) tuple
    """
    # An absent path is a policy decision handled by allow_missing
    if not path_facts['exists']:
        if allow_missing:
            return True, []
        return False, ['path does not exist']

    # Collect every violated expectation for the report
    failures = []
    if not mode_within_limit(path_facts['mode'], max_mode):
        failures.append('mode %s exceeds %s' % (path_facts['mode'], max_mode))
    if path_facts['owner'] != expected_owner:
        failures.append('owner %s is not %s' % (path_facts['owner'], expected_owner))
    if path_facts['group'] != expected_group:
        failures.append('group %s is not %s' % (path_facts['group'], expected_group))

    return len(failures) == 0, failures


def main():
    """Entry point: collect facts, evaluate and exit with the report."""
    # Declare the module interface; the module is audit only, so
    # check mode is trivially supported and nothing ever changes
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type='path', required=True),
            max_mode=dict(type='str', required=True),
            owner=dict(type='str', default='root'),
            group=dict(type='str', default='root'),
            allow_missing=dict(type='bool', default=True),
        ),
        supports_check_mode=True,
    )

    # Inspect the path and evaluate the expectations
    path_facts = stat_path(module.params['path'])
    compliant, failures = evaluate_file_access(
        path_facts,
        module.params['max_mode'],
        module.params['owner'],
        module.params['group'],
        module.params['allow_missing'],
    )

    # Report the audit result without changing anything
    module.exit_json(changed=False, compliant=compliant,
                     exists=path_facts['exists'], mode=path_facts['mode'],
                     owner=path_facts['owner'], group=path_facts['group'],
                     failures=failures)


if __name__ == '__main__':
    main()
