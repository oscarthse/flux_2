# Deployment

> **Part of:** [Flux Architecture Documentation](./README.md)
> **Updated:** Terraform infrastructure (HCL), Python Lambda functions

---

### AWS Services Used

```
┌─────────────────────────────────────────────────────────────────┐
│                         Flux Platform                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Route 53   │────▶│  CloudFront  │────▶│   S3 Bucket  │    │
│  │     DNS      │     │     CDN      │     │  (Next.js)   │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│                              │                                    │
│                              │ /api/*                            │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              API Gateway (HTTP API)                     │    │
│  └────────────────────────────────────────────────────────┘    │
│                              │                                    │
│         ┌────────────────────┼────────────────────┐             │
│         │                    │                    │             │
│         ▼                    ▼                    ▼             │
│  ┌────────────┐      ┌────────────┐      ┌────────────┐       │
│  │  Lambda    │      │  Lambda    │      │  Lambda    │       │
│  │ (FastAPI)  │      │ (Webhook)  │      │  (Worker)  │       │
│  └────────────┘      └────────────┘      └────────────┘       │
│         │                    │                    ▲             │
│         │                    │                    │             │
│         ▼                    ▼                    │             │
│  ┌─────────────────────────────────────────────────────┐       │
│  │                    RDS PostgreSQL                    │       │
│  │                (Multi-AZ, Encrypted)                 │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │  EventBridge │────▶│  SQS Queues  │────▶│   Lambda     │   │
│  │   (Cron)     │     │   + DLQ      │     │  (Workers)   │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │   SageMaker  │     │  ElastiCache │     │      S3      │   │
│  │  Endpoint    │     │    Redis     │     │   (Assets)   │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │   Secrets    │     │  CloudWatch  │     │   Datadog    │   │
│  │   Manager    │     │     Logs     │     │  (Metrics)   │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Terraform Infrastructure

### Project Structure

```
infrastructure/
├── environments/
│   ├── dev/
│   │   ├── main.tf              # Main configuration for dev
│   │   ├── variables.tf
│   │   └── terraform.tfvars     # Dev-specific values
│   ├── staging/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars
│   └── prod/
│       ├── main.tf
│       ├── variables.tf
│       └── terraform.tfvars
├── modules/
│   ├── network/                 # VPC, subnets, security groups
│   ├── database/                # RDS PostgreSQL, ElastiCache
│   ├── compute/                 # Lambda functions
│   ├── storage/                 # S3 buckets
│   ├── queue/                   # SQS queues, EventBridge
│   ├── api/                     # API Gateway
│   ├── frontend/                # CloudFront distribution
│   ├── ml/                      # SageMaker endpoint
│   └── monitoring/              # CloudWatch dashboards, alarms
├── backend.tf                   # Terraform state backend (S3)
├── providers.tf                 # AWS provider configuration
└── versions.tf                  # Terraform version constraints
```

### CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml

name: Deploy Flux Platform

on:
  push:
    branches:
      - main
      - staging

env:
  AWS_REGION: us-east-1
  NODE_VERSION: '18'
  PYTHON_VERSION: '3.12'

jobs:
  test-and-build:
    name: Test & Build
    runs-on: ubuntu-latest
    outputs:
      environment: ${{ steps.set-env.outputs.environment }}
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Determine environment
        id: set-env
        run: |
          if [[ "${{ github.ref }}" == "refs/heads/main" ]]; then
            echo "environment=prod" >> $GITHUB_OUTPUT
          elif [[ "${{ github.ref }}" == "refs/heads/staging" ]]; then
            echo "environment=staging" >> $GITHUB_OUTPUT
          fi

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install Frontend Dependencies
        run: npm ci

      - name: Build Frontend
        run: npm run build --workspace=apps/web

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install Backend Dependencies
        run: uv pip install -r apps/api/requirements.txt
        working-directory: ./

      - name: Lint and Test Backend
        run: |
          uv run ruff check .
          uv run pytest
        working-directory: ./apps/api

      - name: Build Backend Lambda Package
        run: |
          mkdir -p dist/api
          cp -r apps/api/src/* dist/api/
          uv pip freeze > dist/api/requirements.txt
          cd dist/api
          pip install -r requirements.txt --target ./
          zip -r api.zip .

      - name: Upload Artifacts
        uses: actions/upload-artifact@v3
        with:
          name: build-artifacts
          path: |
            dist/
            apps/web/.next/

  deploy:
    name: Deploy to ${{ needs.test-and-build.outputs.environment }}
    needs: test-and-build
    runs-on: ubuntu-latest
    environment: ${{ needs.test-and-build.outputs.environment }}
    permissions:
      id-token: write # Required for AWS OIDC
      contents: read
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Download Artifacts
        uses: actions/download-artifact@v3
        with:
          name: build-artifacts
          path: .

      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.7.0

      - name: Terraform Init & Apply
        id: tf-apply
        run: |
          cd infrastructure/environments/${{ needs.test-and-build.outputs.environment }}
          terraform init -reconfigure
          terraform apply -auto-approve \
            -var="api_lambda_zip_path=../../../../dist/api/api.zip"

      - name: Run Database Migrations
        run: |
          uv pip install -r apps/api/requirements.txt
          uv run alembic upgrade head
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}

      - name: Deploy Frontend to S3 & Invalidate Cache
        run: |
          ENV=${{ needs.test-and-build.outputs.environment }}
          BUCKET_NAME=$(terraform -chdir=infrastructure/environments/$ENV output -raw frontend_bucket_name)
          DISTRIBUTION_ID=$(terraform -chdir=infrastructure/environments/$ENV output -raw cloudfront_distribution_id)
          aws s3 sync .next/ s3://$BUCKET_NAME --delete
          aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"
        working-directory: ./apps/web
```

