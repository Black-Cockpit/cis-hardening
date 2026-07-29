# --------------------------------------------------------------------------------------------------
# Makefile — Black Cockpit CIS hardening test orchestration
# --------------------------------------------------------------------------------------------------
# Wraps the integration harness (tests/integration/run.sh) behind stable
# snake_case targets. Every operational target depends on check_virtual_env so
# the Python virtual environment is provisioned on demand, and every target
# that runs a test activates that environment before calling the harness.
# --------------------------------------------------------------------------------------------------

# Define the shell to be used for commands
SHELL := /bin/bash

# Extract the name of the current Makefile
# Useful for debugging or referencing the Makefile itself
CURRENT_MK := $(lastword $(MAKEFILE_LIST))

# --------------------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------------------

# Virtual environment directory name
# Notes:
#   - (Re)created by install_virtual_env and used by all subsequent targets.
#   - Unquoted on purpose: a quoted value embeds the quotes in the path and
#     breaks the existence check in check_virtual_env.
VIRTUAL_ENV_DIR := ops.venv

# Directory context for the project
# Notes:
#   - All relative paths are resolved from this root path.
#   - If running make from another directory, adjust accordingly.
CONF_DIR_CONTEXT := .

# Python version used to build the virtual environment
PYTHON_VERSION_12 := python3.12

# Collection build output directory
# Notes:
#   - Holds the namespace-name-version.tar.gz artifact produced by
#     build_collection.
#   - Listed in the galaxy.yml build_ignore, so a previous artifact is never
#     packaged into the next one.
COLLECTION_BUILD_DIR := $(CONF_DIR_CONTEXT)/dist

# Collection identity, read from galaxy.yml
# Notes:
#   - Scraped with awk rather than a YAML parser so the Makefile can be
#     parsed before the virtual environment exists.
#   - COLLECTION_ARTIFACT is the file ansible-galaxy produces for the version
#     currently declared in galaxy.yml; bump the version there, never here.
COLLECTION_METADATA := $(CONF_DIR_CONTEXT)/galaxy.yml
COLLECTION_NAMESPACE := $(shell awk '/^namespace:/ {print $$2}' $(COLLECTION_METADATA) 2>/dev/null)
COLLECTION_NAME := $(shell awk '/^name:/ {print $$2}' $(COLLECTION_METADATA) 2>/dev/null)
COLLECTION_VERSION := $(shell awk '/^version:/ {print $$2}' $(COLLECTION_METADATA) 2>/dev/null)
COLLECTION_ARTIFACT := $(COLLECTION_BUILD_DIR)/$(COLLECTION_NAMESPACE)-$(COLLECTION_NAME)-$(COLLECTION_VERSION).tar.gz

# Ansible Galaxy publication settings
# Notes:
#   - GALAXY_TOKEN is the API token from https://galaxy.ansible.com/ui/token.
#     Pass it in the environment (export GALAXY_TOKEN=...) rather than on the
#     make command line, so it stays out of the shell history.
#   - Leave GALAXY_TOKEN empty to let ansible-galaxy fall back to the token
#     stored in ~/.ansible/galaxy_token.
#   - GALAXY_SERVER overrides the target server for a private Automation Hub;
#     empty means the public galaxy.ansible.com.
GALAXY_TOKEN ?=
GALAXY_SERVER ?=

# Hand the token to the recipe through the environment, so it is never part
# of the ansible-galaxy command line make prints, and works whether it was
# exported by the caller or passed as make GALAXY_TOKEN=...
export GALAXY_TOKEN

# Integration harness location
# Notes:
#   - run.sh resolves its own paths, so it can be invoked from anywhere; the
#     targets below still cd into the harness directory to keep relative
#     report and inventory paths predictable.
INTEGRATION_DIR := $(CONF_DIR_CONTEXT)/tests/integration
INTEGRATION_RUNNER := ./run.sh

# Integration matrix file and the entry names it declares
# Notes:
#   - The entry list is scraped with grep rather than a YAML parser so the
#     Makefile can be parsed before the virtual environment exists.
#   - Matches the two-space indented mapping keys under `platforms:`.
INTEGRATION_MATRIX := $(INTEGRATION_DIR)/platforms.yml
INTEGRATION_ENTRIES := $(shell grep -oE '^  [A-Za-z0-9_]+:' $(INTEGRATION_MATRIX) 2>/dev/null | tr -d ' :')

# Keep the VM after a run instead of destroying it
# Notes:
#   - Set to `keep` on the command line to hand the second run.sh argument
#     through: make integration_test_rocky8_l1 KEEP=keep
KEEP ?= destroy

# Entry name consumed by the generic integration_test target
ENTRY ?=

# Targets that are not associated with files
.PHONY: \
    install_virtual_env \
    check_virtual_env \
    build_collection \
    publish_collection \
    list_integration_tests \
    integration_test \
    integration_test_all \
    $(addprefix integration_test_,$(INTEGRATION_ENTRIES))

