#!/usr/bin/env bash
# Purpose: Start Zscaler with a graphical administrator authorization prompt.
# Usage:   open "Start Zscaler.app"

set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
exec osascript - "$repo_dir/start-zscaler.sh" <<'APPLESCRIPT'
on run arguments
    do shell script "/bin/bash " & quoted form of (item 1 of arguments) with administrator privileges
end run
APPLESCRIPT
