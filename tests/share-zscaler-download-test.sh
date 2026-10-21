#!/usr/bin/env bash
# Purpose: Check the generated host configuration uses a pinned logr release.
# Usage:   tests/share-zscaler-download-test.sh

set -euo pipefail

ipconfig() { printf '192.0.2.10\n'; }
host() { printf '%s has address 203.0.113.10\n' "$2"; }
route() {
  printf '%s\n' \
    'destination: 10.0.0.0' \
    'gateway: 192.0.2.1' \
    'interface: utun3'
}
sudo() { return 0; }
mktemp() { printf '/dev/null\n'; }
rm() { return 0; }

export -f ipconfig host route sudo mktemp rm

test_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$test_dir/.." && pwd)
output=$(
  SHARE_ZSCALER_VPN_CLIENT_ADDRESS=192.0.2.10 \
    SHARE_ZSCALER_SOURCE_ADDRESS=192.0.2.0/24 \
    bash -c 'source "$1" --probe foo.bar.internal --domain internal' \
    _ "$repo_root/share-zscaler.v2.sh"
)
expected_url='https://github.com/bkahlert/logr/releases/download/v0.6.4/logr.sh'

if ! grep -Fq "$expected_url" <<<"$output"; then
  printf 'Expected generated configuration to use %s\n' "$expected_url" >&2
  exit 1
fi

if grep -Fq 'https://git.io/logr.sh' <<<"$output"; then
  printf 'Generated configuration still uses floating git.io URL\n' >&2
  exit 1
fi
