#!/bin/sh
set -e

host_from_db_url() {
  echo "$1" | sed -E 's#^[^:]+://[^@]+@([^:/]+):.*$#\1#'
}

port_from_db_url() {
  echo "$1" | sed -E 's#^[^:]+://[^@]+@[^:/]+:([0-9]+).*$#\1#'
}

wait_for_db() {
  db_host="$(host_from_db_url "$DATABASE_URL")"
  db_port="$(port_from_db_url "$DATABASE_URL")"

  if [ -z "$db_host" ] || [ -z "$db_port" ]; then
    echo "[entrypoint] DATABASE_URL parse failed, skip wait"
    return 0
  fi

  echo "[entrypoint] waiting for db $db_host:$db_port"
  i=0
  until nc -z "$db_host" "$db_port"; do
    i=$((i+1))
    if [ "$i" -ge 60 ]; then
      echo "[entrypoint] db not ready"
      exit 1
    fi
    sleep 1
  done
  echo "[entrypoint] db is ready"
}

run_migrations() {
  echo "[entrypoint] running migrations"
  alembic upgrade head
}

case "$1" in
  bot)
    wait_for_db
    run_migrations
    exec python -m sputnik_offer_crm.main
    ;;
  notifications)
    wait_for_db
    run_migrations
    exec sputnik-notifications
    ;;
  migrate)
    wait_for_db
    exec alembic upgrade head
    ;;
  test)
    exec pytest
    ;;
  *)
    exec "$@"
    ;;
esac
