#!/bin/sh

set -eu

. ./deploy/certbot-common.sh

load_certbot_env
require_certbot_env

compose_https up -d nginx

compose_https run --rm --entrypoint certbot certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN"

compose_https up -d
