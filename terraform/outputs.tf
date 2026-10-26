output "report_api_function_url" {
  description = "Public HTTPS Lambda Function URL for ReportAPI (Paste into Dashboard API Config)"
  value       = aws_lambda_function_url.report_api_url.function_url
}

output "s3_dashboard_website_url" {
  description = "Static Website URL for S3 hosted FinOps Cost Guardian dashboard"
  value       = aws_s3_bucket_website_configuration.dashboard_website.website_endpoint
}

output "s3_dashboard_bucket_name" {
  description = "S3 bucket name where frontend dashboard build artifacts are deployed"
  value       = aws_s3_bucket.dashboard_bucket.id
}

output "dynamodb_table_name" {
  description = "DynamoDB scan log table name"
  value       = aws_dynamodb_table.scan_log.name
}

output "sns_topic_arn" {
  description = "SNS topic ARN for FinOps Cost Guardian email alerts"
  value       = aws_sns_topic.alerts.arn
}

output "resource_scanner_lambda_name" {
  description = "ResourceScanner Lambda Function Name"
  value       = aws_lambda_function.resource_scanner.function_name
}

output "remediator_lambda_name" {
  description = "Remediator Lambda Function Name"
  value       = aws_lambda_function.remediator.function_name
}

output "report_api_lambda_name" {
  description = "ReportAPI Lambda Function Name"
  value       = aws_lambda_function.report_api.function_name
}

output "api_secret_key" {
  description = "API Secret Key for x-api-key header authentication"
  value       = var.api_secret_key
  sensitive = true
}
