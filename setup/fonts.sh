#!/usr/bin/env bash
# Ambil font Poppins (OFL) dari repo Google Fonts kalau belum ada
set -e
cd "$(dirname "$0")/.."
mkdir -p fonts
for w in Regular SemiBold Bold ExtraBold Black; do
  f="fonts/Poppins-$w.ttf"
  [ -s "$f" ] || curl -sSL -o "$f" "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-$w.ttf"
done
ls fonts
