#!/bin/sh

set -eu

. ./deploy/certbot-common.sh

step "Preparing ACME challenge publication"
load_certbot_env
require_domain

TOKEN="codex-challenge-$(date +%s)"
CONTENT="challenge-check-for-${DOMAIN}"
log "Challenge token: ${TOKEN}"
log "Expected challenge body: ${CONTENT}"

step "Starting base HTTP nginx service"
compose_base up -d nginx
step "Writing challenge file into the shared certbot webroot"
compose_https run --rm --entrypoint /bin/sh certbot -c \
  "mkdir -p /var/www/certbot/.well-known/acme-challenge && printf '%s\n' '$CONTENT' > /var/www/certbot/.well-known/acme-challenge/$TOKEN"

step "Challenge test file published"
echo "Check this URL from outside your network:"
echo "http://${DOMAIN}/.well-known/acme-challenge/${TOKEN}"
echo
echo "Expected response body:"
echo "${CONTENT}"
