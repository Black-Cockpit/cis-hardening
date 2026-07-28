# -*- coding: utf-8 -*-
"""Shared pure helpers for the cis_hardening audit modules.

Every function in this file is side effect free (no host mutation): the
functions read files, parse command output, or evaluate values, so the
audit logic stays unit testable without an Ansible runtime.
"""
from __future__ import absolute_import, division, print_function

import os
import re
import stat as stat_module

__metaclass__ = type


def read_file_lines(file_path):
    """Return the lines of a file, or an empty list when it is absent.

    :param file_path: absolute path of the file to read
    :returns: list of lines without trailing newlines
    """
    # A missing or unreadable file is reported as empty content so the
    # caller can treat it as an absent configuration
    try:
        with open(file_path, 'r') as file_handle:
            return file_handle.read().splitlines()
    except (IOError, OSError):
        return []


def directory_config_lines(directory_path, suffix='.conf'):
    """Concatenate the lines of every configuration file in a directory.

    :param directory_path: directory holding configuration files
    :param suffix: only files with this suffix are read
    :returns: list of (file_path, line) tuples in file name order
    """
    # Collect the candidate files in deterministic order
    try:
        file_names = sorted(os.listdir(directory_path))
    except (IOError, OSError):
        return []

    # Read every matching file and keep the origin of each line
    collected_lines = []
    for file_name in file_names:
        if not file_name.endswith(suffix):
            continue
        file_path = os.path.join(directory_path, file_name)
        for line in read_file_lines(file_path):
            collected_lines.append((file_path, line))
    return collected_lines


def stat_path(file_path):
    """Describe a filesystem path for permission auditing.

    :param file_path: path to inspect
    :returns: dict with exists, mode (octal string), uid and gid;
              owner and group names are resolved when possible
    """
    # An absent path is reported explicitly instead of raising
    if not os.path.exists(file_path):
        return {'exists': False, 'mode': None, 'owner': None, 'group': None}

    # Collect the raw stat information
    stat_result = os.stat(file_path)
    mode_octal = format(stat_module.S_IMODE(stat_result.st_mode), '04o')

    # Resolve numeric ids to names, falling back to the numeric value
    try:
        import pwd
        owner_name = pwd.getpwuid(stat_result.st_uid).pw_name
    except (ImportError, KeyError):
        owner_name = str(stat_result.st_uid)
    try:
        import grp
        group_name = grp.getgrgid(stat_result.st_gid).gr_name
    except (ImportError, KeyError):
        group_name = str(stat_result.st_gid)

    return {'exists': True, 'mode': mode_octal,
            'owner': owner_name, 'group': group_name}


def mode_within_limit(mode_octal, max_mode_octal):
    """Check that a file mode grants no bit beyond the allowed maximum.

    :param mode_octal: actual mode as an octal string (e.g. '0644')
    :param max_mode_octal: most permissive allowed mode (e.g. '0640')
    :returns: True when no extra permission bit is set
    """
    # Any bit set in the actual mode but not in the allowed mask is a
    # violation
    actual_bits = int(mode_octal, 8)
    allowed_bits = int(max_mode_octal, 8)
    return (actual_bits & ~allowed_bits) == 0


def module_loaded(module_name, proc_modules_lines):
    """Check whether a kernel module appears in /proc/modules content.

    :param module_name: kernel module name (dashes and underscores are
                        equivalent for the kernel)
    :param proc_modules_lines: lines of /proc/modules
    :returns: True when the module is currently loaded
    """
    # The kernel normalizes dashes to underscores in /proc/modules
    normalized_name = module_name.replace('-', '_')
    for line in proc_modules_lines:
        first_field = line.split(' ', 1)[0] if line else ''
        if first_field.replace('-', '_') == normalized_name:
            return True
    return False


