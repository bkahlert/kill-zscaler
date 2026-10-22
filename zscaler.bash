#!/usr/bin/env bash
# Shared launchd lifecycle handling for the shell and application entry points.

zscaler_loaded() {
  local output status
  if output=$(launchctl print "$1" 2>&1); then
    return 0
  else
    status=$?
  fi
  # launchctl returns 113 for a service missing from an existing domain.
  if [[ $status == 113 ]]; then
    return 1
  fi
  printf '%s\n' "$output" >&2
  return 2
}

zscaler_apply() {
  local action=$1 domain=$2 directory=$3 plist label status
  find "$directory" -maxdepth 1 -iname '*zscaler*.plist' \
    \( -type f -o -type l \) -print0 |
    while IFS= read -r -d '' plist; do
      label=$(plutil -extract Label raw -expect string -o - "$plist") || return
      case $label in
        ''|*/*)
          printf 'Invalid launchd Label in %s\n' "$plist" >&2
          return 1
          ;;
      esac
      if zscaler_loaded "$domain/$label"; then
        status=0
      else
        status=$?
      fi
      case "$status:$action" in
        0:stop)
          launchctl bootout "$domain/$label" || return
          printf 'Stopped %s/%s\n' "$domain" "$label"
          ;;
        1:start)
          launchctl bootstrap "$domain" "$plist" || return
          printf 'Started %s/%s\n' "$domain" "$label"
          ;;
        0:start|1:stop)
          printf 'Already in requested state: %s/%s\n' "$domain" "$label"
          ;;
        *) return "$status" ;;
      esac
    done
}

zscaler_main() {
  local action=$1 console_uid script_dir current_uid
  shift
  case ${1-} in
    -h|--help)
      awk 'NR==1 {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$0"
      return 0
      ;;
    '')
      if (( $# )); then
        printf 'Unexpected empty argument. See %s --help\n' "$0" >&2
        return 2
      fi
      ;;
    *)
      printf 'Unexpected argument: %s. See %s --help\n' "$1" "$0" >&2
      return 2
      ;;
  esac
  current_uid=$(id -u) || return
  if [[ $current_uid != 0 ]]; then
    script_dir=$(cd -- "$(dirname -- "$0")" && pwd) || return
    exec sudo /bin/bash "$script_dir/${0##*/}" "$@"
  fi
  console_uid=$(stat -f %u /dev/console) || return
  case $console_uid in
    ''|0|*[!0-9]*)
      printf 'A logged-in console user is required.\n' >&2
      return 1
      ;;
  esac
  launchctl print "gui/$console_uid" > /dev/null || return
  launchctl print system > /dev/null || return

  # Stop watchdog daemons before agents; restore daemons before their clients.
  zscaler_apply "$action" system /Library/LaunchDaemons || return
  zscaler_apply "$action" "gui/$console_uid" /Library/LaunchAgents || return
  if [[ $action == start ]]; then
    launchctl asuser "$console_uid" sudo -u "#$console_uid" \
      open -a /Applications/Zscaler/Zscaler.app --hide
  fi
}
