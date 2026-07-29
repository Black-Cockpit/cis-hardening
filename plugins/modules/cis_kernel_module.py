#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Audit module: verify a kernel module is not available per CIS rules."""
from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.hasnimehdi91.cis_hardening.plugins.module_utils.cis_common import (
    directory_config_lines,
    module_blacklisted,
    module_install_disabled,
    module_loaded,
    read_file_lines,
)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cis_kernel_module
short_description: Audit the availability state of a kernel module
description:
  - Reports whether a kernel module is loaded, disabled through an
    install override and deny listed, and whether that combination
    satisfies the CIS "module not available" requirement.
  - The module never changes the system; it only reports compliance.
options:
  name:
    description: Kernel module name.
    required: true
    type: str
  modprobe_dir:
    description: Directory holding the modprobe configuration.
    default: /etc/modprobe.d
    type: path
author:
  - Hasni Mehdi (@hasnimehdi91)
'''

EXAMPLES = r'''
- name: Audit the cramfs module
  hasnimehdi91.cis_hardening.cis_kernel_module:
    name: cramfs
  register: cramfs_state
'''

RETURN = r'''
compliant:
  description: True when the module is not loaded, or is both disabled and deny listed.
  returned: always
  type: bool
loaded:
  description: Whether the module is currently loaded.
  returned: always
  type: bool
install_disabled:
  description: Whether an install /bin/true or /bin/false override exists.
  returned: always
  type: bool
blacklisted:
  description: Whether a blacklist entry exists.
  returned: always
  type: bool
'''


def main():
    """Entry point: collect the module state and exit with the report."""
    # Declare the audit only module interface
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True),
            modprobe_dir=dict(type='path', default='/etc/modprobe.d'),
        ),
        supports_check_mode=True,
    )

    # Gather the three availability signals for the module
    module_name = module.params['name']
    modprobe_lines = directory_config_lines(module.params['modprobe_dir'])
    loaded = module_loaded(module_name, read_file_lines('/proc/modules'))
    install_disabled = module_install_disabled(module_name, modprobe_lines)
    blacklisted = module_blacklisted(module_name, modprobe_lines)

    # The library semantics: an unloaded module passes, a loaded module
    # passes only when it is both disabled and deny listed
    compliant = (not loaded) or (install_disabled and blacklisted)

    # Report the audit result without changing anything
    module.exit_json(changed=False, compliant=compliant, loaded=loaded,
                     install_disabled=install_disabled,
                     blacklisted=blacklisted)


if __name__ == '__main__':
    main()
