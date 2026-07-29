#!/usr/bin/env bash

# --------------------------------------------------------------------------------------------------
# Script Name   : 00_install_pipeline_dependencies.sh
# Description   : This script automates the creation and configuration
#                of a Python virtual environment for the integration test
#                harness. It:
#                   - Cleans up any existing virtual environment.
#                   - Creates a new virtual environment.
#                   - Installs required Python dependencies (ansible-core and
#                     PyYAML, which tests/integration/run.sh drives).
#                   - Handles retries in case of transient installation failures.
#
# Usage         : ./00_install_pipeline_dependencies.sh
#
# Environment Variables:
#   RETRY_COUNT     → Number of retry attempts for dependency installation (default: 5).
#   RETRY_DELAY     → Delay in seconds between retry attempts (default: 10).
#   PYTHON_VERSION  → Python version to use for the virtual environment (default: python3.12).
# --------------------------------------------------------------------------------------------------

RETRY_COUNT="${RETRY_COUNT:-5}"
RETRY_DELAY="${RETRY_DELAY:-10}"
PYTHON_VERSION="${PYTHON_VERSION:-python3.12}"
export CONF_DIR_CONTEXT="."
export VIRTUAL_ENV_DIR="ops.venv"

# --------------------------------------------------------------------------------------------------
# install_dependencies
# Rebuilds the virtual environment from scratch and installs pip requirements. Returns 0 on
# success, 1 on the first failed step. Tooling upgrades happen inside the virtual environment
# only, so the system Python is never modified.
# --------------------------------------------------------------------------------------------------
install_dependencies() {
    # Recreate the virtual environment from scratch
    rm -rf "${CONF_DIR_CONTEXT:?}/${VIRTUAL_ENV_DIR:?}" || return 1
    "${PYTHON_VERSION}" -m venv "${CONF_DIR_CONTEXT}/${VIRTUAL_ENV_DIR}" || return 1

    # Activate virtual environment
    pushd "${CONF_DIR_CONTEXT}" >/dev/null || return 1
    source "${VIRTUAL_ENV_DIR}/bin/activate" || { popd >/dev/null 2>&1 || true; return 1; }

    # Upgrade packaging tooling inside the virtual environment
    pip3 install --upgrade pip setuptools wheel || { popd >/dev/null 2>&1 || true; return 1; }

    # Install required Python dependencies
    pip3 install -r requirements.txt || { popd >/dev/null 2>&1 || true; return 1; }

    popd >/dev/null 2>&1 || true

    # Success
    return 0
}

success=false

# --------------------------------------------------------------------------------------------------
# Retry Loop
# Iterates up to RETRY_COUNT attempts. Each attempt rebuilds the virtual environment and
# installs all dependencies. On success the loop breaks immediately. On failure it logs a
# timestamped message and sleeps RETRY_DELAY seconds before retrying.
# --------------------------------------------------------------------------------------------------
for i in $(seq 1 $RETRY_COUNT); do
    install_dependencies && {
        success=true
        break
    } || {
        printf "\n\n[%s] Attempt %d/%d failed to install pipeline dependencies. Retrying in %s seconds...\n\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$i" "$RETRY_COUNT" "$RETRY_DELAY"
        sleep "$RETRY_DELAY"
    }
done

# --------------------------------------------------------------------------------------------------
# Exit Status
# Exits with 0 on successful execution, 255 after all retries are exhausted.
# --------------------------------------------------------------------------------------------------
if [ "$success" = false ]; then
    exit 255
fi
