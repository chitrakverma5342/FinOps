terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      ManagedBy   = "Terraform"
      Environment = "Production"
    }
  }
}

data "aws_caller_identity" "current" {}

# Package shared backend Python Lambda source code
data "archive_file" "lambda_backend_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/src"
  output_path = "${path.module}/dist/cost_guardian_backend.zip"
}

# ==============================================================================
# 1. DynamoDB Table (cost-guardian-scan-log)
# ==============================================================================
resource "aws_dynamodb_table" "scan_log" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "resource_id"
  range_key    = "scan_timestamp"

  attribute {
    name = "resource_id"
    type = "S"
  }

  attribute {
    name = "scan_timestamp"
    type = "S"
  }

  tags = {
    Name    = var.dynamodb_table_name
    Purpose = "Audit trail for CLEAN FLAGGED and REMEDIATED cloud resources"
  }
}

# ==============================================================================
# 2. SNS Alert Topic (cost-guardian-alerts)
# ==============================================================================
resource "aws_sns_topic" "alerts" {
  name = var.sns_topic_name

  tags = {
    Name    = var.sns_topic_name
    Purpose = "Formatted email alerts for idle resources and remediation logs"
  }
}

resource "aws_sns_topic_subscription" "email_sub" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ==============================================================================
# 3. AWS Lambda Functions
# ==============================================================================

# Lambda 1: ResourceScanner
resource "aws_lambda_function" "resource_scanner" {
  function_name    = "ResourceScanner"
  role             = aws_iam_role.scanner_role.arn
  handler          = "resource_scanner.lambda_handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 128
  filename         = data.archive_file.lambda_backend_zip.output_path
  source_code_hash = data.archive_file.lambda_backend_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE_NAME  = aws_dynamodb_table.scan_log.name
      SNS_TOPIC_ARN        = aws_sns_topic.alerts.arn
      IDLE_THRESHOLD_HOURS = tostring(var.idle_threshold_hours)
      API_SECRET_KEY       = var.api_secret_key
    }
  }

  tags = {
    Name = "ResourceScanner"
  }
}

# Lambda 2: Remediator
resource "aws_lambda_function" "remediator" {
  function_name    = "Remediator"
  role             = aws_iam_role.remediator_role.arn
  handler          = "remediator.lambda_handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 128
  filename         = data.archive_file.lambda_backend_zip.output_path
  source_code_hash = data.archive_file.lambda_backend_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.scan_log.name
      SNS_TOPIC_ARN       = aws_sns_topic.alerts.arn
      DRY_RUN             = "false"
      API_SECRET_KEY      = var.api_secret_key
    }
  }

  tags = {
    Name = "Remediator"
  }
}

# Lambda 3: ReportAPI
resource "aws_lambda_function" "report_api" {
  function_name    = "ReportAPI"
  role             = aws_iam_role.report_api_role.arn
  handler          = "report_api.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = data.archive_file.lambda_backend_zip.output_path
  source_code_hash = data.archive_file.lambda_backend_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE_NAME            = aws_dynamodb_table.scan_log.name
      API_SECRET_KEY                 = var.api_secret_key
      RESOURCE_SCANNER_FUNCTION_NAME = aws_lambda_function.resource_scanner.function_name
      REMEDIATOR_FUNCTION_NAME       = aws_lambda_function.remediator.function_name
    }
  }

  tags = {
    Name = "ReportAPI"
  }
}

# Lambda Function URL for ReportAPI with CORS
resource "aws_lambda_function_url" "report_api_url" {
  function_name      = aws_lambda_function.report_api.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = false
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST", "OPTIONS"]
    allow_headers     = ["Content-Type", "x-api-key", "Authorization"]
    max_age           = 86400
  }
}

# ==============================================================================
# 4. Amazon EventBridge Schedule (cost-guardian-schedule)
# ==============================================================================
resource "aws_cloudwatch_event_rule" "scanner_schedule" {
  name                = "cost-guardian-schedule"
  description         = "Triggers ResourceScanner Lambda every 6 hours"
  schedule_expression = "rate(6 hours)"
}

resource "aws_cloudwatch_event_target" "scanner_target" {
  rule      = aws_cloudwatch_event_rule.scanner_schedule.name
  target_id = "ResourceScannerTarget"
  arn       = aws_lambda_function.resource_scanner.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeToInvokeResourceScanner"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.resource_scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scanner_schedule.arn
}

# ==============================================================================
# 5. AWS Budgets ($1.00 Monthly Spend Tripwire)
# ==============================================================================
resource "aws_budgets_budget" "cost_guardian_budget" {
  name              = "cost-guardian-monthly-budget"
  budget_type       = "COST"
  limit_amount      = tostring(var.budget_limit_usd)
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2025-01-01_00:00"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}

# ==============================================================================
# 6. S3 Static Website Hosting for FinOps Dashboard
# ==============================================================================
resource "aws_s3_bucket" "dashboard_bucket" {
  bucket        = "cost-guardian-dashboard-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = {
    Name    = "cost-guardian-dashboard"
    Purpose = "Hosts compiled React FinOps Cost Guardian dashboard"
  }
}

resource "aws_s3_bucket_website_configuration" "dashboard_website" {
  bucket = aws_s3_bucket.dashboard_bucket.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

resource "aws_s3_bucket_public_access_block" "dashboard_public_block" {
  bucket = aws_s3_bucket.dashboard_bucket.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "dashboard_public_read" {
  depends_on = [aws_s3_bucket_public_access_block.dashboard_public_block]
  bucket     = aws_s3_bucket.dashboard_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.dashboard_bucket.arn}/*"
      }
    ]
  })
}
