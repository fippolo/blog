#!/bin/sh

set -eu

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.https.yml"

read_env_value() {
  key="$1"
  if [ ! -f ".env" ]; then
    return 0
  fi

  grep -E "^${key}=" .env | head -n 1 | cut -d '=' -f 2- | tr -d '\r'
}

load_certbot_env() {
  DOMAIN="${DOMAIN:-$(read_env_value DOMAIN)}"
  LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-$(read_env_value LETSENCRYPT_EMAIL)}"
  export DOMAIN
  export LETSENCRYPT_EMAIL
}

require_domain() {
  if [ -z "${DOMAIN:-}" ]; then
    echo "DOMAIN must be set, either in the shell environment or in .env."
    exit 1
  fi
}

require_certbot_env() {
  if [ -z "${DOMAIN:-}" ] || [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
    echo "DOMAIN and LETSENCRYPT_EMAIL must be set, either in the shell environment or in .env."
    exit 1
  fi
}

compose_https() {
  docker compose -f docker-compose.yml -f docker-compose.https.yml "$@"
}
