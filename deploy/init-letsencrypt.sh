#!/bin/sh
set -eu

echo "[deploy] Legacy helper invoked."
echo "[deploy] This script only publishes a test ACME challenge."
echo "[deploy] It does not request a certificate by itself."
echo

sh ./deploy/publish-challenge.sh
echo
echo "If the URL above returns the expected body, request the certificate with:"
echo "sh ./deploy/request-certificate.sh"
