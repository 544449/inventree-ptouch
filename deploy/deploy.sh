#!/bin/bash
# Install the committed HEAD on the InvenTree server and restart it.
set -euo pipefail
: "${HOST:?set HOST=user@server (the InvenTree user)}"
: "${PW:?set PW=<ssh password>}"
DEST=/home/inventree/plugins/inventree-ptouch
cd "$(dirname "$0")/.."
git archive --format=tar HEAD | plink -batch -pw "$PW" "$HOST" \
  "rm -rf $DEST && mkdir -p $DEST && tar -x -C $DEST"
plink -batch -pw "$PW" "$HOST" "set -e
~/env/bin/pip install --no-deps --force-reinstall $DEST 2>&1 | tail -1
grep -qxF '$DEST' ~/src/config/plugins.txt || echo '$DEST' >> ~/src/config/plugins.txt
supervisorctl restart inventree-server inventree-cluster
supervisorctl status"
