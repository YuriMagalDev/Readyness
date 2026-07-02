#!/usr/bin/env bash
# Deploy: repo home (prefix Garmin) -> GitHub Readyness (main).
#
# O repo git local é o home inteiro (C:\Users\yurig); o GitHub Readyness recebe
# só o subtree do Garmin, com athlete_profile.json REMOVIDO do histórico
# (repo público, dado de saúde). split + filter-branch são determinísticos:
# rodadas futuras reproduzem os mesmos hashes antigos e só acrescentam commits.
#
# Depois, no server:  cd /home/ubuntu/readiness && git pull && sudo systemctl restart readiness-bot
set -euo pipefail

REMOTE=https://github.com/YuriMagalDev/Readyness.git
PREFIX=Documents/Antigravity/Garmin
TOP=$(git rev-parse --show-toplevel)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

git -C "$TOP" subtree split --prefix="$PREFIX" -b garmin-export
git clone -q --single-branch --branch garmin-export "$TOP" "$TMP/export"
cd "$TMP/export"
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --index-filter \
    "git rm --cached --ignore-unmatch athlete_profile.json" --prune-empty HEAD >/dev/null
if git log --oneline -- athlete_profile.json | grep -q .; then
    echo "ERRO: athlete_profile.json ainda no histórico — push abortado." >&2
    exit 1
fi
git push --force "$REMOTE" HEAD:main
echo "GitHub atualizado: $REMOTE (main)"
