#!/usr/bin/env bash

set -euo pipefail

BIN_DIR="${HOME}/.local/bin"
BIN_PATH="${BIN_DIR}/vimdo"

CACHE_DIR="${XDG_CACHE_HOME:-${HOME}/.cache}/vimdo"
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/vimdo"

KEEP_DATA=false

usage() {
  cat <<EOF2
Usage: ./uninstall.sh [OPTION]

Uninstall Vimdo.

Options:
  --keep-data   Remove only the Vimdo executable.
                Keep cached repositories and saved challenges.

  -h, --help    Show this help message.
EOF2
}

for arg in "$@"; do
  case "$arg" in
    --keep-data)
      KEEP_DATA=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo
      usage
      exit 1
      ;;
  esac
done

if [[ -e "$BIN_PATH" ]]; then
  rm -f "$BIN_PATH"
  echo "Removed: $BIN_PATH"
else
  echo "Not installed: $BIN_PATH"
fi

if [[ "$KEEP_DATA" == false ]]; then
  if [[ -d "$CACHE_DIR" ]]; then
    rm -rf "$CACHE_DIR"
    echo "Removed: $CACHE_DIR"
  fi

  if [[ -d "$STATE_DIR" ]]; then
    rm -rf "$STATE_DIR"
    echo "Removed: $STATE_DIR"
  fi
else
  echo "Keeping Vimdo data:"
  echo "  $CACHE_DIR"
  echo "  $STATE_DIR"
fi

echo
echo "Vimdo uninstalled."
