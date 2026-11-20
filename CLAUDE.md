# House rules for the home server tools

Read by every Claude session and by the automatic pull request review. Keep it short.

## What this repo is
Short commands for the home server (Dell OptiPlex 7040, Debian + CasaOS, 4 GB RAM), the nightly backup script, systemd files and app compose files. Installed on the server with `tools-update` (runs `install.sh`, which runs `tests/check.sh` first).

## Rules a change must follow
- **No secrets in the repo:** no tokens, passwords, push URLs, `secrets.yaml`. The live backup service file stays on the server; only the `.example` is here.
- **Never edit live files with plain `sudo nano`:** tools use `edit` / `edit-ha`, which keep a copy, check the file and allow `undo-edit`.
- **Commands ask for the password themselves;** the user never types `sudo` in front of a tool.
- **Every new app or new data on the server needs a backup rule** in `scripts/backup.py` (and must not pull in media, downloads, logs, caches or files over 50 MB). `backup-check` must not list it as "not backed up".
- **Tools must be safe to run twice** and must say clearly what they changed.
- **`tests/check.sh` must pass.** A new backup rule or tricky tool logic gets a check there.
- The cheat sheet `tools/CHEATSHEET.md` is the one list of commands: a new or changed command updates it.
- Bash tools use `tools/_common.sh`; keep them plain bash and Python 3 standard library (no installs).

## Every pull request
- Has a **How to test** section: a few concrete steps on the server, with what you should see.
- Says what to run after merging (usually `tools-update`, then log out and back in for new commands).
