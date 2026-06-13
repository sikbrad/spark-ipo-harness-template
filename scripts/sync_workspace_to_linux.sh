#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/sync_workspace_to_linux.sh [options]

Sync every folder listed in dof-work-startpoint.code-workspace with the same
absolute path on a Linux machine via rsync.

Options:
  --direction MODE     push, pull, or both. Default: push.
                       push: Mac -> remote
                       pull: remote -> Mac
                       both: pull then push
  --dry-run            Show what would be transferred.
  --delete             Delete remote files that no longer exist locally.
                       In pull mode this deletes local files missing remotely.
                       Not allowed with --direction both.
  --remote HOST        SSH host alias or hostname. Default: NotHome-WS-1203-new
  --workspace PATH     VS Code .code-workspace file.
                       Default: dof-work-startpoint.code-workspace
  --only NAME          Sync only the workspace folder with this name.
  --list               List resolved workspace folders and exit.
  -h, --help           Show this help.

Environment overrides:
  REMOTE_HOST          Same as --remote.
  WORKSPACE_FILE       Same as --workspace.
  RSYNC_RETRIES        Per-folder retry count. Default: 3.
  RSYNC_RETRY_DELAY    Seconds to wait between retries. Default: 10.
  RSYNC_EXTRA_OPTS     Extra rsync options appended at the end.
USAGE
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"

remote_host="${REMOTE_HOST:-NotHome-WS-1203-new}"
workspace_file="${WORKSPACE_FILE:-${project_dir}/dof-work-startpoint.code-workspace}"
direction="${SYNC_DIRECTION:-push}"
dry_run=0
delete_remote=0
list_only=0
only_name=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --direction)
      direction="${2:?--direction requires push, pull, or both}"
      shift 2
      ;;
    --direction=*)
      direction="${1#*=}"
      shift
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --delete)
      delete_remote=1
      shift
      ;;
    --remote)
      remote_host="${2:?--remote requires a value}"
      shift 2
      ;;
    --remote=*)
      remote_host="${1#*=}"
      shift
      ;;
    --workspace)
      workspace_file="${2:?--workspace requires a value}"
      shift 2
      ;;
    --workspace=*)
      workspace_file="${1#*=}"
      shift
      ;;
    --only)
      only_name="${2:?--only requires a workspace folder name}"
      shift 2
      ;;
    --only=*)
      only_name="${1#*=}"
      shift
      ;;
    --list)
      list_only=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$direction" in
  push|pull|both)
    ;;
  *)
    echo "Invalid --direction: ${direction}. Use push, pull, or both." >&2
    exit 2
    ;;
esac

if [[ "$direction" == "both" && "$delete_remote" -eq 1 ]]; then
  echo "--delete is not allowed with --direction both; deletion is ambiguous in two-way sync." >&2
  exit 2
fi

if [[ ! -f "$workspace_file" ]]; then
  echo "Workspace file not found: $workspace_file" >&2
  exit 1
fi

workspace_entries="$(
  python3 - "$workspace_file" <<'PY'
import json
import pathlib
import sys

workspace_path = pathlib.Path(sys.argv[1]).expanduser().resolve()
text = workspace_path.read_text(encoding="utf-8")

def strip_jsonc(src):
    out = []
    i = 0
    in_string = False
    escaped = False
    while i < len(src):
        ch = src[i]
        nxt = src[i + 1] if i + 1 < len(src) else ""
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            while i < len(src) and src[i] not in "\r\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)

data = json.loads(strip_jsonc(text))
base = workspace_path.parent
for folder in data.get("folders", []):
    name = folder.get("name") or pathlib.Path(folder["path"]).name
    local_path = (base / folder["path"]).resolve()
    print(f"{name}\t{local_path}")
PY
)"

if [[ -z "$workspace_entries" ]]; then
  echo "No workspace folders found in: $workspace_file" >&2
  exit 1
fi

missing=0
matched=0
while IFS=$'\t' read -r name local_dir; do
  [[ -n "$name" ]] || continue
  if [[ -n "$only_name" && "$name" != "$only_name" ]]; then
    continue
  fi
  matched=$((matched + 1))
  if [[ ! -d "$local_dir" ]]; then
    echo "Missing local workspace folder: ${name} -> ${local_dir}" >&2
    missing=1
  fi
done <<< "$workspace_entries"

if [[ "$matched" -eq 0 ]]; then
  echo "No workspace folder matched --only '${only_name}'." >&2
  exit 1
fi

if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

if [[ "$list_only" -eq 1 ]]; then
  while IFS=$'\t' read -r name local_dir; do
    [[ -n "$name" ]] || continue
    if [[ -n "$only_name" && "$name" != "$only_name" ]]; then
      continue
    fi
    printf '%s\t%s\t%s:%s/\n' "$name" "$local_dir" "$remote_host" "$local_dir"
  done <<< "$workspace_entries"
  exit 0
