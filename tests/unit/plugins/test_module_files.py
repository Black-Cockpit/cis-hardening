# -*- coding: utf-8 -*-
"""Structural tests for the audit modules under plugins/modules/.

Each module must compile and carry valid YAML in its DOCUMENTATION,
EXAMPLES and RETURN blocks, so ansible-doc can always render them.
"""
from __future__ import absolute_import, division, print_function

import glob
import os
import py_compile
import re
import unittest

import yaml

__metaclass__ = type

# Locate every module file in the repository layout
REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
MODULE_FILES = sorted(
    glob.glob(os.path.join(REPO_ROOT, 'plugins', 'modules', 'cis_*.py')))

# The documentation blocks every module must define
REQUIRED_BLOCKS = ('DOCUMENTATION', 'EXAMPLES', 'RETURN')


class TestModuleFiles(unittest.TestCase):
    """Compile and documentation checks for all audit modules."""

    def test_all_five_modules_exist(self):
        """The committed module set is complete."""
        module_names = [os.path.basename(path) for path in MODULE_FILES]
        self.assertEqual(module_names, [
            'cis_auditd_rules.py', 'cis_file_access.py',
            'cis_kernel_module.py', 'cis_sshd_config.py',
            'cis_sysctl_param.py'])

    def test_modules_compile(self):
        """Every module file compiles cleanly."""
        # Compile to a throwaway location so no __pycache__ lands in the
        # repository
        import tempfile
        for module_path in MODULE_FILES:
            with tempfile.NamedTemporaryFile(suffix='.pyc') as compiled_file:
                py_compile.compile(module_path, cfile=compiled_file.name,
                                   doraise=True)

    def test_documentation_blocks_are_valid_yaml(self):
        """DOCUMENTATION, EXAMPLES and RETURN parse as YAML."""
        for module_path in MODULE_FILES:
            source_text = open(module_path).read()

            # Extract each raw triple quoted block and parse it;
            # DOCUMENTATION and RETURN are mappings, EXAMPLES is a task list
            for block_name in REQUIRED_BLOCKS:
                matched = re.search(
                    block_name + r" = r'''(.*?)'''", source_text, re.S)
                self.assertIsNotNone(
                    matched, '%s missing in %s' % (block_name, module_path))
                parsed = yaml.safe_load(matched.group(1))
                expected_type = list if block_name == 'EXAMPLES' else dict
                self.assertIsInstance(
                    parsed, expected_type,
                    '%s in %s has the wrong shape' % (block_name, module_path))


if __name__ == '__main__':
    unittest.main()
