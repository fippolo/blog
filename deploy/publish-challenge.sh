#!/bin/sh

set -eu

. ./deploy/certbot-common.sh

load_certbot_env
require_domain

TOKEN="codex-challenge-$(date +%s)"
CONTENT="challenge-check-for-${DOMAIN}"

compose_https up -d nginx
compose_https run --rm --entrypoint /bin/sh certbot -c \
  "mkdir -p /var/www/certbot/.well-known/acme-challenge && printf '%s\n' '$CONTENT' > /var/www/certbot/.well-known/acme-challenge/$TOKEN"

echo "Challenge test file published."
echo "Check this URL from outside your network:"
echo "http://${DOMAIN}/.well-known/acme-challenge/${TOKEN}"
echo
echo "Expected response body:"
echo "${CONTENT}"
