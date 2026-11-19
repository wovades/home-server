# Home server

Short commands for the home server (Dell OptiPlex, Debian + CasaOS) and the nightly backup
script. The full list of commands is in [tools/CHEATSHEET.md](tools/CHEATSHEET.md); on the
server, type `cheat`.

## Install or update

First time (on the server):

```bash
git -c core.sshCommand="ssh -i ~/.ssh/home_server_deploy -o IdentitiesOnly=yes" clone git@github.com:wovades/home-server.git ~/home-server
git -C ~/home-server config core.sshCommand "ssh -i ~/.ssh/home_server_deploy -o IdentitiesOnly=yes"
sudo ~/home-server/install.sh
```

After that, to get a merged change: `tools-update`

`install.sh` copies `tools/` to `/DATA/scripts/tools`, puts that folder at the front of the
PATH (so `edit` is ours, not Debian's own `/usr/bin/edit`), and
installs `scripts/backup.py` to `/DATA/scripts/backup.py` (it shows the difference and asks
first). It runs `tests/check.sh` before installing anything.

## Workflow

- `main` is what's installed on the server.
- Each change comes as a pull request. Merge it, then run `tools-update`.
- To undo a change: **Revert** on its pull request, merge, `tools-update`.

## What else is here

- `apps/`: Docker Compose files for apps installed as custom CasaOS apps (Calibre-Web Automated)
- `systemd/`: the backup timer, and the backup service as an example (the live one holds a secret)
- `docs/kobo.md`: Kobo sync commands and troubleshooting

## If the tools are ever missing

The raw commands behind them:

```bash
sudo python3 /DATA/scripts/backup.py --list            # backups
sudo systemctl start homeserver-backup.service         # backup-now
sudo journalctl -u homeserver-backup -n 20 --no-pager -o cat
sudo systemctl status|restart lifetracker              # status / lt-restart
sudo journalctl -u lifetracker -n 30                   # lt-logs
# restore one file by hand
sudo mkdir -p /tmp/restore && sudo tar xzf /DATA/backups/homeserver-DATE.tar.gz -C /tmp/restore
# copy the file back, then: sudo rm -r /tmp/restore
```

## Not in this repo

The backup's systemd service file holds the Uptime Kuma push URL, so it stays on the server
only (it's in the nightly backup). Never commit tokens, passwords or `secrets.yaml`.
