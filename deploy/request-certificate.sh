#!/bin/sh

set -eu

. ./deploy/certbot-common.sh

step "Preparing Let's Encrypt certificate request"
load_certbot_env
require_certbot_env

step "Starting base HTTP nginx service for ACME validation"
compose_base up -d nginx

step "Requesting certificate from Let's Encrypt"
compose_https run --rm --entrypoint certbot certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN"

step "Starting full HTTPS stack"
compose_https up -d
step "Certificate request flow completed"
