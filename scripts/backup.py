#!/usr/bin/env python3
"""Home server backup

Copies the settings of every app (plus the Life Tracker log) into one dated
archive in /DATA/backups. Skips big or rebuildable things: movies, Home
Assistant's history database, logs, caches. Databases are copied safely
even while the apps are running.

Keeps the last 14 days plus one backup per month for a year.
Python standard library only - nothing to install.

  sudo python3 backup.py --list     # show what would be backed up, change nothing
  sudo python3 backup.py            # make a backup now
"""
import argparse
import datetime
import fnmatch
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request

APPDATA = "/DATA/AppData"
DEST = "/DATA/backups"
MAX_FILE = 50 * 1024 * 1024          # skip single files bigger than this
KEEP_DAILY = 14
KEEP_MONTHLY = 12
PREFIX = "homeserver-"

# (label, words in the AppData folder name, only these file names (None = all), skip these)
RULES = [
    ("Life Tracker", ["lifetracker"], None, ["*.tmp"]),
    ("Home Assistant", ["home-assistant", "homeassistant"], None,
     ["home-assistant_v2.db*", "*.log", "*.log.*", "*.db-wal", "*.db-shm",
      "tts/*", "deps/*", "backups/*", "*__pycache__*", ".cloud/*"]),
    ("Homepage", ["homepage"], None, ["logs/*", "*.log"]),
    ("Uptime Kuma", ["kuma"], None, ["*.db-wal", "*.db-shm", "screenshots/*", "docker-tls/*"]),
    ("AdGuard Home", ["adguard"], ["*.yaml", "*.yml"], []),
    ("Nginx Proxy Manager", ["nginx", "npm", "proxy"], None,
     ["logs/*", "*.log", "*.log.*", "*.db-wal", "*.db-shm", "*/temp/*"]),
    # Jellyfin's folder also holds the movies - take only its small settings files
    ("Jellyfin settings", ["jellyfin"], ["*.xml"], ["data/movies/*", "data/tvshows/*", "*/cache/*", "*/metadata/*"]),
    # qBittorrent: settings, categories and torrent resume data only - never the downloads
    ("qBittorrent", ["qbittorrent"], ["*.conf", "*.json", "*.torrent", "*.fastresume"],
     ["logs/*", "GeoDB/*", "*.log", "*.log.*"]),
    # Calibre-Web Automated: its databases only (users, shelves, Kobo token, settings) - never the books
    ("Books (CWA)", ["calibre-web"], ["*.db"],
     ["processed_books/*", "log_archive/*", "*.db-wal", "*.db-shm"]),
]

EXTRA_FILES = [  # outside AppData
    os.path.abspath(__file__),  # this script itself
    "/etc/systemd/system/lifetracker.service",
    "/etc/systemd/system/homeserver-backup.service",
    "/etc/systemd/system/homeserver-backup.timer",
    "/DATA/Books/library/metadata.db",  # e-book library: titles, authors, covers info (not the books)
]


# Folders outside AppData: only small settings files are taken
EXTRA_DIRS = [
    ("CasaOS app settings", "/var/lib/casaos/apps", ["*.yml", "*.yaml", "*.json"]),
    ("CasaOS settings", "/etc/casaos", ["*.conf", "*.json", "*.yml", "*.yaml", "*.ini"]),
    ("Server tools", "/DATA/scripts/tools", ["*"]),
]


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def rule_for(folder):
    name = folder.lower()
    for rule in RULES:
        if any(word in name for word in rule[1]):
            return rule
    return None


def matches(rel, patterns):
    """A pattern matches the file name, the path, or the path inside any subfolder."""
    base = os.path.basename(rel)
    return any(fnmatch.fnmatch(base, p) or fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, "*/" + p)
               for p in patterns)


def is_sqlite(path):
    try:
        with open(path, "rb") as f:
            return f.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def plan():
    """Returns (files, skipped, unmatched): files = [(source, path in archive, label)]."""
    files, skipped, unmatched = [], [], []
    try:
        folders = sorted(os.listdir(APPDATA))
    except OSError as e:
        sys.exit(f"Can't read {APPDATA}: {e}")
    for folder in folders:
        root = os.path.join(APPDATA, folder)
        if not os.path.isdir(root):
            continue
        rule = rule_for(folder)
        if not rule:
            unmatched.append(folder)
            continue
        label, _, only, skip = rule
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for fn in sorted(filenames):
                src = os.path.join(dirpath, fn)
                rel = os.path.relpath(src, root)
                if os.path.islink(src) or not os.path.isfile(src):
                    continue
                if matches(rel, skip) or (only and not matches(rel, only)):
                    continue
                size = os.path.getsize(src)
                if size > MAX_FILE:
                    skipped.append((f"{folder}/{rel}", size))
                    continue
                files.append((src, os.path.join("AppData", folder, rel), label))
    for label, base, only in EXTRA_DIRS:
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames.sort()
            for fn in sorted(filenames):
                src = os.path.join(dirpath, fn)
                rel = os.path.relpath(src, base)
                if os.path.islink(src) or not os.path.isfile(src) or not matches(rel, only):
                    continue
                if os.path.getsize(src) > MAX_FILE:
                    skipped.append((src, os.path.getsize(src)))
                    continue
                files.append((src, os.path.join("system", base.strip("/").replace("/", "_"), rel), label))
    for src in EXTRA_FILES:
        if os.path.isfile(src):
            files.append((src, os.path.join("system", os.path.basename(src)), "System services"))
    return files, skipped, unmatched


