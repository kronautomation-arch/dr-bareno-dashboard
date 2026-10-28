#!/bin/sh
# Cron de Railway (8am, 1pm, 7pm Colombia). dashboard/ vive en la rama gh-pages:
# se clona fresca para que el push -f de main.py conserve index.html, sw.js, etc.
set -e
rm -rf dashboard
git clone --quiet --depth 1 -b gh-pages "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" dashboard
exec python main.py