fi

rsync_opts=(
  -az
  -e
  "ssh -o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=4"
  --partial
  --partial-dir=.rsync-partial
  --timeout=60
  --stats
  --itemize-changes
  --exclude='/.git/'
  --exclude='.DS_Store'
  --exclude='.rsync-partial/'
  --exclude='.*.??????'
  --exclude='node_modules/'
  --exclude='node_modules'
  --exclude='dist/'
  --exclude='dist-ssr/'
  --exclude='build/'
  --exclude='coverage/'
  --exclude='.next/'
  --exclude='.nuxt/'
  --exclude='.turbo/'
  --exclude='.vite/'
  --exclude='.cache/'
  --exclude='.pytest_cache/'
  --exclude='.mypy_cache/'
  --exclude='.ruff_cache/'
  --exclude='.venv/'
  --exclude='venv/'
  --exclude='logs/'
  --exclude='/.omc/logs/'
  --exclude='/.omx/logs/'
  --exclude='/.playwright/'
  --exclude='/.playwright-cli/'
  --exclude='/.playwright-mcp/'
  --exclude='**/__pycache__/'
  --exclude='*.pyc'
  --exclude='*.pyo'
  --exclude='*.log'
  --exclude='npm-debug.log*'
  --exclude='yarn-debug.log*'
  --exclude='yarn-error.log*'
  --exclude='pnpm-debug.log*'
)

if [[ "$dry_run" -eq 1 ]]; then
  rsync_opts+=(--dry-run)
fi

if [[ "$delete_remote" -eq 1 ]]; then
  rsync_opts+=(--delete)
fi

if [[ -n "${RSYNC_EXTRA_OPTS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_opts=(${RSYNC_EXTRA_OPTS})
  rsync_opts+=("${extra_opts[@]}")
fi

echo "Workspace: ${workspace_file}"
echo "Remote host: ${remote_host}"
echo "Direction: ${direction}"
if [[ "$dry_run" -eq 1 ]]; then
  echo "Mode: dry-run"
else
  echo "Mode: apply"
fi
if [[ "$delete_remote" -eq 1 ]]; then
  echo "Remote delete: enabled"
else
  echo "Remote delete: disabled"
fi

synced=0
rsync_retries="${RSYNC_RETRIES:-3}"
rsync_retry_delay="${RSYNC_RETRY_DELAY:-10}"

run_rsync_with_retry() {
  local name="$1"
  local phase="$2"
  local source="$3"
  local target="$4"
  local attempt=1

  echo "Phase: ${phase}"
  echo "Source: ${source}"
  echo "Target: ${target}"

  while true; do
    if rsync "${rsync_opts[@]}" "$source" "$target" < /dev/null; then
      break
    fi
    if [[ "$attempt" -ge "$rsync_retries" ]]; then
      echo "Rsync ${phase} failed for ${name} after ${attempt} attempt(s)." >&2
      exit 1
    fi
    echo "Rsync ${phase} failed for ${name}; retrying in ${rsync_retry_delay}s (${attempt}/${rsync_retries})..." >&2
    sleep "$rsync_retry_delay"
    attempt=$((attempt + 1))
  done
}

while IFS=$'\t' read -r name local_dir; do
  [[ -n "$name" ]] || continue
  if [[ -n "$only_name" && "$name" != "$only_name" ]]; then
    continue
  fi

  remote_dir="$local_dir"
  mkdir_cmd=$(printf 'mkdir -p -- %q' "$remote_dir")
  remote_ref="${remote_host}:${remote_dir}/"
  local_ref="${local_dir}/"

  echo
  echo "==> ${name}"

  if [[ "$direction" == "push" || "$direction" == "both" ]]; then
    ssh -n -o BatchMode=yes "$remote_host" "$mkdir_cmd"
  fi

  case "$direction" in
    push)
      run_rsync_with_retry "$name" "push" "$local_ref" "$remote_ref"
      ;;
    pull)
      ssh -n -o BatchMode=yes "$remote_host" "test -d $(printf '%q' "$remote_dir")"
      run_rsync_with_retry "$name" "pull" "$remote_ref" "$local_ref"
      ;;
    both)
      if ssh -n -o BatchMode=yes "$remote_host" "test -d $(printf '%q' "$remote_dir")"; then
        run_rsync_with_retry "$name" "pull" "$remote_ref" "$local_ref"
      else
        echo "Remote folder missing; skipping pull for ${name} and creating it before push."
        ssh -n -o BatchMode=yes "$remote_host" "$mkdir_cmd"
      fi
      run_rsync_with_retry "$name" "push" "$local_ref" "$remote_ref"
      ;;
  esac

  synced=$((synced + 1))
done <<< "$workspace_entries"

echo
echo "Completed workspace folder count: ${synced}"
