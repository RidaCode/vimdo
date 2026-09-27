#!/usr/bin/env bash
set -euo pipefail

install_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
mkdir -p "$install_dir"
install -m 0755 "$(dirname "$0")/vimdo.py" "$install_dir/vimdo"

echo "Installed: $install_dir/vimdo"
case ":$PATH:" in
  *":$install_dir:"*) ;;
  *)
    echo
    echo "Add this to your shell config if needed:"
    echo "  export PATH=\"$install_dir:\$PATH\""
    ;;
esac

echo
echo "Try: vimdo cpp"
