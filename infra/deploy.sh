#!/usr/bin/env bash
# Deploy the stack, the Lambda code and the static site.
#
# Prerequisites: AWS credentials in the environment, the AWS CLI v2, Node.js 20+, Python 3.11+, zip.
# Usage: AWS_REGION=eu-central-1 [PYTHON=path/to/python] ./infra/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."
REGION="${AWS_REGION:-eu-central-1}"
STACK="${STACK:-isolated-italy}"
DAILY_CAP="${DAILY_CAP:-1000}"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"

aws sts get-caller-identity >/dev/null

# A stack left in ROLLBACK_COMPLETE cannot be updated; remove it first.
status="$(aws cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || true)"
if [ "$status" = "ROLLBACK_COMPLETE" ]; then
  aws cloudformation delete-stack --stack-name "$STACK"
  aws cloudformation wait stack-delete-complete --stack-name "$STACK"
fi

aws cloudformation deploy \
  --stack-name "$STACK" \
  --template-file infra/template.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides DailyCap="$DAILY_CAP" \
  --no-fail-on-empty-changeset

output() {
  aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
BUCKET="$(output Bucket)"
DISTRIBUTION="$(output DistributionId)"
FUNCTION="$(output FunctionName)"
POOL="$(output IdentityPoolId)"
URL="$(output SiteUrl)"

# Lambda package: the function plus a recent boto3 (the runtime's copy may not include geo-routes).
rm -rf infra/build && mkdir -p infra/build/package
"${PYTHON:-python3}" -m pip install --quiet --requirement infra/lambda/requirements.txt --target infra/build/package
cp infra/lambda/reach.py infra/build/package/
(cd infra/build/package && zip -qr ../reach.zip .)
aws lambda update-function-code --function-name "$FUNCTION" --zip-file fileb://infra/build/reach.zip >/dev/null

# Site: the map signs its requests with an unauthenticated Cognito identity, so no key is embedded in the bundle.
(cd web && npm ci --silent && VITE_IDENTITY_POOL_ID="$POOL" VITE_AWS_REGION="$REGION" npm run build)
aws s3 sync web/dist "s3://$BUCKET" --delete --exclude 'reach-cache/*' --cache-control 'public,max-age=300'
aws s3 sync web/dist/data "s3://$BUCKET/data" --cache-control 'public,max-age=86400'
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION" --paths '/*' >/dev/null

echo "Deployed: $URL"
