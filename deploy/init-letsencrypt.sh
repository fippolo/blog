#!/bin/sh
set -eu

sh ./deploy/publish-challenge.sh
echo
echo "If the URL above returns the expected body, request the certificate with:"
echo "sh ./deploy/request-certificate.sh"
