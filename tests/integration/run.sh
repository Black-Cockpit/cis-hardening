#!/usr/bin/env bash
#
# Drive one or all integration matrix entries through the full cycle:
#   up -> baseline audit -> harden -> reboot -> verify -> destroy
#
# Usage:
#   ./run.sh <entry>        run a single platforms.yml entry (e.g. rocky8_l1)
#   ./run.sh all            run every entry, aggregate a pass/fail summary
#   ./run.sh <entry> keep   run an entry but do not destroy the VM afterwards
#
# The playbooks run from the host over SSH using the inventory Vagrant
# generates, so no guest additions or synced folder are needed.
set -uo pipefail

# Resolve paths relative to this script so it runs from anywhere
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

# The disk grow uses Vagrant's built-in disks feature
export VAGRANT_EXPERIMENTAL="disks"
export ANSIBLE_CONFIG="$here/ansible.cfg"

reports_dir="$here/reports"
mkdir -p "$reports_dir"

# List the entries defined in the matrix
list_entries() {
    python3 -c "import yaml,sys; print('\n'.join(yaml.safe_load(open('platforms.yml'))['platforms']))"
}

# Read one field of one entry from platforms.yml
entry_field() {
    local entry_name="$1" field="$2"
    python3 -c "import yaml; entry=yaml.safe_load(open('platforms.yml'))['platforms']['$entry_name']; import json; print(json.dumps(entry.get('$field')))"
}

# Run one playbook against one entry, passing the entry's parameters as
# extra-vars. Returns the ansible-playbook exit code.
run_playbook() {
    local entry_name="$1" playbook="$2"
    local benchmark_mapping levels become_password
    benchmark_mapping="$(entry_field "$entry_name" benchmark_mapping | tr -d '"')"
    levels="$(entry_field "$entry_name" levels)"

    # The become password matches the one set on the vagrant user by the
    # set_password provisioner; it keeps become working after the hardening
    # role strips NOPASSWD from the sudoers files
    become_password="$(entry_field "$entry_name" become_password | tr -d '"')"
    [ "$become_password" = "null" ] && become_password="vagrant"

    # Capture the SSH parameters Vagrant generated for this VM
    vagrant ssh-config "$entry_name" > "$reports_dir/$entry_name.ssh_config" 2>/dev/null

    # The role's audit scripts use bash features (process substitution) that
    # fail under /bin/sh (which is bash in POSIX mode on EL). Run every
    # command/shell task under bash.
    # levels is a list, so it must be passed as a JSON object extra-var;
    # the bare "levels=[...]" key=value form is mangled by ansible on the
    # brackets/space and silently collapses the run to level 1 only.
    ansible-playbook \
        --inventory "$entry_name," \
        --extra-vars "entry_name=$entry_name" \
        --extra-vars "benchmark_mapping=$benchmark_mapping" \
        --extra-vars "{\"levels\": $levels}" \
        --extra-vars "ansible_become_password=$become_password" \
        --extra-vars "ansible_shell_executable=/bin/bash" \
        --ssh-common-args "-F $reports_dir/$entry_name.ssh_config" \
        --user vagrant \
        "playbooks/$playbook"
}

# Run the full cycle for one entry; echo PASS/FAIL and return a status
run_entry() {
    local entry_name="$1" keep="${2:-destroy}"
    echo "=== [$entry_name] up"
    vagrant up "$entry_name" || { echo "=== [$entry_name] FAIL (up)"; return 1; }

    echo "=== [$entry_name] baseline audit"
    run_playbook "$entry_name" audit.yml

    echo "=== [$entry_name] harden"
    run_playbook "$entry_name" harden.yml || { echo "=== [$entry_name] FAIL (harden)"; return 1; }

    # Reboot through Ansible, not `vagrant reload`: the hardening role
    # removes passwordless sudo, which Vagrant's graceful shutdown needs.
    echo "=== [$entry_name] reboot"
    run_playbook "$entry_name" reboot.yml || { echo "=== [$entry_name] FAIL (reboot)"; return 1; }

    echo "=== [$entry_name] verify"
    local verify_status
    run_playbook "$entry_name" verify.yml
    verify_status=$?

    # Tear the VM down unless the caller asked to keep it for inspection
    if [ "$keep" != "keep" ]; then
        echo "=== [$entry_name] destroy"
        vagrant destroy -f "$entry_name"
    fi

    if [ "$verify_status" -eq 0 ]; then
        echo "=== [$entry_name] PASS"
        return 0
    fi
    echo "=== [$entry_name] FAIL (verify)"
    return 1
}

# Require an argument
if [ "$#" -lt 1 ]; then
    echo "usage: $0 <entry|all> [keep]" >&2
    echo "entries:" >&2
    list_entries | sed 's/^/  /' >&2
    exit 2
fi

target="$1"
keep="${2:-destroy}"

# A single entry runs directly; 'all' loops the matrix and summarizes
if [ "$target" = "all" ]; then
    overall=0
    declare -A results
    while read -r entry_name; do
        [ -z "$entry_name" ] && continue
        if run_entry "$entry_name" "$keep"; then
            results[$entry_name]="PASS"
        else
            results[$entry_name]="FAIL"
            overall=1
        fi
    done < <(list_entries)

    echo
    echo "=== summary"
    for entry_name in "${!results[@]}"; do
        printf '  %-24s %s\n' "$entry_name" "${results[$entry_name]}"
    done
    exit "$overall"
else
    run_entry "$target" "$keep"
    exit $?
fi