## Deployment Strategy

### Blue-Green Deployment for Lambda

```hcl
# infrastructure/modules/compute/lambda-deployment.tf

resource "aws_lambda_alias" "prod" {
  name             = "prod"
  function_name    = aws_lambda_function.api.function_name
  function_version = aws_lambda_function.api.version
}

resource "aws_codedeploy_app" "lambda" {
  name             = "flux-${var.environment}-lambda"
  compute_platform = "Lambda"
}

resource "aws_codedeploy_deployment_group" "lambda" {
  app_name               = aws_codedeploy_app.lambda.name
  deployment_group_name  = "flux-${var.environment}-api-deployment"
  service_role_arn       = aws_iam_role.codedeploy.arn
  deployment_config_name = "CodeDeployDefault.LambdaCanary10Percent5Minutes"

  deployment_style {
    deployment_type   = "BLUE_GREEN"
    deployment_option = "WITH_TRAFFIC_CONTROL"
  }

  auto_rollback_configuration {
    enabled = true
    events  = ["DEPLOYMENT_FAILURE", "DEPLOYMENT_STOP_ON_ALARM"]
  }

  alarm_configuration {
    enabled = true
    alarms  = [aws_cloudwatch_metric_alarm.lambda_errors.alarm_name]
  }
}
```

### Rollback Procedure

```bash
# Rollback Lambda function via CodeDeploy
aws deploy create-deployment \
  --application-name flux-prod-lambda \
  --deployment-group-name flux-prod-api-deployment \
  --revision '{"revisionType": "S3", "s3Location": {"bucket": "<your-bucket>", "key": "<previous-zip>", "bundleType": "zip"}}'

# Rollback database migration
uv run alembic downgrade -1 # Or alembic downgrade <revision_id>

# Rollback frontend (re-run GitHub Actions workflow on previous commit)
# Or manually restore from S3 versioning
aws s3api copy-object \
  --copy-source flux-prod-frontend/index.html?versionId=<previous-version-id> \
  --bucket flux-prod-frontend \
  --key index.html
```

## Monitoring & Alarms

### CloudWatch Alarms with Terraform

```hcl
# infrastructure/modules/monitoring/main.tf

variable "environment" {
  type = string
}
variable "api_lambda_name" {
  type = string
}
# ... other variables

# SNS topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "flux-${var.environment}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = "ops@flux.app"
}

# Lambda error alarm
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "flux-${var.environment}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"
  dimensions = {
    FunctionName = var.api_lambda_name
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
}
# ... other alarms for database, API gateway, etc.
```

---

**Previous:** [← Backend Architecture](./09-backend-architecture.md)
**Next:** [Security & Compliance →](./11-security-compliance.md)

```