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
    MARKET_AI_RECOMMENDATIONS_TABLE    = var.market_ai_recommendations_table_name
    STOCK_ORDERS_TABLE                 = var.stock_orders_table_name
    PARSED_INVOICES_TABLE              = var.parsed_invoices_table_name
    SOURCE_DOCUMENTS_BUCKET            = var.source_documents_bucket_name
    API_SHARED_TOKEN                   = var.api_gateway_shared_token
  }

  tags = var.tags
}
