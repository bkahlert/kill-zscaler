#!/bin/bash
#
# A script to share a Zscaler tunnel.
#
# Usage:
# SHARE_ZSCALER_HOSTS='
#     foo.bar.internal
#     example.com
# ' ./share-zscaler.sh
#
# The script sets up network address translation (NAT) so that
# all requests coming from the network of interface en0 have access
# to the network the first resolved host routes to
# (e.g. 10.100.0.0/16 using the tunnel interface utun3).
#
# The script also outputs necessary steps on how to configure
# your local host to actually pass requests to your tunnel endpoint
# for the hosts foo.bar.internal and example.com.
#
# The above example corresponds to the full call:
# SHARE_ZSCALER_TUNNEL_INTERFACE=utun3 \
# SHARE_ZSCALER_EXTERNAL_ADDRESS=10.100.0.0/16 \
# SHARE_ZSCALER_SOURCE_ADDRESS=192.168.64.0/24 \
# SHARE_ZSCALER_HOSTS='
#     foo.bar.internal
#     example.com
# ' ./share-zscaler.sh
#
# Without a local copy this script can also be called using curl:
# SHARE_ZSCALER_HOSTS='
#     foo.bar.internal
#     example.com
# ' bash -c "$(curl -so- https://raw.githubusercontent.com/bkahlert/kill-zscaler/main/share-zscaler.sh)"
#
# bashsupport disable=BP5001

# The IP of the (virtual) host with Zscaler installed (default: IP of en0 interface)
declare -r TUNNEL_ADDRESS=${SHARE_ZSCALER_TUNNEL_ADDRESS:-$(ipconfig getifaddr en0)}

# The network/IP you want to share (default: IP of en0 interface)
declare -r SOURCE_ADDRESS=${SHARE_ZSCALER_SOURCE_ADDRESS:-$(ipconfig getifaddr en0)/24}

# The hosts you want to be able to connect to.
declare -r hosts=${SHARE_ZSCALER_HOSTS?SHARE_ZSCALER_HOSTS is not set}

# The network/IP to tunnel traffic to (e.g. "10.100.0.0/16", default: responsible destination for first resolved host)
declare EXTERNAL_ADDRESS=${SHARE_ZSCALER_EXTERNAL_ADDRESS:-}

# The interface name to tunnel traffic to (e.g. "utun3", default: responsible interface for external address)
# Use `ifconfig` and look for the entry containing "inet 10.100.0.1 --> 10.100.0.1 netmask 0xffff0000"
declare TUNNEL_INTERFACE=${SHARE_ZSCALER_TUNNEL_INTERFACE:-}

# Executes the passed command line while prefixing the output with #
comment_run() {
   "$@" | sed 's/^/# /'
}

# Prints error and exits with 1
die() {
  {
  tput setaf 1
  printf '%s' "$*"
  tput sgr0
  printf '\n'
  } >&2
  exit 1
}

# Resolves the given hostname
print_resolved_host() {
  host "${1?host missing}" | awk '/has address/ { print $4 ; exit }'
}

# Resolves the new-line separated list of hostnames to their IP address.
print_resolved_hosts() {
  declare resolved host
  for host in ${1?host(s) missing}; do
    resolved=$(print_resolved_host "$host")
    if [[ $resolved != "" ]]; then
      printf "%s %s\n" "$resolved" "$host"
      continue
    fi
  done
}

# Resolves the new-line separated list of hostnames until the first could be resolved and returns its IP.
print_first_resolved_host() {
  declare resolved host
  for host in ${1?host(s) missing}; do
    resolved=$(print_resolved_host "$host")
    if [[ $resolved != "" ]]; then
      printf "%s\n" "$resolved"
      return 0
    fi
  done
  return 1
}

# Prints the commands that update /etc/hosts to match the specified
# resolved hosts.
print_hosts_update_cmd() {
  declare -a entry
  declare ip host
  echo "${1?hosts missing}" | while IFS=$' ' read -r -a entry; do
    ip=${entry[0]?ip missing}
    host=${entry[1]?host missing}
    # shellcheck disable=SC2016
    printf 'sudo sed -Ei "" "/.*[[:space:]]+%s/{
h
s/.*/%s %s/
}
\${
x
/^$/{
s//%s %s/
H
}
x
}" /etc/hosts
' "${host//./\.}" "$ip" "$host" "$ip" "$host"
  done
}

# Sets up network address translation.
main() {
  declare resolved_hosts route_cmd hosts_backup_cmd hosts_update_cmd flushdns_cmd

  declare first_resolved_host route_info
  first_resolved_host=$(print_first_resolved_host "$hosts") || {
    die "Failed to resolve any of the given hosts: $hosts"
  }
  route_info=$(route get "$first_resolved_host") || {
    die "Failed to get route information for $first_resolved_host"
  }
  EXTERNAL_ADDRESS=${EXTERNAL_ADDRESS:-$(echo "$route_info" | grep 'destination:' | sed -E 's,.*:[[:space:]]*,,')}
  TUNNEL_INTERFACE=${TUNNEL_INTERFACE:-$(echo "$route_info" | grep 'interface:' | sed -E 's,.*:[[:space:]]*,,')}

  # enables kernel to route packages
  comment_run sudo sysctl -w net.inet.ip.forwarding=1 || {
    die "Failed to enable routing packages"
  }

  # disable network address translation
  comment_run sudo pfctl -d || true

  # flush all rules
  comment_run sudo pfctl -F all || {
    die "Failed to flush all rules"
  }

  # enable network address translation
  declare nat_file && nat_file=$(mktemp)
  echo "nat on $TUNNEL_INTERFACE from $SOURCE_ADDRESS to any -> ($TUNNEL_INTERFACE)" > "$nat_file"
  comment_run sudo pfctl -f "$nat_file" -e || {
    die " 💡 Hint: type \`sudo pfctl -s nat\` to see applied NAT rules"
  }
  comment_run rm "$nat_file"

  resolved_hosts=$(print_resolved_hosts "$hosts")
  route_cmd=$(printf "sudo bash -c 'route delete -net %s; route add -net %s -host %s'" "$EXTERNAL_ADDRESS" "$EXTERNAL_ADDRESS" "$TUNNEL_ADDRESS")
  hosts_backup_cmd='sudo cp /etc/hosts /etc/hosts.backup'
  hosts_update_cmd=$(print_hosts_update_cmd "$resolved_hosts")
  flushdns_cmd='dscacheutil -flushcache'

  comment_run printf "\n"
  comment_run printf "To route your traffic, run the following script, by piping it to bash:\n"
  comment_run printf "\n"
  printf "%s\n%s\n%s\n%s\n" "$route_cmd" "$hosts_backup_cmd" "$hosts_update_cmd" "$flushdns_cmd"
}

main "$@"
