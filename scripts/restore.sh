#!/bin/sh
set -eu
if [ "$#" -ne 1 ]; then echo "usage: restore.sh /backups/baran-TIMESTAMP.dump"; exit 2; fi
test -f "$1"
pg_restore --clean --if-exists --no-owner --no-acl --dbname="$DATABASE_URL" "$1"