# --------------------------------------------------------------------------------------------------
# Target: install_virtual_env
# --------------------------------------------------------------------------------------------------
# Purpose
#   Rebuilds the Python virtual environment from scratch and installs all pip
#   packages the harness needs (ansible-playbook and PyYAML).
#
# Behavior
#   - Exports PYTHON_VERSION and delegates to the bootstrap script.
#
# Idempotency
#   - Destructive by design: the existing virtual environment is removed and
#     rebuilt on every invocation.
#
# Dependencies
#   - None (this is the bootstrap entry point).
install_virtual_env:
	@export PYTHON_VERSION=${PYTHON_VERSION_12} && bash 00_install_pipeline_dependencies.sh

# --------------------------------------------------------------------------------------------------
# Target: check_virtual_env
# --------------------------------------------------------------------------------------------------
# Purpose
#   Guard target: ensures the virtual environment exists before any
#   operational target runs, provisioning it on demand.
#
# Behavior
#   - Checks for the virtual environment directory.
#   - Triggers install_virtual_env only when the directory is missing.
#
# Dependencies
#   - install_virtual_env (invoked only when the venv is missing).
check_virtual_env:
	@if [ ! -d "${CONF_DIR_CONTEXT}/${VIRTUAL_ENV_DIR}" ]; then \
		echo "Virtual environment directory ${CONF_DIR_CONTEXT}/${VIRTUAL_ENV_DIR} not found."; \
		echo "Creating virtual environment..."; \
		$(MAKE) install_virtual_env; \
	fi

