data "aws_iam_policy_document" "inline" {
  statement {
    sid    = "ReadCurrentSnapshots"
    effect = "Allow"
    actions = [
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
      "dynamodb:BatchGetItem",
      "dynamodb:GetItem",
    ]
    resources = [var.historic_stats_table_arn]
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
    resources = [var.zscore_opportunities_table_arn]
  }
}

module "function" {
  source = "../../../../modules/lambda/python-function"

  function_name = "${var.project_name}-${var.environment}-zscore-opportunities-sampler"
  description   = "Samples latest current snapshots on a schedule and upserts z-score opportunity records."
  source_dir    = "${path.module}/src"
  timeout       = 300
  memory_size   = 512
  policy_json   = data.aws_iam_policy_document.inline.json

  environment_variables = {
    CURRENT_SNAPSHOTS_TABLE    = var.current_snapshots_table_name
    HISTORIC_STATS_TABLE       = var.historic_stats_table_name
    STOCK_ORDERS_TABLE         = var.stock_orders_table_name
    ZSCORE_OPPORTUNITIES_TABLE = var.zscore_opportunities_table_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "schedule" {
  name                = "${var.project_name}-${var.environment}-zscore-opportunities-sampler"
  description         = "Runs the z-score opportunities sampler every 10 minutes."
  schedule_expression = var.schedule_expression

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.schedule.name
  target_id = "zscore-opportunities-sampler"
  arn       = module.function.function_arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridgeZscoreOpportunitiesSampler"
  action        = "lambda:InvokeFunction"
  function_name = module.function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule.arn
}
