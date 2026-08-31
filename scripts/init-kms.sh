#!/usr/bin/env bash
# TradeForge — local KMS initialisation script
#
# Alternative to `docker compose --profile init run --rm localstack-init`.
# Run this directly if you prefer a standalone script, or if docker compose run
# is not available in your workflow.
#
# Prerequisites:
#   - docker compose up -d (LocalStack must be healthy first)
#   - AWS CLI installed locally (or run via: docker exec tradeforge-localstack awslocal ...)
#
# Usage:
#   bash scripts/init-kms.sh
#
# After running, copy the KeyMetadata.KeyId from the output and set in .env:
#   KMS_KEY_ARN=arn:aws:kms:ap-south-1:000000000000:key/<KeyId>

set -euo pipefail

LOCALSTACK_URL="${KMS_ENDPOINT_URL:-http://localhost:4566}"
REGION="ap-south-1"

echo "Waiting for LocalStack to be ready at ${LOCALSTACK_URL}..."
until curl -fs "${LOCALSTACK_URL}/_localstack/health" > /dev/null 2>&1; do
  sleep 2
done
echo "LocalStack is ready."

echo ""
echo "Creating TradeForge CMK..."
aws --endpoint-url="${LOCALSTACK_URL}" \
    --region "${REGION}" \
    kms create-key \
    --description "TradeForge broker credentials key (local dev)" \
    --key-usage ENCRYPT_DECRYPT \
    --key-spec SYMMETRIC_DEFAULT

echo ""
echo "Done. Copy the KeyMetadata.KeyId above and set in .env:"
echo "  KMS_KEY_ARN=arn:aws:kms:${REGION}:000000000000:key/<KeyId>"
