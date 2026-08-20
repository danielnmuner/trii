data "aws_caller_identity" "current" {}

module "current_snapshots_table" {
  source = "./services/dynamodb/current-snapshots-table"

  environment  = local.environment
  project_name = local.project_name
  tags         = local.common_tags
}

module "stock_orders_table" {
  source = "./services/dynamodb/stock-orders-table"

  environment  = local.environment
  project_name = local.project_name
  tags         = local.common_tags
}

module "parsed_invoices_table" {
  source = "./services/dynamodb/parsed-invoices-table"

  environment  = local.environment
  project_name = local.project_name
  tags         = local.common_tags
}

module "historic_stats_table" {
  source = "./services/dynamodb/historic-stats-table"

  environment  = local.environment
  project_name = local.project_name
  tags         = local.common_tags
}

module "market_ai_recommendations_table" {
  source = "./services/dynamodb/market-ai-recommendations-table"

  environment  = local.environment
  project_name = local.project_name
  tags         = local.common_tags
}

module "snapshot_ingestion_raw" {
  source = "./services/dynamodb/snapshot-ingestion-raw"

  environment  = local.environment
  project_name = local.project_name
  tags         = local.common_tags
}

module "snapshot_ingestion_checksums_table" {
  source = "./services/dynamodb/snapshot-ingestion-checksums-table"

  environment  = local.environment
  project_name = local.project_name
  tags         = local.common_tags
}

module "processed_stats_events_table" {
  source = "./services/dynamodb/processed-stats-events-table"

  environment  = local.environment
  project_name = local.project_name
  tags         = local.common_tags
}

module "source_documents_bucket" {
  source = "./services/s3/source-documents-bucket"

  environment  = local.environment
  project_name = local.project_name
  tags         = local.common_tags
}

module "bedrock_nova_pro" {
  source = "./services/bedrock/nova-pro"
}

module "historic_stats_updater" {
  source = "./services/lambda/historic-stats-updater"

  environment                                    = local.environment
  project_name                                   = local.project_name
  tags                                           = local.common_tags
  current_snapshots_stream_arn                   = module.current_snapshots_table.stream_arn
  current_snapshots_table_name                   = module.current_snapshots_table.name
  current_snapshots_table_arn                    = module.current_snapshots_table.arn
  historic_stats_table_name                      = module.historic_stats_table.name
  historic_stats_table_arn                       = module.historic_stats_table.arn
  historic_stats_index_arns                      = module.historic_stats_table.index_arns
  processed_stats_events_table_name              = module.processed_stats_events_table.name
  processed_stats_events_table_arn               = module.processed_stats_events_table.arn
  processed_stats_events_index_arns              = module.processed_stats_events_table.index_arns
  market_ai_recommendation_handler_function_name = module.market_ai_recommendation_handler.function_name
  market_ai_recommendation_handler_function_arn  = module.market_ai_recommendation_handler.function_arn
  enabled_statistical_metrics                    = local.enabled_statistical_metrics
}

module "historic_stats_backfill" {
  source = "./services/lambda/historic-stats-backfill"

  environment                  = local.environment
  project_name                 = local.project_name
  tags                         = local.common_tags
  current_snapshots_table_name = module.current_snapshots_table.name
  current_snapshots_table_arn  = module.current_snapshots_table.arn
  historic_stats_table_name    = module.historic_stats_table.name
  historic_stats_table_arn     = module.historic_stats_table.arn
  enabled_statistical_metrics  = local.enabled_statistical_metrics
}

module "market_ai_recommendation_handler" {
  source = "./services/lambda/market-ai-recommendation-handler"

  environment                          = local.environment
  project_name                         = local.project_name
  tags                                 = local.common_tags
  current_snapshots_table_name         = module.current_snapshots_table.name
  current_snapshots_table_arn          = module.current_snapshots_table.arn
  current_snapshots_index_arns         = module.current_snapshots_table.index_arns
  historic_stats_table_name            = module.historic_stats_table.name
  historic_stats_table_arn             = module.historic_stats_table.arn
  historic_stats_index_arns            = module.historic_stats_table.index_arns
  market_ai_recommendations_table_name = module.market_ai_recommendations_table.name
  market_ai_recommendations_table_arn  = module.market_ai_recommendations_table.arn
  bedrock_model_id                     = module.bedrock_nova_pro.model_id
}

module "api_handler" {
  source = "./services/lambda/api-handler"

  environment                             = local.environment
  project_name                            = local.project_name
  tags                                    = local.common_tags
  current_snapshots_table_arn             = module.current_snapshots_table.arn
  current_snapshots_index_arns            = module.current_snapshots_table.index_arns
  snapshot_ingestion_raw_table_name       = module.snapshot_ingestion_raw.name
  snapshot_ingestion_raw_table_arn        = module.snapshot_ingestion_raw.arn
  snapshot_ingestion_checksums_table_name = module.snapshot_ingestion_checksums_table.name
  snapshot_ingestion_checksums_table_arn  = module.snapshot_ingestion_checksums_table.arn
  stock_orders_table_arn                  = module.stock_orders_table.arn
  stock_orders_index_arns                 = module.stock_orders_table.index_arns
  parsed_invoices_table_arn               = module.parsed_invoices_table.arn
  parsed_invoices_index_arns              = module.parsed_invoices_table.index_arns
  source_documents_bucket_arn             = module.source_documents_bucket.bucket_arn
  current_snapshots_table_name            = module.current_snapshots_table.name
  stock_orders_table_name                 = module.stock_orders_table.name
  parsed_invoices_table_name              = module.parsed_invoices_table.name
  source_documents_bucket_name            = module.source_documents_bucket.bucket_name
  historic_stats_table_name               = module.historic_stats_table.name
  historic_stats_table_arn                = module.historic_stats_table.arn
  historic_stats_index_arns               = module.historic_stats_table.index_arns
  market_ai_recommendations_table_name    = module.market_ai_recommendations_table.name
  market_ai_recommendations_table_arn     = module.market_ai_recommendations_table.arn
  market_ai_recommendations_index_arns    = module.market_ai_recommendations_table.index_arns
  api_gateway_shared_token                = var.api_gateway_shared_token
}

module "http_api" {
  source = "./services/apigateway/http-api"

  environment               = local.environment
  project_name              = local.project_name
  tags                      = local.common_tags
  api_handler_function_name = module.api_handler.function_name
  api_handler_invoke_arn    = module.api_handler.invoke_arn
}
