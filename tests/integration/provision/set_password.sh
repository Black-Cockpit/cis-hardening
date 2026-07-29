#!/usr/bin/env bash
#
# Give the vagrant user a real password and unlock the account.
#
# The hardening rule "users must provide a password for privilege
# escalation" strips NOPASSWD from every sudoers file, including the
# vagrant drop-in. From that point on sudo prompts for the vagrant user's
# password, so the account must have one or the remainder of the harden
# run (and the later verify run) cannot use become.
#
# The password is supplied as the first argument and matched by the
# ansible_become_password the harness passes to ansible.
set -euo pipefail

# Use the supplied password, defaulting to 'vagrant' for the stock account
account_password="${1:-vagrant}"

# Set the password and make sure the account is not locked
echo "vagrant:${account_password}" | chpasswd
usermod -U vagrant

echo "set_password: vagrant account password configured"
