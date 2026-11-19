# Server cheat sheet

Type `cheat` to see this page, or `cheat <word>` for just the lines about one thing,
for example `cheat restore`. Commands that need it ask for your password themselves:
don't put `sudo` in front of them.

## The golden rule
Never edit a file with plain nano. Use `edit <file>` (or `edit-ha automations`).
It keeps a copy first, checks your work afterwards, and `undo-edit <file>` puts it back.
Gone wrong after a few days? `restore <file>` gets last night's version from the backup.

## Server
  status                   everything at a glance: RAM, disk, apps, last backup
  apps                     all apps and whether they're up
  app-logs <name> [lines]  an app's latest log lines (part of the name is enough: app-logs adguard)
  app-restart <name>       restart one app (asks first)

## Editing files safely
  edit <file>              copy → nano → check. Example: edit /DATA/scripts/backup.py
  edit-ha automations      the same for Home Assistant files:
                           automations | scripts | configuration | scenes | themes | dashboard
                           (dashboard = the Chores dashboard; afterwards refresh it in HA)
  undo-edit <file>         back to the copy from before your last edit (shows the change, asks)
  undo-edit <file> list    all saved copies (the newest 20 per file are kept)
  restore <file>           a file from last night's backup (shows the change, asks)
  restore <file> 2026-11-14   from a specific day
  restore <file> list      which backups have that file
  Home Assistant files also work by name: restore automations.yaml

After editing a Home Assistant file: HA → Developer tools → YAML → reload that part
(automations, scripts, themes), or Restart after configuration.yaml.
`edit` offers to let Home Assistant check the file first. Say yes.

Copies kept by edit/undo-edit/restore: /DATA/edit-backups (root only, not in the nightly backup)

## Backups (every night at 03:30)
  backups                  list of backups, how the last one went, next run
  backup-now               make one right now
  backup-check             what it would take, and app folders that have no rule yet
  New app installed? Run backup-check. If it's under "not backed up", ask Claude for a rule.

## Life Tracker and the log
  lt-deploy                install the latest merged version (after merging a pull request)
  dash-deploy              install the latest merged Chores dashboard + icon colours
                           (shows the changes, asks; undo-edit puts the old one back)
  lt-restart               restart it and check it answers
  lt-logs [lines]          its latest messages (reminders, confirmations, errors)
  log-tail [lines]         the last lines of tag_log.csv (default 20)
  log-fix                  remove or fix a wrong log line safely. Taps made while you're
                           editing are kept, and each line is checked before saving.

## These tools
  tools-update             get the latest merged version from GitHub and install it
  Code lives in the GitHub repo wovades/home-server, cloned to ~/home-server.
  Changes: pull request → merge → tools-update.

## nano keys (^ = Ctrl, M = Alt)
  ^O then Enter   save            ^X        quit (asks to save if needed)
  ^W              search          ^K        cut a whole line (repeat for more)
  ^U              paste the cut lines above the cursor
  M-/             jump to the end ^_        go to a line number
  M-U             undo            ^C        show which line you're on
  Phone keyboard without Ctrl/Alt? In Termius/JuiceSSH use the extra key row.

## Where things live
  Home Assistant config   /DATA/AppData/big-bear-home-assistant/config/
    automations.yaml, scripts.yaml, configuration.yaml, themes/chores.yaml
  The log                 …/config/tag_log.csv
  Life Tracker            /DATA/AppData/lifetracker/  (app.py, config.json – has a token, don't share)
  Life Tracker code       ~/life-tracker  (GitHub: wovades/life-tracker)
  Backups                 /DATA/backups  (root only)
  Backup script           /DATA/scripts/backup.py
  These tools             /DATA/scripts/tools/  (code: ~/home-server)
  Movies and shows        /DATA/AppData/jellyfin/data/movies, …/tvshows

## Five plain commands worth knowing
  ls -l <folder>           what's in a folder (sudo ls for root-only folders)
  cat <file>               print a short file
  grep <word> <file>       lines in a file that contain a word, e.g. grep coffee tag_log.csv
  free -h                  RAM: look at "available"
  sudo systemctl status <service>   is a service running? (q to leave)

## When something doesn't work
  1. status                 is everything up?
  2. app-logs <name> / lt-logs   what does the app say?
  3. Home Assistant automation: Settings → Automations → ⋮ → Traces shows which step failed
  4. Undo your last change: undo-edit <file>, or restore <file>
