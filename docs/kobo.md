# Kobo sync with Calibre-Web Automated

The Kobo (Aura H2O, firmware 4.38.23697) syncs the `Kobo` shelf from CWA, only on home Wi-Fi.
Setup was done on 2026-11-19; these are the commands that worked, for a reset or a new Kobo.

## The Kobo on the server
Plug it in and tap **Connect**: the server mounts it by itself at `/media/devmon/KOBOeReader`
(`lsblk -f` shows label `KOBOeReader`). The folder belongs to `devmon`, so only `sudo` commands
get in. Unmount before unplugging: `sync; sudo umount /media/devmon/KOBOeReader`

## Point a Kobo at the server
CWA → your user name → **Kobo Sync Token** → Create → keep the code after `/kobo/`. Then, with
the Kobo connected (use the IP, not `books.lan`; the `.bak` keeps the Kobo store setting):

```bash
K="/media/devmon/KOBOeReader/.kobo/Kobo/Kobo eReader.conf"; sudo cp "$K" "$K.bak" && sudo grep -n api_endpoint "$K"
sudo sed -i 's#^api_endpoint=.*#api_endpoint=http://192.168.178.42:8083/kobo/PASTE_CODE#' "$K" && sudo grep -n api_endpoint "$K"
```

Undo (back to the Kobo store): `K="/media/devmon/KOBOeReader/.kobo/Kobo/Kobo eReader.conf"; sudo cp "$K.bak" "$K"`

## Bring books from a Kobo into CWA
```bash
sudo mkdir -p /DATA/kobo-backup/$(date +%F) && sudo cp -a /media/devmon/KOBOeReader/. /DATA/kobo-backup/$(date +%F)/
# doubled file names would overwrite each other: check first
sudo find /DATA/kobo-backup -path '*/.kobo' -prune -o -iname '*.epub' -printf '%f\n' | sort | uniq -d
sudo find /DATA/kobo-backup -path '*/.kobo' -prune -o -iname '*.epub' -exec cp {} /DATA/Books/ingest/ \;
```
No `rsync` on the server, hence `cp`. Delete `/DATA/kobo-backup` once the sync works.

## Remove side-loaded books from the Kobo
`find … -prune … -delete` deletes nothing (`-delete` refuses `-prune`), so skip hidden folders with `-not -path`:
```bash
sudo find /media/devmon/KOBOeReader -type f -not -path '*/.*' \( -iname '*.epub' -o -iname '*.pdf' -o -iname '*.mobi' \) -print | wc -l
sudo find /media/devmon/KOBOeReader -type f -not -path '*/.*' \( -iname '*.epub' -o -iname '*.pdf' -o -iname '*.mobi' \) -delete
```

## Troubleshooting
- Is the Kobo reaching CWA? During a sync: `sudo ss -tn | grep ':8083'` → a line with the Kobo's IP
- Does the sync address work? `curl -s -m 10 http://192.168.178.42:8083/kobo/PASTE_CODE/v1/initialization | head -c 300` → starts with `{`
- Cover addresses: same URL `| grep -oE '"image_[a-z_]+" *: *"[^"]*"'` → both start with `http://192.168.178.42:8083`
- A book removed from the shelf stays on the Kobo: the shelf needs **Sync this shelf with Kobo device** and the profile **Sync only books in selected shelves**, then Sync again
- First sync is slow (stays on "Connecting" for a while); covers appear after the downloads finish
- `app-logs calibre-web-automated` doesn't show every Kobo request
