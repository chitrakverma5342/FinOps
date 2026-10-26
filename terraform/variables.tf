variable "aws_region" {
  description = "AWS deployment region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name tag and prefix"
  type        = string
  default     = "FinOpsCostGuardian"
}

variable "alert_email" {
  description = "Owner verified email address for SNS idle-resource alerts and $1.00 Budget tripwires"
  type        = string
  default     = "your-email@example.com"
}

variable "idle_threshold_hours" {
  description = "Threshold in hours before a running EC2 instance is flagged as idle"
  type        = number
  default     = 12
}

variable "budget_limit_usd" {
  description = "AWS Monthly spend tripwire limit in USD"
  type        = number
  default     = 1.00
}

variable "api_secret_key" {
  description = "Shared secret key passed in the x-api-key header to authenticate with ReportAPI"
  type        = string
  default     = "cost-guardian-secret-2025"
  sensitive   = true
}

variable "dynamodb_table_name" {
  description = "DynamoDB table name for scan audit logs"
  type        = string
  default     = "cost-guardian-scan-log"
}

variable "sns_topic_name" {
  description = "SNS topic name for alerts"
  type        = string
  default     = "cost-guardian-alerts"
}
