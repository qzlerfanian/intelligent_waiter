#!/bin/sh
set -eu
backup_dir="${BACKUP_DIR:-/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
umask 077
pg_dump --format=custom --no-owner --no-acl "$DATABASE_URL" > "$backup_dir/baran-$timestamp.dump"
find "$backup_dir" -name 'baran-*.dump' -mtime "+${BACKUP_RETENTION_DAYS:-14}" -delete
echo "$backup_dir/baran-$timestamp.dump"
