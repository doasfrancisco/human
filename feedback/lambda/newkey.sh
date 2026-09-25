#!/usr/bin/env bash
set -euo pipefail
NAME=${1:?give the name of the person}
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET=human-training-$ACCOUNT
KEY=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
USER=$(python3 -c 'import secrets; print(secrets.token_hex(4))')
printf '{"user": "%s", "name": "%s"}\n' "$USER" "$NAME" | aws s3 cp - "s3://$BUCKET/keys/$KEY" --content-type application/json
echo "user $USER for $NAME"
echo "send this: human login $KEY"
