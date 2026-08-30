data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadCurrentSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.current_snapshots_table_arn],
      var.current_snapshots_index_arns,
    )
  }

  statement {
    sid    = "ReadAnalyticsCatalog"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.analytics_catalog_table_arn],
      var.analytics_catalog_table_index_arns,
    )
  }

  statement {
    sid    = "ReadSnapshotIngestionRaw"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.snapshot_ingestion_raw_table_arn],
      var.snapshot_ingestion_raw_index_arns,
    )
  }

  statement {
    sid    = "ReadSnapshotIngestionChecksums"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.snapshot_ingestion_checksums_table_arn],
      var.snapshot_ingestion_checksums_index_arns,
    )
  }

  statement {
    sid    = "ReadStockOrders"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.stock_orders_table_arn],
      var.stock_orders_index_arns,
    )
  }

  statement {
    sid    = "ReadParsedInvoices"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.parsed_invoices_table_arn],
      var.parsed_invoices_index_arns,
    )
  }

  statement {
    sid    = "ReadHistoricStats"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.historic_stats_table_arn],
      var.historic_stats_index_arns,
    )
  }

  statement {
    sid    = "ReadProcessedStatsEvents"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.processed_stats_events_table_arn],
      var.processed_stats_events_index_arns,
    )
  }

  statement {
    sid    = "ReadDailyClosingSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.daily_closing_snapshots_table_arn],
      var.daily_closing_snapshots_index_arns,
    )
  }

  statement {
    sid    = "ReadZscoreOpportunities"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.zscore_opportunities_table_arn],
      var.zscore_opportunities_index_arns,
    )
  }

  statement {
    sid    = "ReadSessionVectors"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.session_vectors_table_arn],
      var.session_vectors_index_arns,
    )
  }

  statement {
    sid    = "ReadMarketAiRecommendations"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = concat(
      [var.market_ai_recommendations_table_arn],
      var.market_ai_recommendations_index_arns,
    )
  }

  statement {
    sid    = "WriteCurrentSnapshots"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:BatchWriteItem",
      "dynamodb:TransactWriteItems",
    ]
    resources = [
      var.snapshot_ingestion_raw_table_arn,
      var.current_snapshots_table_arn,
      var.snapshot_ingestion_checksums_table_arn,
    ]
  }

  statement {
    sid    = "WriteStockOrders"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:BatchWriteItem",
    ]
    resources = [var.stock_orders_table_arn]
  }

  statement {
    sid    = "WriteParsedInvoices"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:BatchWriteItem",
    ]
    resources = [var.parsed_invoices_table_arn]
  }

  statement {
    sid    = "WriteSourceDocuments"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${var.source_documents_bucket_arn}/*"]
  }

  statement {
    sid       = "ListSourceDocumentsBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.source_documents_bucket_arn]
  }

}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-api-handler"
  description   = "Receives HTTP API requests and persists operational records."
  source_dir    = "${path.module}/src"
  timeout       = 30
  memory_size   = 256
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE            = var.current_snapshots_table_name
    SNAPSHOT_INGESTION_RAW_TABLE       = var.snapshot_ingestion_raw_table_name
    SNAPSHOT_INGESTION_CHECKSUMS_TABLE = var.snapshot_ingestion_checksums_table_name
    HISTORIC_STATS_TABLE               = var.historic_stats_table_name
    PROCESSED_STATS_EVENTS_TABLE       = var.processed_stats_events_table_name
    DAILY_CLOSING_SNAPSHOTS_TABLE      = var.daily_closing_snapshots_table_name
    ZSCORE_OPPORTUNITIES_TABLE         = var.zscore_opportunities_table_name
    SESSION_VECTORS_TABLE             = var.session_vectors_table_name
    MARKET_AI_RECOMMENDATIONS_TABLE    = var.market_ai_recommendations_table_name
    ANALYTICS_CATALOG_TABLE            = var.analytics_catalog_table_name
    STOCK_ORDERS_TABLE                 = var.stock_orders_table_name
    PARSED_INVOICES_TABLE              = var.parsed_invoices_table_name
    SOURCE_DOCUMENTS_BUCKET            = var.source_documents_bucket_name
    API_SHARED_TOKEN                   = var.api_gateway_shared_token
  }

  tags = var.tags
}
