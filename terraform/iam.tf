# ==============================================================================
# FinOps Cost Guardian — Three Least-Privilege IAM Roles
# Dedicated personal account deployment (no AWS Academy LabRole restrictions).
# ==============================================================================

# Common AssumeRole Policy Document for Lambda Service
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ------------------------------------------------------------------------------
# 1. CostGuardianScannerRole (ResourceScanner Lambda)
# Read-only EC2/EBS/EIP Describe*, DynamoDB PutItem, SNS Publish, Lambda Invoke (Remediator)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "scanner_role" {
  name               = "CostGuardianScannerRole"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Role    = "Scanner"
    Project = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "scanner_basic_execution" {
  role       = aws_iam_role.scanner_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "scanner_policy" {
  name        = "CostGuardianScannerPolicy"
  description = "Least-privilege permissions for FinOps ResourceScanner Lambda"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EC2ReadOnlyDiscovery"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeVolumes",
          "ec2:DescribeAddresses",
          "ec2:DescribeTags",
          "ec2:DescribeAvailabilityZones"
        ]
        Resource = "*"
      },
      {
        Sid    = "DynamoDBLogAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.dynamodb_table_name}"
      },
      {
        Sid    = "SNSPublishAlert"
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = "arn:aws:sns:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.sns_topic_name}"
      },
      {
        Sid    = "InvokeRemediatorPipeline"
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:Remediator"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "scanner_custom_attach" {
  role       = aws_iam_role.scanner_role.name
  policy_arn = aws_iam_policy.scanner_policy.arn
}

# ------------------------------------------------------------------------------
# 2. CostGuardianRemediatorRole (Remediator Lambda)
# Stop EC2, Delete EBS, Release EIP, DynamoDB Read/Write, SNS Publish
# ------------------------------------------------------------------------------
resource "aws_iam_role" "remediator_role" {
  name               = "CostGuardianRemediatorRole"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Role    = "Remediator"
    Project = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "remediator_basic_execution" {
  role       = aws_iam_role.remediator_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "remediator_policy" {
  name        = "CostGuardianRemediatorPolicy"
  description = "Least-privilege mutation permissions for FinOps Remediator Lambda"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EC2StateVerification"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeVolumes",
          "ec2:DescribeAddresses"
        ]
        Resource = "*"
      },
      {
        Sid    = "SafeRemediationMutations"
        Effect = "Allow"
        Action = [
          "ec2:StopInstances",
          "ec2:DeleteVolume",
          "ec2:ReleaseAddress",
          "ec2:DisassociateAddress"
        ]
        Resource = "*"
      },
      {
        Sid    = "DynamoDBAuditTrail"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
          "dynamodb:Scan"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.dynamodb_table_name}"
      },
      {
        Sid    = "SNSRemediationConfirmation"
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = "arn:aws:sns:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.sns_topic_name}"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "remediator_custom_attach" {
  role       = aws_iam_role.remediator_role.name
  policy_arn = aws_iam_policy.remediator_policy.arn
}

# ------------------------------------------------------------------------------
# 3. CostGuardianReportApiRole (ReportAPI Lambda Function URL)
# DynamoDB Query/Scan & synchronous Lambda trigger for manual scans & remediations
# ------------------------------------------------------------------------------
resource "aws_iam_role" "report_api_role" {
  name               = "CostGuardianReportApiRole"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Role    = "ReportAPI"
    Project = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "report_api_basic_execution" {
  role       = aws_iam_role.report_api_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "report_api_policy" {
  name        = "CostGuardianReportApiPolicy"
  description = "Permissions for ReportAPI to read scan history and invoke scanner/remediator"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBReadHistory"
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:Query",
          "dynamodb:GetItem"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.dynamodb_table_name}"
      },
      {
        Sid    = "TriggerBackendLambdas"
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:ResourceScanner",
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:Remediator"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "report_api_custom_attach" {
  role       = aws_iam_role.report_api_role.name
  policy_arn = aws_iam_policy.report_api_policy.arn
}
