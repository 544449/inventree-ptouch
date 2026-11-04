#!/bin/bash
# Run a local Django script on the server: HOST=... PW=... deploy/run_django.sh deploy/setup_inventree.py
# PTOUCH_* variables (e.g. PTOUCH_BT_ADDRESS, PTOUCH_MACHINE_NAME) are passed to the script.
set -euo pipefail
: "${HOST:?set HOST=user@server (the InvenTree user)}"
: "${PW:?set PW=<ssh password>}"
ENVS=$(env | grep -E '^PTOUCH_[A-Z_]+=[A-Za-z0-9:._-]*$' | tr '\n' ' ' || true)
plink -batch -pw "$PW" "$HOST" \
  "cd ~/src/src/backend/InvenTree && $ENVS ~/env/bin/python manage.py shell 2>&1" < "$1" \
  | grep -vE '^(INFO|DEBUG)|objects imported automatically'
