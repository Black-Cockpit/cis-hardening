# -*- coding: utf-8 -*-
"""Unit tests for the pure helpers in plugins/module_utils/cis_common.py.

The helpers are imported straight from their file path so the tests run
from the build venv without installing the collection:
    build.venv/bin/python -m unittest discover -s tests/unit -v
"""
from __future__ import absolute_import, division, print_function

import importlib.util
import os
import tempfile
import unittest

__metaclass__ = type

# Load the module under test directly from the repository layout
REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
MODULE_PATH = os.path.join(REPO_ROOT, 'plugins', 'module_utils', 'cis_common.py')
SPEC = importlib.util.spec_from_file_location('cis_common', MODULE_PATH)
cis_common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cis_common)


class TestFileHelpers(unittest.TestCase):
    """Behavior of the file reading and stat helpers."""

    def test_read_file_lines_returns_content(self):
        """An existing file is returned as a list of lines."""
        # Create a two line file and read it back
        with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
            temp_file.write('first\nsecond\n')
        self.addCleanup(os.unlink, temp_file.name)

        self.assertEqual(cis_common.read_file_lines(temp_file.name),
                         ['first', 'second'])

    def test_read_file_lines_missing_file_is_empty(self):
        """A missing file reads as empty content instead of raising."""
        self.assertEqual(cis_common.read_file_lines('/no/such/file'), [])

    def test_directory_config_lines_filters_and_orders(self):
        """Only matching suffixes are read, in file name order."""
        # Build a directory with two conf files and one ignored file
        temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__('shutil').rmtree(temp_dir))
        for file_name, content in (('b.conf', 'bravo'), ('a.conf', 'alpha'),
                                   ('ignored.txt', 'nope')):
            with open(os.path.join(temp_dir, file_name), 'w') as file_handle:
                file_handle.write(content + '\n')

        collected = cis_common.directory_config_lines(temp_dir)
        self.assertEqual([line for _, line in collected], ['alpha', 'bravo'])

    def test_directory_config_lines_missing_directory(self):
        """A missing directory reads as no content."""
        self.assertEqual(cis_common.directory_config_lines('/no/such/dir'), [])

    def test_stat_path_reports_mode_and_existence(self):
        """An existing file reports a four digit octal mode."""
        # Create a file with a known mode
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            pass
        self.addCleanup(os.unlink, temp_file.name)
        os.chmod(temp_file.name, 0o640)

        facts = cis_common.stat_path(temp_file.name)
        self.assertTrue(facts['exists'])
        self.assertEqual(facts['mode'], '0640')

    def test_stat_path_missing(self):
        """A missing path is reported as absent."""
        self.assertEqual(cis_common.stat_path('/no/such/file'),
                         {'exists': False, 'mode': None,
                          'owner': None, 'group': None})


class TestModeLimit(unittest.TestCase):
    """Behavior of the permission mask comparison."""

    def test_equal_mode_is_within_limit(self):
        """A mode identical to the limit passes."""
        self.assertTrue(cis_common.mode_within_limit('0640', '0640'))

    def test_stricter_mode_is_within_limit(self):
        """A stricter mode passes."""
        self.assertTrue(cis_common.mode_within_limit('0600', '0640'))

    def test_looser_mode_violates_limit(self):
        """Any extra bit fails, including setgid style bits."""
        self.assertFalse(cis_common.mode_within_limit('0644', '0640'))
        self.assertFalse(cis_common.mode_within_limit('2640', '0640'))


class TestKernelModuleHelpers(unittest.TestCase):
    """Behavior of the kernel module state helpers."""

    def test_module_loaded_matches_and_normalizes(self):
        """Loaded detection matches names with dash normalization."""
        proc_lines = ['firewire_core 16384 0 - Live 0x0', 'ext4 512 1']
        self.assertTrue(cis_common.module_loaded('firewire-core', proc_lines))
        self.assertTrue(cis_common.module_loaded('ext4', proc_lines))
        self.assertFalse(cis_common.module_loaded('cramfs', proc_lines))

    def test_install_disabled_accepts_true_and_false(self):
        """Both /bin/true and /bin/false overrides are recognized."""
        lines = [('f', 'install cramfs /bin/true'),
                 ('f', 'install udf /bin/false')]
        self.assertTrue(cis_common.module_install_disabled('cramfs', lines))
        self.assertTrue(cis_common.module_install_disabled('udf', lines))
        self.assertFalse(cis_common.module_install_disabled('hfs', lines))

    def test_install_disabled_ignores_other_modules_prefix(self):
        """A module name is matched as a word, not as a prefix."""
        lines = [('f', 'install cramfs2 /bin/true')]
        self.assertFalse(cis_common.module_install_disabled('cramfs', lines))

    def test_blacklisted(self):
        """Blacklist entries are recognized, absent ones are not."""
        lines = [('f', 'blacklist cramfs')]
        self.assertTrue(cis_common.module_blacklisted('cramfs', lines))
        self.assertFalse(cis_common.module_blacklisted('udf', lines))


