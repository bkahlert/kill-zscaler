#!/bin/bash
#
# A script to help sharing a Zscaler tunnel.
#
# Usage:
# SHARE_ZSCALER_EXTERNAL_ADDRESS=10.100.0.0/16 \
# SHARE_ZSCALER_HOSTS='
#     example.com
#     foo.bar.internal
# ' sudo -E ./share-zscaler.sh
#
# This call will set up network address translation (NAT) so that
# all requests coming from network 192.168.64.0/24 will have access
# to network 10.100.0.0/16 using the tunnel interface utun3.
#
# The script will also output necessary steps on how to configure
# your local host to actually pass requests to your tunnel endpoint
# for the hosts example.com and foo.bar.internal.
#
# The above example corresponds to the full call:
# SHARE_ZSCALER_TUNNEL_INTERFACE=utun3 \
# SHARE_ZSCALER_EXTERNAL_ADDRESS=10.100.0.0/16 \
# SHARE_ZSCALER_SOURCE_ADDRESS=192.168.64.0/24 \
# SHARE_ZSCALER_HOSTS='
#     example.com
#     foo.bar.internal
# ' sudo -E ./share-zscaler.sh
#
# tunnel interface utun3,
# bashsupport disable=BP5001

# Name of the interface used by Zscaler to tunnel the traffic
# Use `ifconfig` and look the the entry containing "inet 100.64.0.1 --> 100.64.0.1 netmask 0xffff0000"
declare -r TUNNEL_INTERFACE=${SHARE_ZSCALER_TUNNEL_INTERFACE:-utun3}

# The IP of the host with Zscaler installed (typically the VM guest)
# Leave empty to attempt to find out automatically
declare -r TUNNEL_ADDRESS=${SHARE_ZSCALER_TUNNEL_ADDRESS:-}

# The network you want to share (typically the one shared by your VM host and guest)
declare -r SOURCE_ADDRESS=${SHARE_ZSCALER_SOURCE_ADDRESS:-192.168.64.0/24}

declare -r EXTERNAL_ADDRESS=${SHARE_ZSCALER_EXTERNAL_ADDRESS?EXTERNAL_ADDRESS missing; example: \`SHARE_ZSCALER_EXTERNAL_ADDRESS=10.100.0.0/16\`}

# The hosts you want to be able to connect to.
declare -r hosts=${SHARE_ZSCALER_HOSTS:-}

# Resolves the new-line separated list of hostnames to their IP address.
resolve() {
  declare resolved host
    for host in ${1?host(s) missing} ; do
        resolved=$(nslookup "$host" | grep "Non-authoritative answer" -A5 | grep -oE "[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}")
        if [[ $resolved != "" ]]; then
            printf "%s\t%s\n" "$resolved" "$host"
            continue
        fi
    done
}

# Sets up network address translation.
main() {
  # enables kernel to route packages
  sysctl -w net.inet.ip.forwarding=1 || exit

  pfctl -d

  # flush all rules
  pfctl -F all || exit

  # enable network address translation
  echo "nat on $TUNNEL_INTERFACE from $SOURCE_ADDRESS to any -> ($TUNNEL_INTERFACE)" | pfctl -f - -e || {
    echo " 💡 Hint: type \`sudo pfctl -s nat\` to see applied NAT rules"
    exit
  }

  printf "\n"
  printf "In order to route your traffic properly\n"
  printf "\n"
  printf "1. Add a route to this host:\n"
  printf "\n"
  printf "   sudo bash -c 'route delete -net %s; route add %s %s'\n" "$EXTERNAL_ADDRESS" "$EXTERNAL_ADDRESS"  "${TUNNEL_ADDRESS:-"$(ipconfig getifaddr en0)"}"
  printf "\n"
  printf "2. Update /etc/hosts:\n"
  printf "\n"
  # shellcheck disable=SC2016
  printf '   "${VISUAL:-${EDITOR:-nano}}" /etc/hosts\n'
  printf "\n"
  printf '   Make sure it contains the following entries:\n'
  printf "\n"
  printf "# Added by shared Zscaler\n"
  printf "%s\n" "$(resolve "$hosts")"
  printf "# End of section\n"
  printf "\n"
}

main "$@"
