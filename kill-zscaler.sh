#!/usr/bin/env bash
# Purpose: Stop Zscaler launch agents and daemons for the current login session.
# Usage:   ./kill-zscaler.sh
#
# Requires a logged-in console user. Prompts for administrator privileges.
# Does not uninstall or persistently disable services. Errors exit nonzero.

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=zscaler.bash
source "$script_dir/zscaler.bash"
zscaler_main stop "$@"
