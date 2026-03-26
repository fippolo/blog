#!/bin/sh

set -eu

log() {
  printf '%s\n' "[deploy] $*"
}

step() {
  printf '%s\n' "[deploy][step] $*"
}

warn() {
  printf '%s\n' "[deploy][warn] $*"
}

read_env_value() {
  key="$1"
  if [ ! -f ".env" ]; then
    warn ".env not found in the current directory; only shell environment variables will be used."
    return 0
  fi

  grep -E "^${key}=" .env | head -n 1 | cut -d '=' -f 2- | tr -d '\r'
}

load_certbot_env() {
  step "Loading deployment variables"
  DOMAIN="${DOMAIN:-$(read_env_value DOMAIN)}"
  LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-$(read_env_value LETSENCRYPT_EMAIL)}"
  export DOMAIN
  export LETSENCRYPT_EMAIL
  if [ -n "${DOMAIN:-}" ]; then
    log "DOMAIN=${DOMAIN}"
  else
    warn "DOMAIN is empty"
  fi
  if [ -n "${LETSENCRYPT_EMAIL:-}" ]; then
    log "LETSENCRYPT_EMAIL=${LETSENCRYPT_EMAIL}"
  else
    warn "LETSENCRYPT_EMAIL is empty"
  fi
}

require_domain() {
  if [ -z "${DOMAIN:-}" ]; then
    echo "DOMAIN must be set, either in the shell environment or in .env."
    exit 1
  fi
  log "Domain value is present"
}

require_certbot_env() {
  if [ -z "${DOMAIN:-}" ] || [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
    echo "DOMAIN and LETSENCRYPT_EMAIL must be set, either in the shell environment or in .env."
    exit 1
  fi
  log "Domain and email values are present"
}

compose_https() {
  log "Running docker compose with HTTPS overlay: docker-compose.yml + docker-compose.https.yml"
  docker compose -f docker-compose.yml -f docker-compose.https.yml "$@"
}

compose_base() {
  log "Running docker compose with base HTTP stack: docker-compose.yml"
  docker compose -f docker-compose.yml "$@"
}
