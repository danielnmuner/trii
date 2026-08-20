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

output "snapshot_ingestion_raw_table_name" {
  description = "Snapshot ingestion raw DynamoDB table name."
  value       = module.snapshot_ingestion_raw.name
}

output "historic_stats_table_name" {
  description = "Historic stats DynamoDB table name."
  value       = module.historic_stats_table.name
}

output "market_ai_recommendations_table_name" {
  description = "Market AI recommendations DynamoDB table name."
  value       = module.market_ai_recommendations_table.name
}

output "snapshot_ingestion_checksums_table_name" {
  description = "Snapshot ingestion checksums DynamoDB table name."
  value       = module.snapshot_ingestion_checksums_table.name
}

output "processed_stats_events_table_name" {
  description = "Processed stats events DynamoDB table name."
  value       = module.processed_stats_events_table.name
}

output "stock_orders_table_name" {
  description = "Stock orders DynamoDB table name."
  value       = module.stock_orders_table.name
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

output "historic_stats_backfill_function_name" {
  description = "Historic stats backfill Lambda function name."
  value       = module.historic_stats_backfill.function_name
}

output "market_ai_recommendation_handler_function_name" {
  description = "Market AI recommendation handler Lambda function name."
  value       = module.market_ai_recommendation_handler.function_name
}
