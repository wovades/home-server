#!/usr/bin/env bash
# Quick checks that change nothing on the server. install.sh runs this first.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
fails=0

for f in tools/*; do
  [[ -f $f ]] || continue
  case $f in
    *.md) ;;
    *) if head -1 "$f" | grep -q python || [[ $f == *.py ]]; then
         python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$f" || { echo "Python error: $f"; fails=1; }
       else
         bash -n "$f" || { echo "Bash error: $f"; fails=1; }
       fi ;;
  esac
done
python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" scripts/backup.py || { echo "Python error: backup.py"; fails=1; }

# backup.py: the qBittorrent rule takes settings, not downloads or logs
tmp=$(mktemp -d)
mkdir -p "$tmp/qbittorrent/qBittorrent/logs" "$tmp/qbittorrent/qBittorrent/BT_backup" "$tmp/qbittorrent/downloads"
touch "$tmp/qbittorrent/qBittorrent/qBittorrent.conf" "$tmp/qbittorrent/qBittorrent/categories.json" \
      "$tmp/qbittorrent/qBittorrent/BT_backup/a.torrent" "$tmp/qbittorrent/qBittorrent/BT_backup/a.fastresume" \
      "$tmp/qbittorrent/qBittorrent/logs/qbittorrent.log" "$tmp/qbittorrent/downloads/movie.mkv"
out=$(python3 - "$tmp" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("backup", "scripts/backup.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
b.APPDATA = sys.argv[1]
files, _, unmatched = b.plan()
print(sorted(r.split("qbittorrent/", 1)[1] for _, r, label in files if label == "qBittorrent"), unmatched)
PY
)
rm -rf "$tmp"
expected="['qBittorrent/BT_backup/a.fastresume', 'qBittorrent/BT_backup/a.torrent', 'qBittorrent/categories.json', 'qBittorrent/qBittorrent.conf'] []"
[[ $out == "$expected" ]] || { echo "backup.py qBittorrent rule: got $out"; fails=1; }

# backup.py: the CWA rule takes its databases, not processed books, logs or WAL files
tmp=$(mktemp -d)
c="$tmp/calibre-web-automated/config"
mkdir -p "$c/processed_books/imported" "$c/log_archive"
touch "$c/app.db" "$c/cwa.db" "$c/app.db-wal" "$c/calibre-web.log" \
      "$c/processed_books/imported/book.epub" "$c/log_archive/old.db"
out=$(python3 - "$tmp" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("backup", "scripts/backup.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
b.APPDATA = sys.argv[1]
files, _, unmatched = b.plan()
print(sorted(r.split("calibre-web-automated/", 1)[1] for _, r, label in files if label == "Books (CWA)"), unmatched)
PY
)
rm -rf "$tmp"
expected="['config/app.db', 'config/cwa.db'] []"
[[ $out == "$expected" ]] || { echo "backup.py CWA rule: got $out"; fails=1; }

# install.sh: the tools folder goes in FRONT of the PATH (Debian's /usr/bin/edit must not win)
grep -qF 'PATH="/DATA/scripts/tools:$PATH"' install.sh || { echo "install.sh: tools not in front of PATH"; fails=1; }

# restore: finds files where backup.py puts them
out=$(python3 - <<'PY'
import importlib.util
from importlib.machinery import SourceFileLoader
spec = importlib.util.spec_from_loader("restore", SourceFileLoader("restore", "tools/restore"))
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
for p in ["/DATA/AppData/big-bear-home-assistant/config/automations.yaml",
          "/DATA/scripts/backup.py", "/etc/casaos/gateway.ini", "/DATA/scripts/tools/cheat"]:
    print(r.member_for(p))
PY
)
expected="AppData/big-bear-home-assistant/config/automations.yaml
system/backup.py
system/etc_casaos/gateway.ini
system/DATA_scripts_tools/cheat"
[[ $out == "$expected" ]] || { echo "restore paths: got $out"; fails=1; }

# _check: HA's header lines and Life Tracker undo lines are fine in tag_log.csv
out=$(python3 - <<'PY'
import sys; sys.path.insert(0, "tools")
import _check
log = ("Home Assistant (Log started: 2026-11-01T08:00:00.000000+00:00)\n" + "-" * 80 + "\n"
       "2026-11-15,08:10,coffee\n2026-11-15,08:12,undo 2026-11-15 08:10 coffee\n"
       "2026-11-15,08:13,undo 2026-11-15 08:12 undo 2026-11-15 08:10 coffee\n"
       "2026-11-15,09:00,Coffee\n" + "-" * 80 + "\n2026-11-15,coffee\n")
print([n for n, _ in _check.bad_log_lines(log)])
PY
)
[[ $out == "[6, 7, 8]" ]] || { echo "log check: got $out"; fails=1; }

# _check: dashboard lines HA accepts (a "?" inside {text: ...}) are valid YAML
tmp=$(mktemp --suffix=.yaml)
echo '- {type: button, tap_action: {action: perform-action, confirmation: {text: Log a coffee?}}}' >"$tmp"
if python3 -c "import yaml; yaml.CSafeLoader" 2>/dev/null; then
  python3 tools/_check.py "$tmp" >/dev/null || { echo "_check rejects HA dashboard YAML"; fails=1; }
fi
rm -f "$tmp"

[[ $fails -eq 0 ]] && echo "All checks passed" || exit 1
