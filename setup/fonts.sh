#!/usr/bin/env bash
# Ambil font Poppins dan Inter (OFL) dari repo Google Fonts kalau belum ada
set -e
cd "$(dirname "$0")/.."
mkdir -p fonts
for w in Regular SemiBold Bold ExtraBold Black; do
  f="fonts/Poppins-$w.ttf"
  [ -s "$f" ] || curl -sSL -o "$f" "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-$w.ttf"
done
# Inter (variabel) dipakai scene "ui"; kalau gagal diunduh, scenes_ui.py otomatis memakai Poppins
[ -s fonts/Inter-Var.ttf ] || curl -sSL -o fonts/Inter-Var.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf" || rm -f fonts/Inter-Var.ttf
ls fonts
