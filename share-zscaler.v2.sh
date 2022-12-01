#!/bin/bash
#
# A script to share a Zscaler VPN tunnel.
#
# Usage:
# ./share-zscaler.v2.sh --probe foo.bar.internal --domain internal
#
# The script sets up network address translation (NAT) so that
# all requests coming from the network of interface en0 have access
# to the network the probe host routes to
# (e.g. 10.100.0.0/16 using the tunnel interface utun3).
#
# The script also outputs a script that
# can be executed locally to configure the host
# to make use of the tunnel for the specified domains.
#
# Without a local copy, this script can also be called using curl:
# bash -c "$(curl -so- https://raw.githubusercontent.com/bkahlert/kill-zscaler/main/share-zscaler.v2.sh)" -- --probe foo.bar.internal --domain internal
#
# bashsupport disable=BP5001

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

# The IP of the (virtual) host with Zscaler installed (default: IP of en0 interface)
declare -r VPN_CLIENT_ADDRESS=${SHARE_ZSCALER_VPN_CLIENT_ADDRESS:-$(ipconfig getifaddr en0)}

# The network/IP you want to share (default: IP of en0 interface)
declare -r SOURCE_ADDRESS=${SHARE_ZSCALER_SOURCE_ADDRESS:-$(ipconfig getifaddr en0)/24}

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

# Sets up NAT on this VPN client and
# prints the script to configure the host
# to use the VPN tunnel.
# Globals:
#   SOURCE_ADDRESS
#   VPN_CLIENT_ADDRESS
# Arguments:
#   --probe - name of the host to resolve to find the VPN tunnel details
#   --domain[@] - domain(s) to include in the host DNS resolve configuration script
#   --debug - if specified, outputs diagnostic commands to the host configuration script
main() {
  local debug probe
  local -a domains=() args=()
  while (($#)); do
    case $1 in
      --debug)
        debug=1 && shift
        ;;
      --probe)
        [ "${2-}" ] || die "$1 value missing"
        probe=$2 && shift 2
        ;;
      --domain)
        [ "${2-}" ] || die "$1 value missing"
        domains+=("$2") && shift 2
        ;;
      *)
        args+=("$1") && shift
        ;;
    esac
  done
  set -- "${args[@]}"

  [ "$probe" ] || die "--probe value missing"

  declare probe_ip route_info vpn_address vpn_interface vpn_gateway
  probe_ip=$(print_resolved_host "$probe") || {
    die "Failed to resolve probe: $probe"
  }
  route_info=$(route get "$probe_ip") || {
    die "Failed to get route information for $probe_ip"
  }
  vpn_address=$(echo "$route_info" | grep 'destination:' | sed -E 's,.*:[[:space:]]*,,')
  vpn_interface=$(echo "$route_info" | grep 'interface:' | sed -E 's,.*:[[:space:]]*,,')
  vpn_gateway=$(echo "$route_info" | grep 'gateway:' | sed -E 's,.*:[[:space:]]*,,')

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
  echo "nat on $vpn_interface from $SOURCE_ADDRESS to any -> ($vpn_interface)" >"$nat_file"
  comment_run sudo pfctl -f "$nat_file" -e || {
    die ' 💡 Hint: type `sudo pfctl -s nat` to see applied NAT rules'
  }
  comment_run rm "$nat_file"

  declare route_cmd
  route_cmd=$(printf "sudo bash -c 'route delete -net %s; route add -net %s -host %s'" "$vpn_address" "$vpn_address" "$VPN_CLIENT_ADDRESS")

  declare -a dns_cmds=()
  for domain in "${domains[@]}"; do
    dns_cmds+=("sudo bash -c 'echo \"domain $domain
search $domain
nameserver $vpn_gateway
\" > /etc/resolver/$domain'")
  done
  dns_cmds+=('sudo killall -HUP mDNSResponder')
  dns_cmds+=('dscacheutil -flushcache')

  declare unshare_sh='$HOME/unshare-zscaler.v2.sh'
  dns_cmds=('if [ -x "'"$unshare_sh"'" ]; then "'"$unshare_sh"'"; fi' "${dns_cmds[@]}")
  dns_cmds+=('echo "cd /etc/resolver && sudo rm '"${domains[*]}"'" > "'"$unshare_sh"'" && chmod +x "'"$unshare_sh"'"')

  if [ "${debug-}" ]; then
    dns_cmds+=("scutil --dns")
    dns_cmds+=("dns-sd -G v4v6 $probe")
  fi

  comment_run printf "———\n"
  comment_run printf "Successfully set up this VPN client.\n"
  comment_run printf "To use the VPN tunnel on your host:\n"
  comment_run printf "— either run the following script on it, or\n"
  comment_run printf "— pipe this output to its Bash.\n"
  comment_run printf "———\n"
  printf "%s\n" "$route_cmd"
  printf "%s\n" "${dns_cmds[@]}"
}

main "$@"
