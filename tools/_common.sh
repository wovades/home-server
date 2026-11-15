# Shared settings and helpers for the server tools. Not a command itself.

TOOLS_DIR=/DATA/scripts/tools
HA_CONFIG=/DATA/AppData/big-bear-home-assistant/config
TAG_LOG=$HA_CONFIG/tag_log.csv
BACKUP_DIR=/DATA/backups
EDIT_BACKUPS=/DATA/edit-backups
KEEP_COPIES=20

say()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ask "Question?"      -> yes only if you type y
# ask_yes "Question?"  -> yes unless you type n
ask()     { local a; read -r -p "$1 [y/N] " a; [[ $a =~ ^[Yy] ]]; }
ask_yes() { local a; read -r -p "$1 [Y/n] " a; [[ ! $a =~ ^[Nn] ]]; }

# Run the rest of the script as root (asks for your password once).
as_root() { [[ $EUID -eq 0 ]] || exec sudo "$0" "$@"; }

# Name under which copies of a file are kept in $EDIT_BACKUPS
copy_key() { local p=${1#/}; echo "${p//\//__}"; }

# save_copy FILE -> keeps a timestamped copy, prints its path
save_copy() {
  local f=$1 key dest
  key=$(copy_key "$f")
  mkdir -p "$EDIT_BACKUPS"; chmod 700 "$EDIT_BACKUPS"
  dest="$EDIT_BACKUPS/$key.$(date +%Y%m%d-%H%M%S-%6N)"
  cp -p "$f" "$dest"
  # newest first by name (the time is in the name); keep only the newest $KEEP_COPIES copies of this file
  ls -1 "$EDIT_BACKUPS/$key".* 2>/dev/null | sort -r | tail -n +$((KEEP_COPIES + 1)) | xargs -r rm -f
  echo "$dest"
}

# find_container PART -> prints the one container whose name matches
find_container() {
  local part=$1 names matches
  names=$(docker ps -a --format '{{.Names}}')
  if grep -qx -- "$part" <<<"$names"; then echo "$part"; return; fi
  matches=$(grep -i -- "$part" <<<"$names" || true)
  [[ -n $matches ]] || fail "No app matches '$part'. Type 'apps' to see the names."
  if [[ $(wc -l <<<"$matches") -gt 1 ]]; then
    warn "'$part' matches more than one app:"; sed 's/^/  /' <<<"$matches" >&2
    fail "Use more of the name."
  fi
  echo "$matches"
}

ha_container() { find_container 'home-assistant' 2>/dev/null || find_container 'homeassistant'; }
