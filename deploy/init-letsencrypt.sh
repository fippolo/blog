#!/bin/sh
set -eu

read_env_value() {
  key="$1"
  if [ ! -f ".env" ]; then
    return 0
  fi

  grep -E "^${key}=" .env | head -n 1 | cut -d '=' -f 2- | tr -d '\r'
}

DOMAIN="${DOMAIN:-$(read_env_value DOMAIN)}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-$(read_env_value LETSENCRYPT_EMAIL)}"

if [ -z "${DOMAIN:-}" ] || [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
  echo "DOMAIN and LETSENCRYPT_EMAIL must be set, either in the shell environment or in .env."
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.https.yml up -d nginx

docker compose -f docker-compose.yml -f docker-compose.https.yml run --rm --entrypoint certbot certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN"

docker compose -f docker-compose.yml -f docker-compose.https.yml up -d
