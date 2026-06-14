#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: remote_probe.sh [--show|--check] [--ssh 'ssh ...'] [--timeout SECONDS]

Prints the parsed remote target and optionally performs a non-interactive SSH
connectivity check.
USAGE
}

ssh_line="ssh -p 62001 gq@odungnest.iptime.org"
mode="show"
timeout_seconds="8"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --show)
      mode="show"
      shift
      ;;
    --check)
      mode="check"
      shift
      ;;
    --ssh)
      ssh_line="${2:?--ssh requires an ssh command}"
      shift 2
      ;;
    --timeout)
      timeout_seconds="${2:?--timeout requires seconds}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

read -r -a ssh_tokens <<< "$ssh_line"
if [[ "${ssh_tokens[0]}" != "ssh" ]]; then
  echo "first parsed command is not ssh: $ssh_line" >&2
  exit 1
fi

ssh_args=("${ssh_tokens[@]:1}")
ssh_config="$(ssh -G "${ssh_args[@]}" 2>/dev/null || true)"
config_value() {
  local key="$1"
  awk -v key="$key" '$1 == key {print $2; exit}' <<< "$ssh_config"
}

host="$(config_value hostname)"
user="$(config_value user)"
port="$(config_value port)"

echo "command=$ssh_line"
echo "user=${user:-unknown}"
echo "host=${host:-unknown}"
echo "port=${port:-unknown}"

if [[ "$mode" == "show" ]]; then
  exit 0
fi

ssh -o BatchMode=yes -o ConnectTimeout="$timeout_seconds" "${ssh_args[@]}" \
  'printf "remote-ok host=%s user=%s cwd=%s\n" "$(hostname)" "$(whoami)" "$(pwd)"; uname -a'
