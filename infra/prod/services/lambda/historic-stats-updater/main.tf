data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadCurrentSnapshotsStream"
    effect = "Allow"
    actions = [
      "dynamodb:DescribeStream",
      "dynamodb:GetRecords",
      "dynamodb:GetShardIterator",
      "dynamodb:ListStreams",
    ]
    resources = [var.current_snapshots_stream_arn]
  }

  statement {
    sid    = "ReadCurrentSnapshotsTable"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:Query",
    ]
    resources = [var.current_snapshots_table_arn]
  }

  statement {
    sid    = "ReadWriteHistoricStats"
    effect = "Allow"
    actions = [
      "dynamodb:BatchGetItem",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:TransactWriteItems",
    ]
    resources = concat(
      [var.historic_stats_table_arn, var.processed_stats_events_table_arn],
      var.historic_stats_index_arns,
      var.processed_stats_events_index_arns,
    )
  }

  statement {
    sid    = "ReadStockOrders"
    effect = "Allow"
    actions = [
      "dynamodb:Query",
    ]
    resources = concat(
      [var.stock_orders_table_arn],
      var.stock_orders_index_arns,
    )
  }

  statement {
    sid    = "WriteZscoreOpportunities"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
    ]
    resources = concat(
      [var.zscore_opportunities_table_arn],
      var.zscore_opportunities_index_arns,
    )
  }

  statement {
    sid     = "InvokeMarketAiRecommendationHandler"
    effect  = "Allow"
    actions = ["lambda:InvokeFunction"]
    resources = [
      var.market_ai_recommendation_handler_function_arn,
      "${var.market_ai_recommendation_handler_function_arn}:*",
    ]
  }
}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-historic-stats-updater"
  description   = "Consumes current snapshots stream records and incrementally updates official historic stats."
  source_dir    = "${path.module}/src"
  timeout       = 60
  memory_size   = 512
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE                   = var.current_snapshots_table_name
    HISTORIC_STATS_TABLE                      = var.historic_stats_table_name
    PROCESSED_STATS_EVENTS_TABLE              = var.processed_stats_events_table_name
    STOCK_ORDERS_TABLE                        = var.stock_orders_table_name
    ZSCORE_OPPORTUNITIES_TABLE                = var.zscore_opportunities_table_name
    MARKET_AI_RECOMMENDATION_HANDLER_FUNCTION = var.market_ai_recommendation_handler_function_name
    ENABLED_STATISTICAL_METRICS               = join(",", var.enabled_statistical_metrics)
  }

  tags = var.tags
}

resource "aws_lambda_event_source_mapping" "current_snapshots_stream" {
  event_source_arn  = var.current_snapshots_stream_arn
  function_name     = module.function.function_arn
  starting_position = "LATEST"
  batch_size        = 10
}
