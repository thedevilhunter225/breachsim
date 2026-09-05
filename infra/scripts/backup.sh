#!/bin/sh
set -eu

umask 077
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
backup_dir=${BACKUP_DIR:-"$project_root/backups"}
case "$backup_dir" in
  /*) ;;
  *) backup_dir="$project_root/$backup_dir" ;;
esac
mkdir -p "$backup_dir"

stamp=$(date -u +%Y%m%dT%H%M%SZ)
compose() {
  docker compose \
    --env-file "$project_root/.env.production" \
    -f "$project_root/docker-compose.production.yml" \
    "$@"
}

compose exec -T postgres pg_dump -U breachsim -d breachsim -Fc > "$backup_dir/postgres-$stamp.dump"

docker run --rm \
  --volume breachsim_media_data:/source:ro \
  --volume "$backup_dir:/backup" \
  alpine:3.22 tar -C /source -czf "/backup/media-$stamp.tar.gz" .

docker run --rm \
  --volume breachsim_report_data:/source:ro \
  --volume "$backup_dir:/backup" \
  alpine:3.22 tar -C /source -czf "/backup/reports-$stamp.tar.gz" .

echo "Backup created in $backup_dir with timestamp $stamp"