def module_install_disabled(module_name, modprobe_lines):
    """Check for an install override sending a module to /bin/true|false.

    :param module_name: kernel module name
    :param modprobe_lines: (file_path, line) tuples from modprobe.d
    :returns: True when an install /bin/true or /bin/false entry exists
    """
    # The entry may be commented in audits performed by the legacy tree,
    # so the optional leading # is accepted to stay behavior compatible
    install_pattern = re.compile(
        r'^(#)?\s*install\s+' + re.escape(module_name) + r'\s+/bin/(true|false)\b')
    return any(install_pattern.search(line) for _, line in modprobe_lines)


def module_blacklisted(module_name, modprobe_lines):
    """Check for a blacklist entry for a module in modprobe.d content.

    :param module_name: kernel module name
    :param modprobe_lines: (file_path, line) tuples from modprobe.d
    :returns: True when a blacklist entry exists
    """
    # The optional leading # mirrors the legacy audit expression
    blacklist_pattern = re.compile(
        r'^(#)?\s*blacklist\s+' + re.escape(module_name) + r'\b')
    return any(blacklist_pattern.search(line) for _, line in modprobe_lines)


def sysctl_running_value(parameter_name, proc_sys_root='/proc/sys'):
    """Read the running value of a sysctl parameter from /proc/sys.

    :param parameter_name: dotted sysctl name (e.g. net.ipv4.ip_forward)
    :param proc_sys_root: base directory (overridable for tests)
    :returns: the current value as a stripped string, or None
    """
    # The dotted name maps directly onto the /proc/sys hierarchy
    parameter_path = os.path.join(proc_sys_root, *parameter_name.split('.'))
    lines = read_file_lines(parameter_path)
    return lines[0].strip() if lines else None


def sysctl_persisted_value(parameter_name, config_files):
    """Find the persisted value of a sysctl parameter across files.

    :param parameter_name: dotted sysctl name
    :param config_files: configuration files in evaluation order
    :returns: the value of the last assignment found, or None
    """
    # Later assignments override earlier ones, matching systemd-sysctl
    assignment_pattern = re.compile(
        r'^\s*' + re.escape(parameter_name) + r'\s*=\s*(\S+)')
    persisted_value = None
    for config_file in config_files:
        for line in read_file_lines(config_file):
            matched = assignment_pattern.match(line)
            if matched:
                persisted_value = matched.group(1).strip()
    return persisted_value


def parse_sshd_config_dump(sshd_test_output):
    """Parse `sshd -T` output into a parameter dictionary.

    :param sshd_test_output: raw stdout of sshd -T
    :returns: dict mapping lowercase parameter names to their values
              (a repeated parameter keeps the first occurrence, as sshd
              applies the first obtained value)
    """
    # Every line is "parameter value..."; the parameter is lowercased
    # by sshd already but lowercasing again keeps the parser tolerant
    effective_settings = {}
    for line in sshd_test_output.splitlines():
        stripped = line.strip()
        if not stripped or ' ' not in stripped:
            continue
        parameter_name, parameter_value = stripped.split(' ', 1)
        parameter_name = parameter_name.lower()
        if parameter_name not in effective_settings:
            effective_settings[parameter_name] = parameter_value.strip()
    return effective_settings


def normalize_audit_rule(rule_line):
    """Normalize an audit rule line for comparison.

    :param rule_line: a single audit rule
    :returns: the rule with collapsed whitespace, or an empty string for
              comments and blank lines
    """
    # Comments and empty lines never participate in the comparison
    stripped = rule_line.strip()
    if not stripped or stripped.startswith('#'):
        return ''

    # Whitespace runs carry no meaning in audit rules
    return re.sub(r'\s+', ' ', stripped)


def missing_audit_rules(expected_rules, present_lines):
    """List the expected audit rules absent from the present lines.

    :param expected_rules: rules that must exist
    :param present_lines: rule lines found on the system
    :returns: the normalized expected rules that were not found
    """
    # Normalize both sides so formatting differences never matter
    present_normalized = {normalize_audit_rule(line) for line in present_lines}
    present_normalized.discard('')

    # Keep the expected order in the report for readability
    missing_rules = []
    for expected_rule in expected_rules:
        normalized_expected = normalize_audit_rule(expected_rule)
        if normalized_expected and normalized_expected not in present_normalized:
            missing_rules.append(normalized_expected)
    return missing_rules