class TestSysctlHelpers(unittest.TestCase):
    """Behavior of the sysctl value helpers."""

    def test_running_value_reads_proc_hierarchy(self):
        """The dotted name maps onto the /proc/sys layout."""
        # Build a fake /proc/sys hierarchy with one parameter
        fake_root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__('shutil').rmtree(fake_root))
        parameter_dir = os.path.join(fake_root, 'net', 'ipv4')
        os.makedirs(parameter_dir)
        with open(os.path.join(parameter_dir, 'ip_forward'), 'w') as file_handle:
            file_handle.write('0\n')

        self.assertEqual(
            cis_common.sysctl_running_value('net.ipv4.ip_forward', fake_root),
            '0')
        self.assertIsNone(
            cis_common.sysctl_running_value('net.ipv4.absent', fake_root))

    def test_persisted_value_last_assignment_wins(self):
        """The last assignment across the file list is authoritative."""
        # Two files assign the same parameter with different values
        first_file = tempfile.NamedTemporaryFile('w', delete=False)
        first_file.write('net.ipv4.ip_forward = 1\n')
        first_file.close()
        second_file = tempfile.NamedTemporaryFile('w', delete=False)
        second_file.write('# a comment\nnet.ipv4.ip_forward=0\n')
        second_file.close()
        self.addCleanup(os.unlink, first_file.name)
        self.addCleanup(os.unlink, second_file.name)

        persisted = cis_common.sysctl_persisted_value(
            'net.ipv4.ip_forward', [first_file.name, second_file.name])
        self.assertEqual(persisted, '0')

    def test_persisted_value_absent(self):
        """A parameter assigned nowhere reports None."""
        self.assertIsNone(
            cis_common.sysctl_persisted_value('kernel.absent', []))


class TestSshdParsing(unittest.TestCase):
    """Behavior of the sshd -T output parser."""

    def test_parse_keeps_first_occurrence(self):
        """The first value of a repeated parameter is kept."""
        dump = 'usepam yes\nmaxauthtries 4\nmaxauthtries 6\n'
        parsed = cis_common.parse_sshd_config_dump(dump)
        self.assertEqual(parsed['usepam'], 'yes')
        self.assertEqual(parsed['maxauthtries'], '4')

    def test_parse_ignores_blank_lines(self):
        """Blank and value-less lines never produce entries."""
        parsed = cis_common.parse_sshd_config_dump('\nsolo\nport 22\n')
        self.assertEqual(parsed, {'port': '22'})


class TestAuditRules(unittest.TestCase):
    """Behavior of the audit rules normalization and comparison."""

    def test_normalize_collapses_whitespace(self):
        """Whitespace runs collapse; comments and blanks are dropped."""
        self.assertEqual(
            cis_common.normalize_audit_rule('-w  /etc/sudoers   -p wa -k scope'),
            '-w /etc/sudoers -p wa -k scope')
        self.assertEqual(cis_common.normalize_audit_rule('# comment'), '')
        self.assertEqual(cis_common.normalize_audit_rule('   '), '')

    def test_missing_rules_reported_in_order(self):
        """Missing rules keep their expected order; found ones drop out."""
        expected = ['-w /etc/sudoers -p wa -k scope',
                    '-w /etc/sudoers.d -p wa -k scope']
        present = ['-w   /etc/sudoers -p wa -k scope']

        missing = cis_common.missing_audit_rules(expected, present)
        self.assertEqual(missing, ['-w /etc/sudoers.d -p wa -k scope'])


if __name__ == '__main__':
    unittest.main()
