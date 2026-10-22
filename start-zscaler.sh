#!/usr/bin/env bash
# Purpose: Restore Zscaler launch agents and daemons and open its application.
# Usage:   ./start-zscaler.sh
#
# Requires a logged-in console user. Prompts for administrator privileges.
# Already loaded services are retained. Errors exit nonzero.

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=zscaler.bash
source "$script_dir/zscaler.bash"
zscaler_main start "$@"
