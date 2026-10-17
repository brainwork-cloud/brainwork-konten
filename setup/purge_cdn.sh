#!/usr/bin/env bash
# Hapus cache jsDelivr untuk file aset yang baru di-push (dipanggil workflow render).
# Link "Putar video" / "Lihat semua slide" di Sheet memakai https://cdn.jsdelivr.net/gh/brainwork-cloud/brainwork-konten@main/...
# jsDelivr menyimpan cache @main (termasuk 404 kalau file belum ada) sampai 12 jam, jadi harus dibersihkan setelah render.
[ $# -eq 0 ] && exit 0
B="https://purge.jsdelivr.net/gh/brainwork-cloud/brainwork-konten@main"
for f in "$@"; do curl -s -o /dev/null --max-time 20 "$B/$f" || true; done
for d in $(printf '%s\n' "$@" | xargs -n1 dirname | sort -u); do curl -s -o /dev/null --max-time 20 "$B/$d/" || true; done
echo "purge cdn: $# file"
