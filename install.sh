#!/usr/bin/env bash
# Installs the server tools and the backup script. Run on the server: sudo ~/home-server/install.sh
# Safe to run again: it only replaces files that changed, and asks before touching backup.py.
set -euo pipefail
[[ $EUID -eq 0 ]] || exec sudo "$0" "$@"
cd "$(dirname "$(readlink -f "$0")")"

DEST=/DATA/scripts/tools
LIVE_BACKUP=/DATA/scripts/backup.py

bash tests/check.sh >/dev/null || { echo "Checks failed: nothing installed. Run: bash tests/check.sh"; exit 1; }

# 1. The commands and the cheat sheet
mkdir -p "$DEST"
find tools -maxdepth 1 -type f -exec cp {} "$DEST/" \;
rm -rf "$DEST/__pycache__"
chmod 755 "$DEST"/*
chmod 644 "$DEST/_common.sh" "$DEST/_check.py" "$DEST/CHEATSHEET.md"
echo "✓ Tools installed in $DEST"

# 2. Make them available as commands (new logins pick this up)
cat > /etc/profile.d/home-tools.sh <<'EOF'
case ":$PATH:" in *:/DATA/scripts/tools:*) ;; *) PATH="$PATH:/DATA/scripts/tools" ;; esac
EOF
echo "✓ Added to PATH"

# 3. Folder for the copies 'edit' keeps (root only)
mkdir -p /DATA/edit-backups && chmod 700 /DATA/edit-backups

# 4. The backup script
if ! cmp -s scripts/backup.py "$LIVE_BACKUP"; then
  echo
  echo "backup.py on the server differs from the one here (- server, + new):"
  diff -u --label server --label new "$LIVE_BACKUP" scripts/backup.py | tail -n +3 || true
  read -r -p "Install the new backup.py? [y/N] " a
  if [[ $a =~ ^[Yy] ]]; then
    cp -p "$LIVE_BACKUP" "$LIVE_BACKUP.bak"
    cp scripts/backup.py "$LIVE_BACKUP"
    echo "✓ backup.py updated (old one: $LIVE_BACKUP.bak)"
  else
    echo "  backup.py left as it was"
  fi
else
  echo "✓ backup.py is up to date"
fi

echo
echo "Done. Log out and back in (or run: source /etc/profile.d/home-tools.sh), then type: cheat"
