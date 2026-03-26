#!/bin/sh
set -eu

if [ -z "${DOMAIN:-}" ] || [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
  echo "DOMAIN and LETSENCRYPT_EMAIL must be set."
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.https.yml up -d nginx

docker compose -f docker-compose.yml -f docker-compose.https.yml run --rm certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN"

docker compose -f docker-compose.yml -f docker-compose.https.yml up -d
