output "aws_account_id" {
  description = "AWS account where Terraform is executing."
  value       = data.aws_caller_identity.current.account_id
}

output "state_bucket_name" {
  description = "Terraform backend bucket used by the prod root module."
  value       = local.state_bucket_name
}

output "http_api_endpoint" {
  description = "HTTP API invoke URL."
  value       = module.http_api.api_endpoint
}

output "api_handler_function_name" {
  description = "API handler Lambda function name."
  value       = module.api_handler.function_name
}

output "current_snapshots_table_name" {
  description = "Current snapshots DynamoDB table name."
  value       = module.current_snapshots_table.name
}

output "historic_stats_table_name" {
  description = "Historic stats DynamoDB table name."
  value       = module.historic_stats_table.name
}

output "analytics_catalog_table_name" {
  description = "Analytics catalog DynamoDB table name."
  value       = module.analytics_catalog_table.name
}

output "stock_orders_table_name" {
  description = "Stock orders DynamoDB table name."
  value       = module.stock_orders_table.name
}

output "session_vectors_table_name" {
  description = "Session vectors DynamoDB table name."
  value       = module.session_vectors_table.name
}

output "daily_closing_snapshots_table_name" {
  description = "Daily closing snapshots DynamoDB table name."
  value       = module.daily_closing_snapshots_table.name
}

output "parsed_invoices_table_name" {
  description = "Parsed invoices DynamoDB table name."
  value       = module.parsed_invoices_table.name
}

output "source_documents_bucket_name" {
  description = "Source documents S3 bucket name."
  value       = module.source_documents_bucket.bucket_name
}

output "historic_stats_updater_function_name" {
  description = "Historic stats updater Lambda function name."
  value       = module.historic_stats_updater.function_name
}

output "daily_closing_snapshots_updater_function_name" {
  description = "Daily closing snapshots updater Lambda function name."
  value       = module.daily_closing_snapshots_updater.function_name
}

output "analytics_catalog_updater_function_name" {
  description = "Analytics catalog updater Lambda function name."
  value       = module.analytics_catalog_updater.function_name
}

output "session_vectors_updater_function_name" {
  description = "Session vectors updater Lambda function name."
  value       = module.session_vectors_updater.function_name
}

output "current_snapshots_pruner_function_name" {
  description = "Current snapshots pruner Lambda function name."
  value       = module.current_snapshots_pruner.function_name
}
