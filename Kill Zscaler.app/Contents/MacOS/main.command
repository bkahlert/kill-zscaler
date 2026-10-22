#!/usr/bin/env bash
# Purpose: Stop Zscaler with a graphical administrator authorization prompt.
# Usage:   open "Kill Zscaler.app"

set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
exec osascript - "$repo_dir/kill-zscaler.sh" <<'APPLESCRIPT'
on run arguments
    do shell script "/bin/bash " & quoted form of (item 1 of arguments) with administrator privileges
end run
APPLESCRIPT