# --------------------------------------------------------------------------------------------------
# Target: build_collection
# --------------------------------------------------------------------------------------------------
# Purpose
#   Packages the repository into an installable Ansible collection artifact,
#   dist/<namespace>-<name>-<version>.tar.gz.
#
# Behavior
#   - Activates the virtual environment, then runs ansible-galaxy collection
#     build into COLLECTION_BUILD_DIR.
#   - Everything the artifact must not ship (the test suite, the virtual
#     environment, this Makefile, the bootstrap script, editor and coverage
#     droppings and any previous artifact) is excluded through the
#     galaxy.yml build_ignore list, not through flags here.
#   - --force overwrites an artifact of the same version, so rebuilding after
#     an edit does not require bumping galaxy.yml.
#   - Prints the resulting artifact path.
#
# Idempotency
#   - Safe to re-run: the output directory is created on demand and the
#     artifact is rewritten in place.
#
# Dependencies
#   - check_virtual_env
build_collection: check_virtual_env
	@mkdir -p "${COLLECTION_BUILD_DIR}"
	@source "${CONF_DIR_CONTEXT}/${VIRTUAL_ENV_DIR}/bin/activate" && \
		ansible-galaxy collection build "${CONF_DIR_CONTEXT}" \
			--output-path "${COLLECTION_BUILD_DIR}" \
			--force
	@ls -1 "${COLLECTION_BUILD_DIR}"/*.tar.gz

# --------------------------------------------------------------------------------------------------
# Target: publish_collection
# --------------------------------------------------------------------------------------------------
# Purpose
#   Publishes the built artifact for the version declared in galaxy.yml to
#   Ansible Galaxy (or to the Automation Hub named by GALAXY_SERVER).
#
# Behavior
#   - Rebuilds the artifact first, so what is uploaded always matches the
#     working tree and the galaxy.yml build_ignore list.
#   - Authenticates with GALAXY_TOKEN when set, otherwise leaves
#     ansible-galaxy to use ~/.ansible/galaxy_token.
#   - Announces the collection, version and target server before uploading.
#   - Waits for Galaxy to finish the import, so a rejected import fails the
#     target instead of passing silently.
#
# Idempotency
#   - NOT idempotent: Galaxy refuses a version that already exists. Bump
#     `version` in galaxy.yml before publishing again.
#
# Dependencies
#   - build_collection (and through it check_virtual_env)
#   - A Galaxy API token with rights on the ${COLLECTION_NAMESPACE} namespace
# --------------------------------------------------------------------------------------------------
# ⚠️ CAUTION: This target is public and irreversible. A published version
# cannot be replaced or removed without Galaxy administrator intervention.
# Do NOT execute it unless the release has been approved.
# --------------------------------------------------------------------------------------------------
publish_collection: build_collection
	@echo "Publishing ${COLLECTION_NAMESPACE}.${COLLECTION_NAME} ${COLLECTION_VERSION} to ${if ${GALAXY_SERVER},${GALAXY_SERVER},galaxy.ansible.com}"
	@source "${CONF_DIR_CONTEXT}/${VIRTUAL_ENV_DIR}/bin/activate" && \
		ansible-galaxy collection publish "${COLLECTION_ARTIFACT}" \
			$${GALAXY_TOKEN:+--token "$${GALAXY_TOKEN}"} \
			${if ${GALAXY_SERVER},--server "${GALAXY_SERVER}",} \
			--timeout 120

# --------------------------------------------------------------------------------------------------
# Target: list_integration_tests
# --------------------------------------------------------------------------------------------------
# Purpose
#   Prints the integration matrix entries, one per line, together with the
#   target name that runs each of them.
#
# Behavior
#   - Reads the entry names scraped from platforms.yml at parse time.
#
# Idempotency
#   - Read-only.
#
# Dependencies
#   - None (no virtual environment needed to read the matrix).
list_integration_tests:
	@echo "Integration matrix (${INTEGRATION_MATRIX}):"
	@$(foreach entry,$(INTEGRATION_ENTRIES),printf '  %-24s make integration_test_%s\n' "$(entry)" "$(entry)";)

# --------------------------------------------------------------------------------------------------
# Target: integration_test
# --------------------------------------------------------------------------------------------------
# Purpose
#   Runs one integration matrix entry through the full harness cycle:
#   up -> baseline audit -> harden -> reboot -> verify -> destroy.
#
# Behavior
#   - Requires ENTRY to name a platforms.yml entry.
#   - Activates the virtual environment, then invokes run.sh with ENTRY and
#     KEEP.
#
# Usage
#   make integration_test ENTRY=rocky8_l1
#   make integration_test ENTRY=rocky8_l1 KEEP=keep
#
# Idempotency
#   - This target is a thin orchestrator. Each run boots a disposable VM and
#     destroys it afterwards unless KEEP=keep.
#
# Dependencies
#   - check_virtual_env
#   - VirtualBox and Vagrant on the host (see tests/integration/README.md).
integration_test: check_virtual_env
	@if [ -z "${ENTRY}" ]; then \
		echo "ENTRY is required, e.g. make integration_test ENTRY=rocky8_l1"; \
		$(MAKE) --no-print-directory list_integration_tests; \
		exit 2; \
	fi
	@source "${CONF_DIR_CONTEXT}/${VIRTUAL_ENV_DIR}/bin/activate" && \
		cd "${INTEGRATION_DIR}" && ${INTEGRATION_RUNNER} "${ENTRY}" "${KEEP}"

# --------------------------------------------------------------------------------------------------
# Target: integration_test_all
# --------------------------------------------------------------------------------------------------
# Purpose
#   Runs every entry in the integration matrix and prints an aggregated
#   pass/fail summary.
#
# Behavior
#   - Activates the virtual environment, then invokes run.sh with the `all`
#     pseudo entry, which loops the matrix itself.
#   - Exits non-zero when any entry fails.
#
# Usage
#   make integration_test_all
#   make integration_test_all KEEP=keep
#
# Idempotency
#   - This target is a thin orchestrator. One disposable VM is booted per
#     entry and destroyed afterwards unless KEEP=keep.
#
# Dependencies
#   - check_virtual_env
#   - VirtualBox and Vagrant on the host (see tests/integration/README.md).
# --------------------------------------------------------------------------------------------------
# ⚠️ CAUTION: A full matrix run boots every platform in sequence and takes
# hours. Prefer a single-entry target while iterating.
# --------------------------------------------------------------------------------------------------
integration_test_all: check_virtual_env
	@source "${CONF_DIR_CONTEXT}/${VIRTUAL_ENV_DIR}/bin/activate" && \
		cd "${INTEGRATION_DIR}" && ${INTEGRATION_RUNNER} all "${KEEP}"

# --------------------------------------------------------------------------------------------------
# Generated targets: integration_test_<entry>
# --------------------------------------------------------------------------------------------------
# Purpose
#   One convenience target per platforms.yml entry, so every matrix row is
#   reachable by name without passing ENTRY.
#
# Behavior
#   - Generated from INTEGRATION_ENTRIES at parse time, so a new matrix row is
#     a new target with no change to this Makefile.
#   - Each target activates the virtual environment and delegates to run.sh
#     with its own entry name and KEEP.
#
# Usage
#   make integration_test_rocky8_l1
#   make integration_test_nginx_alma10_l2 KEEP=keep
#   make list_integration_tests            # show every generated target
#
# Idempotency
#   - Same as integration_test: a disposable VM per run, destroyed unless
#     KEEP=keep.
#
# Dependencies
#   - check_virtual_env
#   - VirtualBox and Vagrant on the host (see tests/integration/README.md).
define INTEGRATION_TEST_TARGET
integration_test_$(1): check_virtual_env
	@source "$${CONF_DIR_CONTEXT}/$${VIRTUAL_ENV_DIR}/bin/activate" && \
		cd "$${INTEGRATION_DIR}" && $${INTEGRATION_RUNNER} "$(1)" "$${KEEP}"
endef

$(foreach entry,$(INTEGRATION_ENTRIES),$(eval $(call INTEGRATION_TEST_TARGET,$(entry))))