def copy_file(src, dst):
    """Databases via SQLite's own backup (consistent while the app runs), others as plain copies."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if is_sqlite(src):
        try:
            source = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)
            target = sqlite3.connect(dst)
            with target:
                source.backup(target)
            target.close()
            source.close()
            return "db"
        except sqlite3.Error:
            pass  # fall back to a plain copy
    shutil.copy2(src, dst)
    return "file"


def rotate(dest, today):
    """Keep the newest KEEP_DAILY, plus the first backup of each of the last KEEP_MONTHLY months."""
    backups = []
    for fn in os.listdir(dest):
        if fn.startswith(PREFIX) and fn.endswith(".tar.gz"):
            try:
                day = datetime.date.fromisoformat(fn[len(PREFIX):-len(".tar.gz")])
            except ValueError:
                continue
            backups.append((day, fn))
    backups.sort(reverse=True)
    keep = {fn for _, fn in backups[:KEEP_DAILY]}
    first_of_month = {}
    for day, fn in sorted(backups):
        first_of_month.setdefault((day.year, day.month), fn)
    months = sorted(first_of_month, reverse=True)[:KEEP_MONTHLY]
    keep |= {first_of_month[m] for m in months}
    removed = []
    for _, fn in backups:
        if fn not in keep:
            os.remove(os.path.join(dest, fn))
            removed.append(fn)
    return removed


def push(url, ok, msg):
    """Tell Uptime Kuma (Push monitor) that the backup ran."""
    if not url:
        return
    q = urllib.parse.urlencode({"status": "up" if ok else "down", "msg": msg[:200], "ping": ""})
    try:
        urllib.request.urlopen(url.split("?")[0] + "?" + q, timeout=15).read()
    except Exception as e:
        print(f"Could not reach Uptime Kuma: {e}")


def list_only():
    files, skipped, unmatched = plan()
    by_label = {}
    for src, _, label in files:
        n, size = by_label.get(label, (0, 0))
        by_label[label] = (n + 1, size + os.path.getsize(src))
    print("Would back up:")
    for label, (n, size) in by_label.items():
        print(f"  {label:<22} {n:>5} files  {human(size):>9}")
    total = sum(s for _, s in by_label.values())
    print(f"  {'Total (before zipping)':<22} {len(files):>5} files  {human(total):>9}")
    if skipped:
        print(f"\nSkipped, bigger than {human(MAX_FILE)}:")
        for path, size in skipped:
            print(f"  {path} ({human(size)})")
    if unmatched:
        print("\nAppData folders not backed up (no rule for them):")
        for folder in unmatched:
            print(f"  {folder}")


def run(push_url):
    today = datetime.date.today()
    os.makedirs(DEST, mode=0o700, exist_ok=True)
    os.chmod(DEST, 0o700)  # contains tokens and passwords: root only
    files, skipped, unmatched = plan()
    if not files:
        raise RuntimeError("Nothing found to back up")

    stage = tempfile.mkdtemp(prefix=".staging-", dir=DEST)
    try:
        counts = {"db": 0, "file": 0}
        errors = []
        for src, rel, _ in files:
            try:
                counts[copy_file(src, os.path.join(stage, rel))] += 1
            except OSError as e:
                errors.append(f"{rel}: {e}")
        with open(os.path.join(stage, "MANIFEST.txt"), "w", encoding="utf-8") as f:
            f.write(f"Home server backup {datetime.datetime.now():%Y-%m-%d %H:%M}\n\n")
            f.write(f"{counts['file']} files + {counts['db']} databases (safe copies)\n")
            if skipped:
                f.write("\nSkipped (too big):\n" + "".join(f"  {p} ({human(s)})\n" for p, s in skipped))
            if unmatched:
                f.write("\nAppData folders without a rule (not included):\n" + "".join(f"  {u}\n" for u in unmatched))
            if errors:
                f.write("\nCould not copy:\n" + "".join(f"  {e}\n" for e in errors))

        final = os.path.join(DEST, f"{PREFIX}{today.isoformat()}.tar.gz")
        tmp = final + ".tmp"
        with tarfile.open(tmp, "w:gz") as tar:
            tar.add(stage, arcname=f"{PREFIX}{today.isoformat()}")
        os.chmod(tmp, 0o600)
        os.replace(tmp, final)  # a crash never leaves half an archive
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    removed = rotate(DEST, today)
    size = os.path.getsize(final)
    msg = f"{len(files)} files, {human(size)}" + (f", {len(errors)} errors" if errors else "")
    with open(os.path.join(DEST, "last_backup.json"), "w", encoding="utf-8") as f:
        json.dump({"date": today.isoformat(), "file": os.path.basename(final), "size": size,
                   "files": len(files), "databases": counts["db"], "errors": errors,
                   "removed_old": removed}, f, indent=2)
    print(f"Backup done: {final} ({msg})")
    if removed:
        print(f"Removed {len(removed)} old backup(s), keeping {KEEP_DAILY} days + 1 per month")
    if errors:
        print("Could not copy:\n  " + "\n  ".join(errors))
    push(push_url, not errors, msg)
    return 1 if errors else 0


def main():
    global APPDATA, DEST
    p = argparse.ArgumentParser(description="Home server backup")
    p.add_argument("--list", action="store_true", help="show what would be backed up, change nothing")
    p.add_argument("--push-url", default=os.environ.get("KUMA_PUSH_URL", ""), help="Uptime Kuma push URL")
    p.add_argument("--appdata", default=APPDATA)
    p.add_argument("--dest", default=DEST)
    a = p.parse_args()
    APPDATA, DEST = a.appdata, a.dest
    if a.list:
        return list_only()
    try:
        sys.exit(run(a.push_url))
    except Exception as e:
        print(f"Backup FAILED: {e}")
        push(a.push_url, False, f"failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
