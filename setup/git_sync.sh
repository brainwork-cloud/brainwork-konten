#!/usr/bin/env bash
# Sinkron repo brainwork-cloud/brainwork-konten dari komputer Naufal (dipakai agen lewat device_bash).
#   bash git_sync.sh pull                -> clone/pull ke $HOME/brainwork-konten, cetak path
#   bash git_sync.sh push "pesan commit" -> commit semua perubahan lalu push
#   bash git_sync.sh runs                -> status 5 run GitHub Actions terakhir
# Token dibaca dari file .github_token.txt di folder agen_konten; tidak pernah dicetak.
set -e
A="$HOME/mnt/Nopal Brainwork/agen_konten"
TOKF="$A/.github_token.txt"; [ -f "$TOKF" ] || TOKF="$A/.github_token"
TOK=$(tr -d ' \n\r' < "$TOKF")
AUTH=$(printf 'x-access-token:%s' "$TOK" | base64 | tr -d '\n')
R="$HOME/brainwork-konten"
g() { git -c http.extraheader="AUTHORIZATION: basic $AUTH" "$@" 2>&1 | sed "s/$TOK/***/g"; }
case "$1" in
  pull)
    if [ -d "$R/.git" ]; then (cd "$R" && g pull -q --rebase origin main); else g clone -q https://github.com/brainwork-cloud/brainwork-konten "$R"; fi
    cd "$R"; git config user.name brainwork-cloud; git config user.email brainwork-cloud@users.noreply.github.com
    echo "$R" ;;
  push)
    cd "$R"; git add -A
    if git diff --cached --quiet; then echo "tidak ada perubahan"; exit 0; fi
    git commit -qm "${2:-update dari agen}"; g pull -q --rebase origin main; g push -q origin main; git log --oneline -1 ;;
  runs)
    curl -s -H "Authorization: Bearer $TOK" "https://api.github.com/repos/brainwork-cloud/brainwork-konten/actions/runs?per_page=5" \
      | python3 -c "import sys,json;[print(r['created_at'],r['name'],r['status'],r['conclusion']) for r in json.load(sys.stdin)['workflow_runs']]" ;;
  *) echo "pakai: pull | push \"pesan\" | runs"; exit 1 ;;
esac
