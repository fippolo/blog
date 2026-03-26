#!/bin/sh

set -eu

. ./deploy/certbot-common.sh

step "Updating application repository"
log "Pulling the latest code from the current git remote"
git pull

step "Rebuilding and restarting the HTTPS stack"
compose_https up --build -d

step "Showing current container status"
compose_https ps

step "Pruning unused Docker images"
docker image prune -f

step "Update flow completed"
